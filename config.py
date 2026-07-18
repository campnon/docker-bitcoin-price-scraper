import os

KALSHI_API_URL = "https://api.elections.kalshi.com/trade-api/v2"
KALSHI_DEMO_URL = "https://demo-api.kalshi.co/trade-api/v2"

# Kalshi API Credentials
#KALSHI_KEY_ID = os.getenv("KALSHI_KEY_ID", "56e345cd-d886-48a0-b75b-1035060d2508")
#KALSHI_PRIVATE_KEY_PATH = os.getenv("KALSHI_PRIVATE_KEY_PATH", "kalshi_key.pem")

# Database Credentials
DB_NAME = os.getenv("DB_NAME", "market_monitoring")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "secure_password")
# Correcting to standard port based on probe result
DB_HOST = "192.168.68.136"
DB_PORT = "5432" 
