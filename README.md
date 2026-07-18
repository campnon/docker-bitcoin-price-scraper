# Docker Bitcoin & Ethereum Price Scraper and Storage

This project is a containerized real-time cryptocurrency tick data scraper that reads prices via WebSockets, saves them to a PostgreSQL database, aggregates the raw prices into daily, weekly, and monthly Open-High-Low-Close (OHLC) values, and pre-loads historical data from parquet archive files.

## Project Structure

```
├── data/
│   ├── brti_prices.parquet    # Historical BTC tick data (approx. 160MB, track with Git LFS)
│   └── eth_prices.parquet     # Historical ETH tick data (approx. 116MB, track with Git LFS)
├── Dockerfile                 # Docker image building instructions
├── docker-compose.yml         # Multi-container orchestration (scrapers and Postgres DB)
├── entrypoint.py              # Platform-independent container boot coordinator (wait for DB, import history)
├── import_parquet.py          # High-performance bulk importer using COPY protocol
├── init.sql                   # Initial database schemas for brti_prices and eth_prices
├── ohlc_setup.sql             # SQL schemas for btc_ohlc table and aggregation function
├── main.py                    # Real-time WebSocket scraper client
├── requirements.txt           # Python application dependencies
├── .gitignore                 # Files excluded from Git tracking
└── README.md                  # Setup & usage instructions
```

---

## Prerequisites & Large File Storage (Git LFS)

Because the historical parquet files (`brti_prices.parquet` and `eth_prices.parquet`) are larger than 100MB, GitHub will reject pushing them directly. You must use **Git LFS (Large File Storage)** to push them to your repository.

### Push to GitHub (On your machine)
1. **Install Git LFS**:
   Download and install Git LFS from [git-lfs.github.com](https://git-lfs.github.com/) or via your package manager:
   ```bash
   git lfs install
   ```
2. **Track Parquet files**:
   Ensure Git LFS is configured to track `.parquet` files in this repository:
   ```bash
   git lfs track "*.parquet"
   ```
   *Note: This generates a `.gitattributes` file. Make sure to commit and push it.*

3. **Commit and Push**:
   ```bash
   git add .gitattributes
   # Add your files as usual
   git add .
   git commit -m "Initial commit with Git LFS configuration"
   git push origin main
   ```

### Pull from GitHub (On the server / friend's machine)
Before cloning the repo, your friend should also have Git LFS installed.
1. Run `git lfs install` on the target machine.
2. Clone the repository:
   ```bash
   git clone <your-repo-url>
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

## Technical Details

- **Bulk Import Speed**: Instead of standard row-by-row inserts (which would take hours for 16M rows), `import_parquet.py` reads the parquet in chunks and utilizes the PostgreSQL `COPY` protocol via `psycopg2`'s `copy_expert`.
- **Platform-Independent Startup**: `entrypoint.py` is written in Python rather than Bash to avoid CRLF/LF line-ending incompatibilities between Windows and Linux environments.
- **Aggregations**: Bitcoin aggregations are performed database-side via `ohlc_setup.sql`. The logic is invoked by the Python client and runs in `update_ohlc_from_brti()`.
