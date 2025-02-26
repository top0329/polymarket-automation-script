import os
import json
import time
import requests

from datetime import datetime
from typing import Dict, List
from pymongo import MongoClient
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from datetime import datetime

load_dotenv()

# Configuration
class Config:
    MONGO_URI = os.getenv('MONGODB_URI')
    GAMMA_ENDPOINT = os.getenv('GAMMA_ENDPOINT')
    CLOB_HTTP_URL = os.getenv('CLOB_HTTP_URL')
    PRIVATE_KEY = os.getenv('PRIVATE_KEY')
    CHAIN_ID = 137
    BATCH_SIZE = 500

# MongoDB Schema Definitions
class MongoSchema:
    MARKET_SCHEMA = {
        "enable_order_book": bool,
        "active": bool,
        "closed": bool,
        "archived": bool,
        "accepting_orders": bool,
        "accepting_order_timestamp": datetime,
        "minimum_order_size": float,
        "minimum_tick_size": float,
        "condition_id": str,
        "question_id": str,
        "question": str,
        "description": str,
        "market_slug": str,
        "end_date_iso": datetime,
        "game_start_time": datetime,
        "seconds_delay": int,
        "fpmm": str,
        "maker_base_fee": float,
        "taker_base_fee": float,
        "notifications_enabled": bool,
        "neg_risk": bool,
        "neg_risk_market_id": str,
        "neg_risk_request_id": str,
        "icon": str,
        "image": str,
        "rewards": {
            "rates": List[float],
            "min_size": float,
            "max_spread": float
        },
        "is_50_50_outcome": bool,
        "tokens": [{
            "token_id": str,
            "outcome": str,
            "price": float,
            "winner": bool
        }],
        "tags": List[str]
    }

    @classmethod
    def validate_market(cls, market_data: dict) -> bool:
        required_fields = ["question", "market_slug"]
        return all(field in market_data for field in required_fields)


# MongoDB Handler
class MongoDBHandler:
    def __init__(self):
        self.client = self._connect()
        if self.client:
            self.db = self.client['polymarket']
            self.markets_collection = self.db['markets']
            self._create_indexes()

    def _connect(self):
        try:
            client = MongoClient(Config.MONGO_URI)
            client.admin.command('ismaster')
            print("MongoDB connection successful")
            return client
        except Exception as e:
            print(f"MongoDB connection failed: {e}")
            return None

    def _create_indexes(self):
        self.markets_collection.create_index("market_slug", unique=True)
        print("MongoDB indexes created successfully")

    def save_markets(self, markets_data: List[Dict]):
        if not self.client:
            print("MongoDB connection not available")
            return

        try:
            for market in markets_data:
                if MongoSchema.validate_market(market):
                    self.markets_collection.update_one(
                        {'market_slug': market['market_slug']},
                        {'$set': market},
                        upsert=True
                    )
                else:
                    print(f"Skipping market with invalid data: {market}")
            print(f"Successfully saved {len(markets_data)} markets to MongoDB")
        except Exception as e:
            print(f"Error saving markets to MongoDB: {e}")
            if markets_data:
                print(f"Sample market data: {markets_data[0]}")

# Market Handler
class MarketHandler:
    def __init__(self, mongo_handler: MongoDBHandler):
        self.mongo_handler = mongo_handler
        self.clob_client = ClobClient(Config.CLOB_HTTP_URL, key=Config.PRIVATE_KEY, chain_id=Config.CHAIN_ID)

    def fetch_markets(self) -> List[Dict]:
        all_markets = []
        next_cursor = ""

        while True:
            try:
                response = self.clob_client.get_markets(next_cursor=next_cursor)
                parsed_response = json.loads(json.dumps(response))

                all_markets.extend(parsed_response["data"])

                next_cursor = parsed_response["next_cursor"]
                print(f"Next cursor: {next_cursor}")

                if next_cursor == "LTE=":
                    break

            except (ConnectionError, TimeoutError):
                print("Network connectivity issue. Retrying in 60 seconds...")
                time.sleep(60)
                continue
            except Exception as e:
                print(f"Error fetching markets: {e}. Retrying in 120 seconds...")
                time.sleep(120)
                continue

        return all_markets

    def initialize(self):
        markets = self.fetch_markets()
        self.mongo_handler.save_markets(markets)
        print(f"Total markets processed: {len(markets)}")
        print("Market initialization complete!")

