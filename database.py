from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
import os
from datetime import datetime, timedelta, date
import logging

logger = logging.getLogger(__name__)

# MongoDB connection
client = None
db = None

def init_db():
    """Initialize MongoDB connection"""
    global client, db
    try:
        mongodb_uri = os.getenv("MONGODB_URI", "mongodb+srv://VNI0X:iPIDqeYidbBQlZtG@vni0x.hykq8l4.mongodb.net/?retryWrites=true&w=majority&appName=VNI0X")
        client = MongoClient(mongodb_uri)
        db = client["taitanx_bot"]
        
        # Test connection
        client.admin.command('ping')
        logger.info("✅ Connected to MongoDB successfully!")
        
        # Create indexes
        db.users.create_index("user_id", unique=True)
        db.api_keys.create_index("key", unique=True)
        db.api_keys.create_index("expires_at", expireAfterSeconds=0)
        db.requests.create_index([("user_id", 1), ("date", 1)])
        
    except ConnectionFailure as e:
        logger.error(f"❌ MongoDB connection failed: {e}")
        raise

def get_db():
    """Get database instance"""
    if db is None:
        init_db()
    return db

class UserManager:
    @staticmethod
    def add_user(user_data):
        """Add or update user"""
        db = get_db()
        user_data["created_at"] = datetime.utcnow()
        db.users.update_one(
            {"user_id": user_data["user_id"]},
            {"$set": user_data},
            upsert=True
        )
    
    @staticmethod
    def get_user(user_id):
        """Get user by ID"""
        db = get_db()
        return db.users.find_one({"user_id": user_id})
    
    @staticmethod
    def get_all_users():
        """Get all users"""
        db = get_db()
        return list(db.users.find({}))
    
    @staticmethod
    def get_user_count():
        """Get total user count"""
        db = get_db()
        return db.users.count_documents({})

class KeyManager:
    @staticmethod
    def generate_key(user_id, is_admin=False):
        """Generate API key"""
        import secrets
        import random
        import string
        
        # Generate key in Taitan{Random} format
        random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
        key = f"Taitan{random_part}"
        
        db = get_db()
        
        if is_admin:
            expires_at = None  # Lifetime for admin
        else:
            expires_at = datetime.utcnow() + timedelta(days=7)
        
        key_data = {
            "key": key,
            "user_id": user_id,
            "is_admin": is_admin,
            "created_at": datetime.utcnow(),
            "expires_at": expires_at,
            "daily_requests": 0,
            "total_requests": 0,
            "last_reset": datetime.utcnow(),  # Store as datetime, not date
            "is_active": True
        }
        
        db.api_keys.insert_one(key_data)
        return key
    
    @staticmethod
    def validate_key(key):
        """Validate API key and check rate limits"""
        db = get_db()
        key_data = db.api_keys.find_one({"key": key, "is_active": True})
        
        if not key_data:
            return False, "Invalid API key"
        
        # Check expiration
        if key_data.get("expires_at") and key_data["expires_at"] < datetime.utcnow():
            db.api_keys.update_one({"key": key}, {"$set": {"is_active": False}})
            return False, "API key expired"
        
        # Reset daily counter if new day
        today = datetime.utcnow().date()
        last_reset_date = key_data["last_reset"].date() if isinstance(key_data["last_reset"], datetime) else key_data["last_reset"]
        
        if last_reset_date != today:
            db.api_keys.update_one(
                {"key": key}, 
                {"$set": {"daily_requests": 0, "last_reset": datetime.utcnow()}}
            )
            key_data["daily_requests"] = 0
        
        # Check daily limit (200 for normal users, unlimited for admin)
        if not key_data.get("is_admin") and key_data["daily_requests"] >= 200:
            return False, "Daily request limit exceeded"
        
        return True, key_data
    
    @staticmethod
    def increment_request(key):
        """Increment request counter"""
        db = get_db()
        db.api_keys.update_one(
            {"key": key},
            {
                "$inc": {"daily_requests": 1, "total_requests": 1},
                "$set": {"last_used": datetime.utcnow()}
            }
        )
    
    @staticmethod
    def get_all_keys():
        """Get all API keys"""
        db = get_db()
        return list(db.api_keys.find({}))
    
    @staticmethod
    def delete_key(key):
        """Delete API key"""
        db = get_db()
        result = db.api_keys.delete_one({"key": key})
        return result.deleted_count > 0
    
    @staticmethod
    def get_user_keys(user_id):
        """Get all keys for a user"""
        db = get_db()
        return list(db.api_keys.find({"user_id": user_id}))
    
    @staticmethod
    def add_key(key_data):
        """Add a key directly (for bot integration)"""
        db = get_db()
        key_data["created_at"] = datetime.utcnow()
        if key_data.get("expires_at") and isinstance(key_data["expires_at"], (int, float)):
            key_data["expires_at"] = datetime.utcfromtimestamp(key_data["expires_at"])
        db.api_keys.insert_one(key_data)

class RequestLogger:
    @staticmethod
    def log_request(user_id, endpoint, success=True):
        """Log API request"""
        db = get_db()
        db.requests.insert_one({
            "user_id": user_id,
            "endpoint": endpoint,
            "success": success,
            "timestamp": datetime.utcnow(),
            "date": datetime.utcnow()  # Store as datetime
        })
    
    @staticmethod
    def get_daily_stats():
        """Get today's statistics"""
        db = get_db()
        today = datetime.utcnow().date()
        start_of_day = datetime(today.year, today.month, today.day)
        
        total_requests = db.requests.count_documents({"date": {"$gte": start_of_day}})
        successful_requests = db.requests.count_documents({
            "date": {"$gte": start_of_day}, 
            "success": True
        })
        unique_users = len(db.requests.distinct("user_id", {"date": {"$gte": start_of_day}}))
        
        return {
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "unique_users": unique_users
        }
