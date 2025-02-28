from datetime import datetime
from typing import List, Optional
from pymongo import MongoClient
from bson import ObjectId
import logging

logger = logging.getLogger(__name__)

class OrderSchema:
    """MongoDB schema for orders"""

    def __init__(self):
        self.schema = {
            "user_id": int,  # Telegram user ID
            "market_id": str,
            "outcome": str,
            "token_id": str,
            "amount": float,
            "side": str,  # "BUY" or "SELL"
            "type": str,  # "market" or "limit"
            "price": Optional[float],  # Required for limit orders
            "status": str,  # "pending", "success", "failed"
            "order_id": Optional[str],
            "transaction_hashes": List[str],
            "error_message": Optional[str],
            "created_at": datetime,
            "updated_at": Optional[datetime]
        }

    def validate_order(self, order_data: dict) -> bool:
        """Validate order data against schema"""
        required_fields = [
            "user_id", "market_id", "outcome", "token_id",
            "amount", "side", "type", "status", "created_at"
        ]

        # Check required fields
        if not all(field in order_data for field in required_fields):
            return False

        # Validate field types
        try:
            assert isinstance(order_data["user_id"], int)
            assert isinstance(order_data["market_id"], str)
            assert isinstance(order_data["outcome"], str)
            assert isinstance(order_data["token_id"], str)
            assert isinstance(order_data["amount"], (int, float))
            assert order_data["side"] in ["BUY", "SELL"]
            assert order_data["type"] in ["market", "limit"]
            assert order_data["status"] in ["pending", "success", "failed"]
            assert isinstance(order_data["created_at"], datetime)

            # Validate price for limit orders
            if order_data["type"] == "limit":
                assert isinstance(order_data["price"], (int, float))
                assert 0 <= order_data["price"] <= 1

            # Validate optional fields if present
            if "transaction_hashes" in order_data:
                assert isinstance(order_data["transaction_hashes"], list)
                assert all(isinstance(hash, str) for hash in order_data["transaction_hashes"])

            if "updated_at" in order_data:
                assert isinstance(order_data["updated_at"], datetime)

            if "error_message" in order_data:
                assert isinstance(order_data["error_message"], str)

            return True

        except (AssertionError, KeyError):
            return False

class MongoDBHandler:
    """Handler for MongoDB operations"""

    def __init__(self, uri: str = "mongodb://localhost:27017"):
        try:
            self.client = MongoClient(uri)
            # Test the connection
            self.client.admin.command('ping')
            logger.info("✅ Successfully connected to MongoDB!")

            self.db = self.client.polymarket
            self.orders = self.db.orders
            self.order_schema = OrderSchema()

            # Create indexes
            self._create_indexes()
            logger.info("✅ MongoDB indexes created successfully!")

        except Exception as e:
            logger.error(f"❌ Failed to connect to MongoDB: {str(e)}")
            raise

    def _create_indexes(self):
        """Create necessary indexes for the orders collection"""
        try:
            self.orders.create_index([("user_id", 1)])
            self.orders.create_index([("market_id", 1)])
            self.orders.create_index([("created_at", -1)])
            self.orders.create_index([("status", 1)])
            logger.debug("Created MongoDB indexes for orders collection")
        except Exception as e:
            logger.error(f"Failed to create MongoDB indexes: {str(e)}")
            raise

    def save_order(self, order_data: dict) -> bool:
        """Save order to MongoDB"""
        try:
            if not self.order_schema.validate_order(order_data):
                logger.error("Invalid order data format")
                return False

            order_data["updated_at"] = datetime.utcnow()
            result = self.orders.insert_one(order_data)
            logger.info(f"Order saved successfully with ID: {result.inserted_id}")
            return bool(result.inserted_id)
        except Exception as e:
            logger.error(f"Failed to save order to MongoDB: {str(e)}")
            return False

    def update_order_status(self, order_id: str, status: str, error_message: str = None) -> bool:
        """Update order status"""
        try:
            update_data = {
                "status": status,
                "updated_at": datetime.utcnow()
            }
            if error_message:
                update_data["error_message"] = error_message

            result = self.orders.update_one(
                {"_id": ObjectId(order_id)},
                {"$set": update_data}
            )
            if result.modified_count > 0:
                logger.info(f"Order {order_id} status updated to: {status}")
            else:
                logger.warning(f"Order {order_id} not found or status not changed")
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Failed to update order status: {str(e)}")
            return False

    def get_user_orders(self, user_id: int, limit: int = 10) -> List[dict]:
        """Get user's orders sorted by creation date"""
        try:
            orders = list(
                self.orders.find({"user_id": user_id})
                .sort("created_at", -1)
                .limit(limit)
            )
            logger.info(f"Retrieved {len(orders)} orders for user {user_id}")
            return orders
        except Exception as e:
            logger.error(f"Failed to fetch user orders: {str(e)}")
            return []

    def get_market_orders(self, market_id: str, limit: int = 10) -> List[dict]:
        """Get orders for a specific market"""
        try:
            orders = list(
                self.orders.find({"market_id": market_id})
                .sort("created_at", -1)
                .limit(limit)
            )
            logger.info(f"Retrieved {len(orders)} orders for market {market_id}")
            return orders
        except Exception as e:
            logger.error(f"Failed to fetch market orders: {str(e)}")
            return []