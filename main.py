import websocket
import _thread
import time
import json
import base64
import sys
import os
import psycopg2
from datetime import datetime

# Configuration
WS_URL = "wss://www.cfbenchmarks.com/ws/v4"
# Credentials from webpull.py
USERNAME = os.getenv("WS_USERNAME", "cfbenchmarksws2")
PASSWORD = os.getenv("WS_PASSWORD", "e3709a02-9876-45ea-ac46-e9020e06d7c6")

# Environment Variables
TARGET_URL = os.getenv("TARGET_URL")
MARKET_ID = os.getenv("MARKET_ID")
TABLE_NAME = os.getenv("TABLE_NAME")

# Database Connection Details
DB_CONFIG = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST")
}

# Aggregation Configuration
RUN_AGGREGATION = os.getenv("RUN_AGGREGATION", "false").lower() == "true"
AGGREGATION_FUNCTION = os.getenv("AGGREGATION_FUNCTION", "update_ohlc_from_brti()")

last_agg_time = time.time()

def get_auth_header(username, password):
    credentials = f"{username}:{password}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    return [f"Authorization: Basic {encoded_credentials}"]

def save_to_db(timestamp, price):
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        query = f"INSERT INTO {TABLE_NAME} (time_raw, price) VALUES (%s, %s) ON CONFLICT (time_raw) DO NOTHING"
        cur.execute(query, (timestamp, price))
        conn.commit()
        cur.close()
        conn.close()
        # print(f"Saved to DB: {price} at {timestamp}")
    except Exception as e:
        print(f"DB Error: {e}")

def update_aggregates():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute(f"SELECT {AGGREGATION_FUNCTION};")
        conn.commit()
        cur.close()
        conn.close()
        print(f"Aggregated OHLC data using {AGGREGATION_FUNCTION}.")
    except Exception as e:
        print(f"Aggregation Error: {e}")

def on_message(ws, message):
    global last_agg_time
    # print(f"Received: {message}")
    try:
        data = json.loads(message)
        # Check if the message is a value update for our subscribed ID
        if data.get("type") == "value" and data.get("id") == MARKET_ID:
            price = data.get("value")
            # The API returns time in milliseconds, which matches our schema expectations
            timestamp = data.get("time")
            
            print(f"[{MARKET_ID}] Price: {price} Time: {timestamp}")
            save_to_db(timestamp, price)

            # Aggregate every 60 seconds if configured
            if RUN_AGGREGATION:
                if time.time() - last_agg_time > 60:
                    update_aggregates()
                    last_agg_time = time.time()

    except json.JSONDecodeError:
        print("Failed to decode JSON")
    except Exception as e:
        print(f"Error processing message: {e}")

def on_error(ws, error):
    print(f"WebSocket Error: {error}")

def on_close(ws, close_status_code, close_msg):
    print("### closed ###")
    print(f"Status: {close_status_code}, Msg: {close_msg}")

def on_open(ws):
    print("### opened ###")
    # Subscribe using the configured MARKET_ID
    subscribe_msg = {
        "type": "subscribe",
        "id": MARKET_ID,
        "stream": "value"
    }
    print(f"Sending subscription for {MARKET_ID}: {json.dumps(subscribe_msg)}")
    ws.send(json.dumps(subscribe_msg))

if __name__ == "__main__":
    # websocket.enableTrace(True) # Uncomment for debug
    
    headers = get_auth_header(USERNAME, PASSWORD)
    
    while True:
        print(f"Connecting to {WS_URL} for {MARKET_ID}...")
        try:
            ws = websocket.WebSocketApp(WS_URL,
                                        header=headers,
                                        on_open=on_open,
                                        on_message=on_message,
                                        on_error=on_error,
                                        on_close=on_close)
            
            # blocked call
            ws.run_forever(reconnect=5)
        except Exception as e:
            print(f"Main loop exception: {e}")
        
        print("Connection lost. Reconnecting in 5 seconds...")
        time.sleep(5)