import os
import io
import sys
import time
import pandas as pd
import psycopg2

# Database Connection Details
DB_CONFIG = {
    "dbname": os.getenv("DB_NAME", "market_monitoring"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "secure_password"),
    "host": os.getenv("DB_HOST", "localhost")
}

# Config from env variables
PARQUET_FILE = os.getenv("PARQUET_FILE")
TABLE_NAME = os.getenv("TABLE_NAME")
CHUNK_SIZE = 1000000  # 1 million rows per batch to limit memory usage

def bulk_import():
    if not PARQUET_FILE or not TABLE_NAME:
        print("ERROR: PARQUET_FILE or TABLE_NAME environment variables are missing.")
        sys.exit(1)

    if not os.path.exists(PARQUET_FILE):
        print(f"WARNING: Parquet file '{PARQUET_FILE}' not found. Skipping historical import.")
        return

    print(f"Connecting to database at {DB_CONFIG['host']}...")
    try:
        conn = psycopg2.connect(**DB_CONFIG)
    except Exception as e:
        print(f"ERROR: Could not connect to database: {e}")
        sys.exit(1)

    try:
        with conn.cursor() as cur:
            # Check if table has records already
            print(f"Checking if table '{TABLE_NAME}' already contains data...")
            cur.execute(f"SELECT EXISTS (SELECT 1 FROM {TABLE_NAME} LIMIT 1);")
            exists = cur.fetchone()[0]

            if exists:
                print(f"Table '{TABLE_NAME}' is not empty. Skipping historical parquet import.")
                return

            print(f"Table '{TABLE_NAME}' is empty. Reading parquet file '{PARQUET_FILE}'...")
            start_time = time.time()
            
            # Read parquet file using pandas
            df = pd.read_parquet(PARQUET_FILE)
            total_rows = len(df)
            print(f"Loaded {total_rows:,} rows from '{PARQUET_FILE}' in {time.time() - start_time:.2f} seconds.")

            # Ensure columns are ordered correctly as (time_raw, price)
            if 'time_raw' not in df.columns or 'price' not in df.columns:
                print(f"ERROR: Parquet file must contain 'time_raw' and 'price' columns. Found: {list(df.columns)}")
                sys.exit(1)

            df = df[['time_raw', 'price']]

            print(f"Starting bulk copy of {total_rows:,} rows into '{TABLE_NAME}'...")
            copy_start = time.time()

            for i in range(0, total_rows, CHUNK_SIZE):
                chunk = df.iloc[i:i + CHUNK_SIZE]
                
                # Write chunk to memory string buffer as CSV
                buffer = io.StringIO()
                chunk.to_csv(buffer, index=False, header=False)
                buffer.seek(0)

                # Bulk insert via PostgreSQL COPY
                cur.copy_expert(f"COPY {TABLE_NAME} (time_raw, price) FROM STDIN WITH CSV", buffer)
                print(f"Imported {min(i + CHUNK_SIZE, total_rows):,} / {total_rows:,} rows...")

            # Commit the transaction
            conn.commit()
            duration = time.time() - copy_start
            print(f"SUCCESS: Finished bulk import for table '{TABLE_NAME}' in {duration:.2f} seconds.")
            
    except Exception as e:
        conn.rollback()
        print(f"ERROR: Import failed, rolled back database changes. Error details: {e}")
        sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    bulk_import()
