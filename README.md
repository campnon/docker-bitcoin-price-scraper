# Docker Bitcoin & Ethereum Price Scraper and Storage

This project is a containerized real-time cryptocurrency tick data scraper that reads prices via WebSockets, saves them to a PostgreSQL database, aggregates the raw prices into daily, weekly, and monthly Open-High-Low-Close (OHLC) values, and pre-loads historical data from parquet archive files.

## Project Structure

```
├── data/
│   ├── brti_prices.parquet       # Historical BTC tick data (approx. 160MB, track with Git LFS)
│   └── eth_prices.parquet        # Historical ETH tick data (approx. 116MB, track with Git LFS)
├── scripts/                      # Local management, migration, and export scripts
│   ├── config.py.example         # Example template for local config settings (copy to config.py)
│   ├── price_sync.py             # Remote-to-local DB synchronization tool (selective day/range syncing)
│   ├── parquet_chart_data_bit.py # Local DB exporter (exports tables to Parquet or compressed CSV)
│   ├── migrate_db.py             # DB migration script (idempotent, batch-wise)
│   └── import_csv_history.py     # Imports historical daily/weekly/monthly OHLC CSV files
├── Dockerfile                    # Docker image building instructions
├── docker-compose.yml            # Multi-container orchestration (scrapers and Postgres DB)
├── entrypoint.py                 # Platform-independent container boot coordinator (wait for DB, import history)
├── import_parquet.py             # High-performance bulk importer using COPY protocol
├── init.sql                      # Initial database schemas for brti_prices and eth_prices
├── ohlc_setup.sql                # SQL schemas for btc_ohlc table and aggregation function
├── main.py                       # Real-time WebSocket scraper client
├── requirements.txt              # Python application dependencies
├── .gitignore                    # Files excluded from Git tracking
├── .env                          # Local environment variable overrides (ignored by Git)
└── README.md                     # Setup & usage instructions
```

---


### Pull from GitHub (On the server / friend's machine)
Before cloning the repo, your friend should also have Git LFS installed.
1. Run `git lfs install` on the target machine.
2. Clone the repository:
   ```bash
   git clone https://github.com/campnon/docker-bitcoin-price-scraper
   ```
   Git LFS will automatically download the full parquet files instead of their pointer files.

---

## Deployment & Running

Everything is orchestrated using Docker Compose. Setting it up is extremely simple:

1. **Start the containers**:
   Run the following command in the project root directory:
   ```bash
   docker compose up -d --build
   ```

   This will:
   - Start the PostgreSQL database (`db`) container.
   - Run the schema scripts (`init.sql` and `ohlc_setup.sql`) automatically in the database container.
   - Start the Bitcoin scraper (`btc_scraper`) and Ethereum scraper (`eth_scraper`) containers.
   - **Automatic Import**: Each scraper's entrypoint will wait for the database to become ready, check if their respective database tables are empty, and if so, perform a high-speed bulk import of historical tick data from the parquet files (~16 million rows per file, completing in 1-2 minutes).
   - **Launch Scraping**: Begin real-time WebSocket connection to feed new tick data.
   - **Trigger Aggregations**: The Bitcoin scraper will trigger the OHLC aggregation function every 60 seconds.

2. **Verify it is running**:
   Check container logs to see the startup progress and real-time prices coming in:
   ```bash
   # See logs for Bitcoin scraper
   docker compose logs -f btc_scraper

   # See logs for Ethereum scraper
   docker compose logs -f eth_scraper
   ```

3. **Stop the services**:
   To stop the scrapers and database without destroying the data:
   ```bash
   docker compose down
   ```
   *Note: The database state is persisted in a Docker volume named `postgres_data`.*

---

## Local Management Scripts

The `scripts/` directory contains various utility scripts for database management, data synchronization, migrations, and exports.

### 1. Configuration (`config.py`)
To configure local database credentials:
1. Copy the example config file:
   ```bash
   cp scripts/config.py.example scripts/config.py
   ```
2. Open `scripts/config.py` and set your local database host, port, username, and password. (Note: `config.py` is ignored by Git to keep your credentials secure).

### 2. Environment Variables (`.env`)
You can create a `.env` file at the root of the project to store sensitive settings, such as the remote database credentials:
```env
# Remote Database Configuration
REMOTE_HOST=135.148.26.79
REMOTE_PORT=5432
TARGET_DB_NAME=market_monitoring
TARGET_DB_USER=postgres_mesisamu
TARGET_DB_PASSWORD=your_remote_db_password
```
This `.env` file is also ignored by Git.

### 3. Remote-to-Local Database Sync (`price_sync.py`)
Use this script to pull price records for specific day(s) or a date range from the remote database and merge them into your local database. It is timezone-aware (`America/New_York`) and uses server-side cursors to pull large datasets efficiently.

- **Interactive Mode**:
  Run the script with no arguments and follow the prompt:
  ```bash
  python scripts/price_sync.py
  ```
  *Pressing Enter at the prompt defaults to syncing **today**.*
  
- **CLI Argument Mode**:
  Provide specific dates or ranges via the `--days` parameter:
  ```bash
  # Sync a single day
  python scripts/price_sync.py --days 2026-08-01

  # Sync multiple comma-separated days
  python scripts/price_sync.py --days "2026-08-01, 2026-08-02"

  # Sync a date range (inclusive of start and end days)
  python scripts/price_sync.py --days "2026-08-01:2026-08-03"
  ```

### 4. Local Data Export (`parquet_chart_data_bit.py`)
Exports local database tables into local data files.
- **Usage**:
  ```bash
  python scripts/parquet_chart_data_bit.py
  ```
- **Configuration**: Inside the script, you can set `EXPORT_FORMAT` to `"parquet"` (requires `pyarrow` installed: `pip install pyarrow`) or `"csv"` (exports to a compressed `.csv.gz` file). Files are written to the `data/` folder.

### 5. Database Migration (`migrate_db.py`)
Used to migrate price data between a source database and a target database in bulk batches with conflict handling.
- **Usage**:
  Set the target host environment variable and run:
  ```bash
  TARGET_DB_HOST=your_target_ip python scripts/migrate_db.py
  ```

### 6. Historical CSV Import (`import_csv_history.py`)
Pre-loads daily, weekly, and monthly historical OHLC data from CSV files (`daily.csv`, `weekly.csv`, `monthly.csv`) into the local `btc_ohlc` database table.
- **Usage**:
  ```bash
  python scripts/import_csv_history.py
  ```

---

## Technical Details

- **Bulk Import Speed**: Instead of standard row-by-row inserts (which would take hours for 16M rows), `import_parquet.py` reads the parquet in chunks and utilizes the PostgreSQL `COPY` protocol via `psycopg2`'s `copy_expert`.
- **Platform-Independent Startup**: `entrypoint.py` is written in Python rather than Bash to avoid CRLF/LF line-ending incompatibilities between Windows and Linux environments.
- **Aggregations**: Bitcoin aggregations are performed database-side via `ohlc_setup.sql`. The logic is invoked by the Python client and runs in `update_ohlc_from_brti()`.

