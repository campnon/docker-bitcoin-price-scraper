import os
import sys
import argparse
from datetime import datetime, time, timezone, timedelta
from zoneinfo import ZoneInfo
import psycopg2
import psycopg2.extras

import config

def load_dotenv():
    # Resolve the .env path relative to this script's directory (one level up)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    dotenv_path = os.path.abspath(os.path.join(script_dir, "..", ".env"))
    if os.path.exists(dotenv_path):
        with open(dotenv_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip()
                    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                        val = val[1:-1]
                    os.environ[key] = val

# Load environment variables from .env
load_dotenv()

# --- Configuration ---

# REMOTE (Old 'Target' in db_move.py, now the Source of Truth/Data)
REMOTE_HOST = os.getenv("REMOTE_HOST", "135.148.26.79")
REMOTE_PORT = os.getenv("REMOTE_PORT", "5432")
# Using TARGET credentials from db_move.py as this was the 'copy db in the cloud'
REMOTE_DB_NAME = os.getenv("TARGET_DB_NAME", "market_monitoring")
REMOTE_DB_USER = os.getenv("TARGET_DB_USER", "postgres_mesisamu")
REMOTE_DB_PASSWORD = os.getenv("TARGET_DB_PASSWORD", "")

# LOCAL (Destination)
# Using config.py as it is verified to work
LOCAL_HOST = config.DB_HOST
LOCAL_PORT = config.DB_PORT
LOCAL_DB_NAME = config.DB_NAME
LOCAL_DB_USER = config.DB_USER
LOCAL_DB_PASSWORD = config.DB_PASSWORD

TABLES = ["brti_prices", "eth_prices"]
BATCH_SIZE = 20000

def get_connection(name, host, port, dbname, user, password):
    print(f"Connecting to {name} DB at {host}:{port}...")
    try:
        if not host:
             raise ValueError("Host is None")
        conn = psycopg2.connect(
            dbname=dbname,
            user=user,
            password=password,
            host=host,
            port=port
        )
        return conn
    except Exception as e:
        print(f"Failed to connect to {name} DB: {e}")
        return None

def get_day_range_ms(date_str, tz_name="America/New_York"):
    """
    Parses a YYYY-MM-DD string and returns the start and end of that day in milliseconds.
    start is inclusive (00:00:00.000), end is exclusive (00:00:00.000 of the next day).
    """
    tz = ZoneInfo(tz_name)
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"Invalid date format: '{date_str}'. Must be YYYY-MM-DD.")
    
    # Create start of day datetime in the specified timezone
    start_dt = datetime(dt.year, dt.month, dt.day, tzinfo=tz)
    end_dt = start_dt + timedelta(days=1)
    
    start_ms = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)
    return start_ms, end_ms

def parse_days_input(days_input, tz_name="America/New_York"):
    """
    Parses user input representing day(s) or range and returns a list of (start_ms, end_ms) tuples.
    Input formats:
      - 'today' -> today's range
      - 'YYYY-MM-DD' -> range for that day
      - 'YYYY-MM-DD, YYYY-MM-DD' -> list of ranges
      - 'YYYY-MM-DD:YYYY-MM-DD' -> start of first day to end of second day
    """
    tz = ZoneInfo(tz_name)
    ranges = []
    
    # Split by comma to support multiple days/ranges
    parts = [p.strip() for p in days_input.split(",") if p.strip()]
    if not parts:
        raise ValueError("No dates or ranges provided.")
        
    for part in parts:
        if ":" in part:
            start_str, end_str = [x.strip() for x in part.split(":", 1)]
            if start_str.lower() == "today":
                start_str = datetime.now(tz).strftime("%Y-%m-%d")
            if end_str.lower() == "today":
                end_str = datetime.now(tz).strftime("%Y-%m-%d")
            
            start_ms, _ = get_day_range_ms(start_str, tz_name)
            _, end_ms = get_day_range_ms(end_str, tz_name)
            if start_ms > end_ms:
                raise ValueError(f"Invalid range '{part}': start date is after end date.")
            ranges.append((start_ms, end_ms))
        elif part.lower() == "today":
            today_str = datetime.now(tz).strftime("%Y-%m-%d")
            ranges.append(get_day_range_ms(today_str, tz_name))
        else:
            ranges.append(get_day_range_ms(part, tz_name))
            
    return ranges