# Market Monitor
class MarketMonitor:
    def __init__(self, mongo_handler: MongoDBHandler, market_handler: MarketHandler):
        self.mongo_handler = mongo_handler
        self.market_handler = market_handler
        self.monitoring_interval = 60  # 1 minute in seconds

    def initialize_if_needed(self):
        # Check if initialization is needed for markets
        existing_markets_count = self.mongo_handler.markets_collection.count_documents({})
        if existing_markets_count == 0:
            print("First run detected for markets. Performing initial market sync...")
            self.market_handler.initialize()
        else:
            print(f"Database already contains {existing_markets_count} markets. Skipping market initialization.")

    def get_latest_markets(self) -> List[Dict]:
        # Get all existing market slugs from MongoDB
        existing_market_slugs = set(
            doc['market_slug'] for doc in
            self.mongo_handler.markets_collection.find({}, {'market_slug': 1})
        )

        # Fetch all markets from the API
        all_markets = self.market_handler.fetch_markets()

        # Filter out markets that don't exist in MongoDB
        new_markets = [
            market for market in all_markets
            if market.get('market_slug') and market['market_slug'] not in existing_market_slugs
        ]

        print(f"Found {len(new_markets)} new markets out of {len(all_markets)} total markets")
        return new_markets

    def process_new_markets(self, markets: List[Dict]):
        if markets:
            print(f"Found {len(markets)} new markets")
            market_slugs = [market['market_slug'] for market in markets if 'market_slug' in market]
            print(f"Market slugs to be saved: {market_slugs}")

            self.mongo_handler.save_markets(markets)

            saved_count = self.mongo_handler.markets_collection.count_documents({
                'market_slug': {'$in': market_slugs}
            })

            if saved_count != len(market_slugs):
                missing_slugs = [
                    slug for slug in market_slugs
                    if not self.mongo_handler.markets_collection.find_one({'market_slug': slug})
                ]
                print(f"Missing markets with slugs: {missing_slugs}")
            print("New markets saved to MongoDB")
        else:
            print("No new markets found")

    def start_monitoring(self):
        print("Starting event and market monitoring...")
        consecutive_failures = 0
        max_consecutive_failures = 5
        base_retry_interval = 60

        while True:
            try:
                latest_markets = self.get_latest_markets()
                self.process_new_markets(latest_markets)

                # Reset failure counter on successful execution
                consecutive_failures = 0
                time.sleep(self.monitoring_interval)
            except requests.exceptions.ConnectionError:
                consecutive_failures += 1
                retry_interval = base_retry_interval * (2 ** consecutive_failures)
                print(f"Network connectivity issue. Retrying in {retry_interval} seconds...")
                time.sleep(retry_interval)

            except Exception as e:
                consecutive_failures += 1
                retry_interval = base_retry_interval * (2 ** consecutive_failures)
                print(f"Error during monitoring: {e}")
                print(f"Retrying in {retry_interval} seconds...")
                time.sleep(retry_interval)

                # If too many consecutive failures, raise an alert
                if consecutive_failures >= max_consecutive_failures:
                    print("CRITICAL: Maximum consecutive failures reached. Manual intervention may be required.")
                    # Here you could add additional alerting logic (email, Slack, etc.)
                    consecutive_failures = 0  # Reset counter and continue trying

# Main execution
def main():
    mongo_handler = MongoDBHandler()
    market_handler = MarketHandler(mongo_handler)
    monitor = MarketMonitor(mongo_handler, market_handler)

    # Initialize if needed
    monitor.initialize_if_needed()

    # Start continuous monitoring
    monitor.start_monitoring()

if __name__ == "__main__":
    main()
