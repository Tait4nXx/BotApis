from pymongo import MongoClient
from datetime import datetime, timedelta
import os
import logging

logger = logging.getLogger(__name__)

class MongoCache:
    def __init__(self):
        self.mongo_uri = os.getenv('MONGODB_URI', 'mongodb+srv://VNI0X:iPIDqeYidbBQlZtG@vni0x.hykq8l4.mongodb.net/?retryWrites=true&w=majority&appName=VNI0X')
        self.db_name = os.getenv('MONGO_DB_NAME', 'taitanx_bot')
        self.client = None
        self.db = None
        self.connect()
    
    def connect(self):
        """Connect to MongoDB"""
        try:
            self.client = MongoClient(self.mongo_uri)
            self.db = self.client[self.db_name]
            # Create collections if they don't exist
            self.db.audio_cache.create_index("created_at", expireAfterSeconds=86400)  # 24 hours TTL
            self.db.video_cache.create_index("created_at", expireAfterSeconds=86400)  # 24 hours TTL
            logger.info("✅ Connected to MongoDB cache successfully")
        except Exception as e:
            logger.error(f"MongoDB cache connection error: {e}")
            self.client = None
            self.db = None
    
    def get_audio_cache(self, video_id):
        """Get cached audio response for video ID"""
        if not self.db:
            return None
        
        try:
            cache_entry = self.db.audio_cache.find_one({
                "video_id": video_id,
                "created_at": {"$gte": datetime.now() - timedelta(hours=23)}
            })
            return cache_entry.get('response') if cache_entry else None
        except Exception as e:
            logger.error(f"Error getting audio cache: {e}")
            return None
    
    def get_video_cache(self, video_id):
        """Get cached video response for video ID"""
        if not self.db:
            return None
        
        try:
            cache_entry = self.db.video_cache.find_one({
                "video_id": video_id,
                "created_at": {"$gte": datetime.now() - timedelta(hours=23)}
            })
            return cache_entry.get('response') if cache_entry else None
        except Exception as e:
            logger.error(f"Error getting video cache: {e}")
            return None
    
    def set_audio_cache(self, video_id, response):
        """Cache audio response for video ID"""
        if not self.db:
            return False
        
        try:
            self.db.audio_cache.update_one(
                {"video_id": video_id},
                {
                    "$set": {
                        "response": response,
                        "created_at": datetime.now(),
                        "title": response.get('result', {}).get('title', ''),
                        "duration": response.get('result', {}).get('duration', '')
                    }
                },
                upsert=True
            )
            logger.info(f"Audio cache set for video_id: {video_id}")
            return True
        except Exception as e:
            logger.error(f"Error setting audio cache: {e}")
            return False
    
    def set_video_cache(self, video_id, response):
        """Cache video response for video ID"""
        if not self.db:
            return False
        
        try:
            self.db.video_cache.update_one(
                {"video_id": video_id},
                {
                    "$set": {
                        "response": response,
                        "created_at": datetime.now(),
                        "title": response.get('result', {}).get('title', ''),
                        "duration": response.get('result', {}).get('duration', ''),
                        "quality": response.get('result', {}).get('quality', '')
                    }
                },
                upsert=True
            )
            logger.info(f"Video cache set for video_id: {video_id}")
            return True
        except Exception as e:
            logger.error(f"Error setting video cache: {e}")
            return False
    
    def delete_audio_cache(self, video_id):
        """Delete audio cache for video ID"""
        if not self.db:
            return False
        
        try:
            self.db.audio_cache.delete_one({"video_id": video_id})
            return True
        except Exception as e:
            logger.error(f"Error deleting audio cache: {e}")
            return False
    
    def delete_video_cache(self, video_id):
        """Delete video cache for video ID"""
        if not self.db:
            return False
        
        try:
            self.db.video_cache.delete_one({"video_id": video_id})
            return True
        except Exception as e:
            logger.error(f"Error deleting video cache: {e}")
            return False

# Global instance
cache_db = MongoCache()
