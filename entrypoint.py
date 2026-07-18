import os
import sys
import time
import psycopg2
import subprocess

def main():
    # Retrieve DB config from env variables
    db_host = os.getenv("DB_HOST", "db")
    db_name = os.getenv("DB_NAME", "market_monitoring")
    db_user = os.getenv("DB_USER", "postgres")
    db_pass = os.getenv("DB_PASSWORD", "secure_password")

    print(f"Waiting for PostgreSQL database to start at '{db_host}'...")
    while True:
        try:
            conn = psycopg2.connect(
                dbname=db_name,
                user=db_user,
                password=db_pass,
                host=db_host
            )
            conn.close()
            print("PostgreSQL is up and accepting connections.")
            break
        except psycopg2.OperationalError:
            time.sleep(1)

    # Check and run parquet import
    parquet_file = os.getenv("PARQUET_FILE")
    table_name = os.getenv("TABLE_NAME")

    if parquet_file and table_name:
        print(f"Parquet import configured: importing '{parquet_file}' to table '{table_name}' if empty.")
        # Launch import_parquet.py
        result = subprocess.run([sys.executable, "import_parquet.py"])
        if result.returncode != 0:
            print("WARNING: Parquet import script failed. Proceeding to run scraper anyway.")
        else:
            print("Parquet import process completed successfully.")
    else:
        print("No PARQUET_FILE and TABLE_NAME configured. Skipping historical import.")

    # Launch the main scraping process
    print("Launching scraper (main.py)...")
    sys.stdout.flush()
    sys.stderr.flush()

    # Replaces the current process with main.py so signals (SIGTERM, SIGINT) are handled cleanly.
    os.execvp(sys.executable, [sys.executable, "main.py"])

if __name__ == "__main__":
    main()