def sync_table(table_name, remote_conn, local_conn, ranges):
    print(f"\n--- Syncing table: {table_name} ---")
    
    # 1. Fetch from Remote
    # We filter data based on the provided ranges
    where_clauses = []
    query_params = []
    for start, end in ranges:
        where_clauses.append("(time_raw >= %s AND time_raw < %s)")
        query_params.extend([start, end])
    
    where_clause = " OR ".join(where_clauses)
    
    # Named server-side cursor to avoid loading all rows into client memory
    r_cur = remote_conn.cursor(name=f"sync_{table_name}")
    query = f"SELECT time_raw, price FROM {table_name} WHERE {where_clause} ORDER BY time_raw ASC"
    
    r_cur.execute(query, tuple(query_params))
    l_cur = local_conn.cursor()
    total_synced = 0
    
    while True:
        rows = r_cur.fetchmany(BATCH_SIZE)
        if not rows:
            break
            
        # 2. Insert into Local
        # We assume columns: time_raw (BIGINT PK), price (NUMERIC)
        # time_est is generated, so we skip it.
        insert_query = f"""
            INSERT INTO {table_name} (time_raw, price)
            VALUES %s
            ON CONFLICT (time_raw) DO NOTHING
        """
        
        try:
            psycopg2.extras.execute_values(
                l_cur, 
                insert_query, 
                rows,
                template="(%s, %s)" 
            )
            local_conn.commit()
            total_synced += len(rows)
            print(f"Processed {total_synced} rows...", end='\r')
            
        except Exception as e:
            print(f"\nError inserting batch: {e}")
            local_conn.rollback()
            r_cur.close()
            l_cur.close()
            return

    r_cur.close()
    l_cur.close()
    print(f"\nFinished {table_name}. Total rows processed/inserted: {total_synced}")

def main():
    parser = argparse.ArgumentParser(description="Sync price data from remote to local database for specific days.")
    parser.add_argument(
        "--days",
        type=str,
        help="Day(s) to sync. Format: 'today', 'YYYY-MM-DD', 'YYYY-MM-DD, YYYY-MM-DD', or a range 'YYYY-MM-DD:YYYY-MM-DD'."
    )
    args = parser.parse_args()
    
    days_input = args.days
    if not days_input:
        try:
            days_input = input(
                "Enter day, days, or range to sync (e.g. '2026-08-01', '2026-08-01, 2026-08-02', '2026-08-01:2026-08-03', or press Enter for 'today'): "
            ).strip()
        except KeyboardInterrupt:
            print("\nExiting.")
            return
            
    if not days_input:
        days_input = "today"
        
    try:
        ranges = parse_days_input(days_input)
    except ValueError as e:
        print(f"Error parsing input: {e}")
        return
        
    print("\nParsed time ranges to sync (America/New_York):")
    tz = ZoneInfo("America/New_York")
    for start, end in ranges:
        start_dt = datetime.fromtimestamp(start / 1000.0, tz=tz)
        end_dt = datetime.fromtimestamp(end / 1000.0, tz=tz)
        print(f"  - From {start_dt.strftime('%Y-%m-%d %H:%M:%S')} to {end_dt.strftime('%Y-%m-%d %H:%M:%S')} (exclusive)")
    
    remote_conn = get_connection("REMOTE", REMOTE_HOST, REMOTE_PORT, REMOTE_DB_NAME, REMOTE_DB_USER, REMOTE_DB_PASSWORD)
    local_conn = get_connection("LOCAL", LOCAL_HOST, LOCAL_PORT, LOCAL_DB_NAME, LOCAL_DB_USER, LOCAL_DB_PASSWORD)
    
    if not remote_conn or not local_conn:
        print("Connection failure. Exiting.")
        if remote_conn: remote_conn.close()
        if local_conn: local_conn.close()
        return

    try:
        for table in TABLES:
            sync_table(table, remote_conn, local_conn, ranges)
        print("\nSync completed successfully.")
    except Exception as e:
        print(f"\nSync failed: {e}")
    finally:
        if remote_conn: remote_conn.close()
        if local_conn: local_conn.close()

if __name__ == "__main__":
    main()
