"""
MongoDB database module for tracking posted games.
"""
from pymongo import MongoClient
from pymongo.errors import PyMongoError
import os
from datetime import datetime
from typing import List, Dict, Any, Optional

class MongoDBError(Exception):
    """Custom exception for MongoDB related errors."""
    pass

class MongoDB:
    """MongoDB wrapper for tracking posted games."""
    
    def __init__(self, connection_string: str = None, db_name: str = "epic_games"):
        """Initialize MongoDB connection.
        
        Args:
            connection_string: MongoDB connection string. If None, will try to get from MONGODB_URI env var.
            db_name: Database name to use.
        """
        self.connection_string = connection_string or os.getenv('MONGODB_URI')
        if not self.connection_string:
            raise MongoDBError("MongoDB connection string not provided and MONGODB_URI environment variable not set")
        
        try:
            self.client = MongoClient(self.connection_string, serverSelectionTimeoutMS=5000)
            # Test the connection
            self.client.server_info()
            self.db = self.client[db_name]
            self.posted_games = self.db.posted_games
            # Create index on game_id for faster lookups
            self.posted_games.create_index('game_id', unique=True)
        except Exception as e:
            raise MongoDBError(f"Failed to connect to MongoDB: {str(e)}")
    
    def is_game_posted(self, game_id: str, valid_until: str, service: str) -> bool:
        """Check if a game has been posted for a specific promotion period.
        
        Args:
            game_id: The unique identifier of the game.
            valid_until: The promotion end time (ISO8601 string).
            service: The service to check (e.g., 'discord').
        Returns:
            bool: True if the game has been posted for this promotion period, False otherwise.
        """
        try:
            return bool(self.posted_games.find_one({"game_id": game_id, "valid_until": valid_until, "service": service}))
        except PyMongoError as e:
            raise MongoDBError(f"Error checking if game is posted: {str(e)}")
    
    def mark_game_as_posted(self, game_id: str, title: str, valid_until: str, service: str) -> None:
        """Mark a game as posted for a specific promotion period.
        
        Args:
            game_id: The unique identifier of the game.
            title: The title of the game.
            valid_until: The promotion end time (ISO8601 string).
            service: The service where the game was posted (e.g., 'discord').
        """
        try:
            self.posted_games.update_one(
                {"game_id": game_id, "valid_until": valid_until, "service": service},
                {
                    "$set": {
                        "title": title,
                        "service": service,
                        "valid_until": valid_until,
                        "posted_at": datetime.utcnow(),
                        "last_updated": datetime.utcnow()
                    },
                    "$setOnInsert": {
                        "first_posted": datetime.utcnow()
                    }
                },
                upsert=True
            )
        except PyMongoError as e:
            raise MongoDBError(f"Error marking game as posted: {str(e)}")
    
    def close(self):
        """Close the MongoDB connection."""
        self.client.close()

# Singleton instance
db = None
try:
    db = MongoDB()
except MongoDBError as e:
    print(f"Warning: {str(e)}")
    db = None
