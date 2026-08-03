import os
import psycopg2
import pandas as pd
import config

# LOCAL DB Configuration (imported from config.py)
DB_HOST = config.DB_HOST
DB_PORT = config.DB_PORT
DB_NAME = config.DB_NAME
DB_USER = config.DB_USER
DB_PASSWORD = config.DB_PASSWORD

TABLES = ["brti_prices", "eth_prices"]

# CHOOSE YOUR EXPORT FORMAT: 'parquet' or 'csv'
EXPORT_FORMAT = "parquet" 

def get_connection():
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        return conn
    except Exception as e:
        print(f"Failed to connect to local database: {e}")
        return None

def export_table(table_name, conn, format_type):
    print(f"\n--- Exporting table: {table_name} ---")
    query = f"SELECT time_raw, price FROM {table_name} ORDER BY time_raw ASC;"
    
    print("Fetching data from local database...")
    try:
        # Load data directly into a Pandas DataFrame
        df = pd.read_sql_query(query, conn)
        print(f"Loaded {len(df):,} rows into memory.")
        
        # Resolve target directory (data/ folder at project root)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        target_dir = os.path.abspath(os.path.join(script_dir, "..", "data"))
        os.makedirs(target_dir, exist_ok=True)
        
        if format_type == "parquet":
            filename = f"{table_name}.parquet"
            filepath = os.path.join(target_dir, filename)
            print(f"Writing to Parquet: {filepath}...")
            # Requires 'pyarrow' library: pip install pyarrow
            df.to_parquet(filepath, index=False)
            
        else: # Default to compressed CSV (.csv.gz)
            filename = f"{table_name}.csv.gz"
            filepath = os.path.join(target_dir, filename)
            print(f"Writing to compressed CSV: {filepath}...")
            df.to_csv(filepath, index=False, compression="gzip")
            
        file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
        print(f"Successfully exported to {filepath}! File size: {file_size_mb:.2f} MB")
            
    except Exception as e:
        print(f"Failed to export {table_name}: {e}")
        if "pyarrow" in str(e) or "fastparquet" in str(e):
            print("\n[TIP]: To export to Parquet, run: pip install pyarrow")

def main():
    conn = get_connection()
    if not conn:
        print("Could not connect to database. Exiting.")
        return

    try:
        for table in TABLES:
            export_table(table, conn, EXPORT_FORMAT)
        print("\nAll exports completed successfully.")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    main()