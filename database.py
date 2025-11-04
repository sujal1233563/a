import pymongo
from datetime import datetime, timedelta
import pytz
import logging
from typing import Optional, Dict, List, Any
import os
import json
import asyncio
from config import ADMIN_IDS, MONGODB_URI

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('database')

# Constants
USERS_FILE = 'users.json'
SETTINGS_COLLECTION = "settings"
DEFAULT_NIRVANA_API = "https://ugxplayer.vercel.app"

# MongoDB connection
client = None
db = None
users_collection = None
settings_collection = None

def init_mongodb_sync():
    """Initialize MongoDB connection synchronously"""
    global client, db, users_collection, settings_collection
    try:
        client = pymongo.MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        # Test the connection
        client.server_info()
        db = client["subscription_bot"]
        users_collection = db["users"]
        settings_collection = db["settings"]
        
        # Create indexes if they don't exist
        users_collection.create_index("user_id", unique=True)
        users_collection.create_index("subscription_expiry")
        
        # Initialize default settings if they don't exist
        if not settings_collection.find_one({"setting": "nirvana_api"}):
            settings_collection.insert_one({
                "setting": "nirvana_api",
                "value": DEFAULT_NIRVANA_API,
                "last_updated": datetime.utcnow()
            })
        
        logger.info("Successfully connected to MongoDB")
        return True
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        global_cleanup()
        return False

def global_cleanup():
    """Cleanup global MongoDB resources"""
    global client, db, users_collection, settings_collection
    try:
        if client:
            client.close()
    except Exception as e:
        logger.error(f"Error during MongoDB cleanup: {e}")
    finally:
        client = None
        db = None
        users_collection = None
        settings_collection = None

# Initialize MongoDB at startup
try:
    init_mongodb_sync()
except Exception as e:
    logger.error(f"Failed to initialize MongoDB at startup: {e}")
    global_cleanup()

async def ensure_mongodb_connected():
    """Ensure MongoDB connection is active"""
    global client, db, users_collection, settings_collection
    try:
        if client is None or db is None or users_collection is None or settings_collection is None:
            return init_mongodb_sync()
        # Test the connection
        client.server_info()
        return True
    except Exception as e:
        logger.error(f"MongoDB connection check failed: {e}")
        global_cleanup()
        return init_mongodb_sync()

# File paths
CHATS_FILE = 'chats.json'

# Initialize files if they don't exist
def init_files():
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'w') as f:
            json.dump([], f)
    if not os.path.exists(CHATS_FILE):
        with open(CHATS_FILE, 'w') as f:
            json.dump({}, f)
    logger.info("JSON storage files initialized")

init_files()

def get_utc_now() -> datetime:
    """Get current UTC time"""
    return datetime.now(pytz.UTC)

async def is_user_authorized(user_id: int) -> bool:
    """Check if user is authorized and subscription is valid"""
    try:
        # First check admin status for immediate access
        if user_id in ADMIN_IDS:
            logger.info(f"User {user_id} authorized as admin")
            return True

        # Ensure MongoDB connection
        await ensure_mongodb_connected()

        # Check MongoDB
        if users_collection is not None:
            user = users_collection.find_one({"user_id": user_id})
            if user:
                expiry_date = user.get("subscription_expiry")
                if expiry_date:
                    is_valid = datetime.utcnow() <= expiry_date
                    logger.info(f"MongoDB: User {user_id} authorization status: {is_valid}")
                    return is_valid
            logger.info(f"User {user_id} not found in MongoDB")
            return False

        logger.warning("MongoDB not available")
        return False
        
    except Exception as e:
        logger.error(f"Error checking user authorization: {e}")
        return user_id in ADMIN_IDS  # Fallback to admin check on error

async def add_user(user_id: int, duration_days: int = 30) -> bool:
    """Add or update user subscription"""
    try:
        current_time = datetime.utcnow()
        expiry_date = current_time + timedelta(days=duration_days)
        
        # Ensure MongoDB connection
        await ensure_mongodb_connected()
        
        # Update MongoDB
        if users_collection is not None:
            result = users_collection.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "user_id": user_id,
                        "subscription_expiry": expiry_date,
                        "added_on": current_time,
                        "last_updated": current_time
                    }
                },
                upsert=True
            )
            success = result.acknowledged
            if success:
                logger.info(f"Successfully added/updated user {user_id} in MongoDB")
                return True
            else:
                logger.error(f"Failed to add/update user {user_id} in MongoDB")
                return False
        else:
            logger.error("MongoDB not available")
            return False
            
    except Exception as e:
        logger.error(f"Error adding/updating user: {e}")
        return False

async def get_subscription_status(user_id: int) -> Dict:
    """Get user's subscription details"""
    try:
        # Ensure MongoDB connection
        await ensure_mongodb_connected()
        
        if users_collection is not None:
            user = users_collection.find_one({"user_id": user_id})
            if user:
                expiry_date = user.get("subscription_expiry")
                if expiry_date:
                    current_time = datetime.utcnow()
                    days_left = (expiry_date - current_time).days
                    return {
                        "is_subscribed": days_left > 0,
                        "expiry_date": expiry_date,
                        "days_left": max(0, days_left)
                    }
        
        return {
            "is_subscribed": False,
            "expiry_date": None,
            "days_left": 0
        }
        
    except Exception as e:
        logger.error(f"Error getting subscription status: {e}")
        return {
            "is_subscribed": False,
            "expiry_date": None,
            "days_left": 0,
            "error": str(e)
        }

async def remove_user(user_id: int) -> bool:
    """Remove user from authorized users"""
    try:
        result = users_collection.delete_one({"user_id": user_id})
        success = result.deleted_count > 0
        if success:
            logger.info(f"Successfully removed user {user_id}")
        else:
            logger.warning(f"User {user_id} not found for removal")
        return success
        
    except Exception as e:
        logger.error(f"Error removing user: {e}")
        return False

async def get_all_users() -> List[Dict]:
    """Get list of all users with their subscription details"""
    try:
        # Ensure MongoDB connection
        await ensure_mongodb_connected()
        
        users = []
        if users_collection is not None:
            cursor = users_collection.find({})
            current_time = datetime.utcnow()
            
            for user in cursor:
                expiry_date = user.get("subscription_expiry")
                if expiry_date:
                    days_left = (expiry_date - current_time).days
                    users.append({
                        "user_id": user["user_id"],
                        "expiry_date": expiry_date,
                        "days_left": max(0, days_left),
                        "is_active": days_left > 0,
                        "added_on": user.get("added_on"),
                        "last_updated": user.get("last_updated")
                    })
        
        # Also check JSON backup
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r') as f:
                json_users = json.load(f)
                current_time = datetime.now(pytz.UTC)
                
                for user in json_users:
                    # Skip if user already added from MongoDB
                    if any(u["user_id"] == user["user_id"] for u in users):
                        continue
                        
                    expiry_date = datetime.fromisoformat(user.get('expiry_date'))
                    days_left = (expiry_date.replace(tzinfo=pytz.UTC) - current_time).days
                    users.append({
                        "user_id": user["user_id"],
                        "expiry_date": expiry_date,
                        "days_left": max(0, days_left),
                        "is_active": days_left > 0,
                        "source": "json_backup"
                    })
        
        # Sort by active status and days left
        users.sort(key=lambda x: (-x["is_active"], -x["days_left"]))
        return users
        
    except Exception as e:
        logger.error(f"Error getting all users: {e}")
        return []

# New functions for chat management
async def add_chat(user_id: int, chat_id: int) -> bool:
    """Add a chat to a user's authorized chats"""
    try:
        # Load existing chats
        chats_data = {}
        if os.path.exists(CHATS_FILE):
            with open(CHATS_FILE, 'r') as f:
                chats_data = json.load(f)
        
        # Convert user_id to string for JSON compatibility
        user_id_str = str(user_id)
        
        # Initialize user's chats list if not exists
        if user_id_str not in chats_data:
            chats_data[user_id_str] = []
            
        # Add chat if not already present
        if chat_id not in chats_data[user_id_str]:
            chats_data[user_id_str].append(chat_id)
            
            # Save updated chats
            with open(CHATS_FILE, 'w') as f:
                json.dump(chats_data, f, indent=2)
            
            logger.info(f"Successfully added chat {chat_id} for user {user_id}")
            return True
        else:
            logger.info(f"Chat {chat_id} already authorized for user {user_id}")
            return True
            
    except Exception as e:
        logger.error(f"Error adding chat: {e}")
        return False

async def remove_chat(user_id: int, chat_id: int) -> bool:
    """Remove a chat from a user's authorized chats"""
    try:
        if not os.path.exists(CHATS_FILE):
            logger.error("Chats file does not exist")
            return False
            
        with open(CHATS_FILE, 'r') as f:
            chats_data = json.load(f)
        
        user_id_str = str(user_id)
        if user_id_str in chats_data and chat_id in chats_data[user_id_str]:
            chats_data[user_id_str].remove(chat_id)
            
            with open(CHATS_FILE, 'w') as f:
                json.dump(chats_data, f, indent=2)
            
            logger.info(f"Successfully removed chat {chat_id} for user {user_id}")
            return True
        else:
            logger.info(f"Chat {chat_id} not found for user {user_id}")
            return False
            
    except Exception as e:
        logger.error(f"Error removing chat: {e}")
        return False

async def get_user_chats(user_id: Optional[int] = None) -> List[int]:
    """Get all chats authorized for a user or all chats if user_id is None"""
    try:
        if not os.path.exists(CHATS_FILE):
            return []
            
        with open(CHATS_FILE, 'r') as f:
            chats_data = json.load(f)
        
        if user_id is not None:
            # Return chats for specific user
            user_id_str = str(user_id)
            return chats_data.get(user_id_str, [])
        else:
            # Return all unique chats
            all_chats = set()
            for user_chats in chats_data.values():
                all_chats.update(user_chats)
            return list(all_chats)
            
    except Exception as e:
        logger.error(f"Error getting user chats: {e}")
        return []

async def is_chat_authorized(chat_id: int) -> bool:
    """Check if a chat is authorized"""
    try:
        logger.info(f"Checking authorization for chat ID: {chat_id}")
        
        # Check JSON file
        if os.path.exists(CHATS_FILE):
            with open(CHATS_FILE, 'r') as f:
                chats_data = json.load(f)
                logger.info(f"Loaded chats data: {chats_data}")
                
                # Check all users' authorized chats
                for user_id, user_chats in chats_data.items():
                    logger.info(f"Checking user {user_id}'s chats: {user_chats}")
                    # Convert both chat IDs to int for comparison
                    if int(chat_id) in [int(x) for x in user_chats]:
                        logger.info(f"Chat {chat_id} found in authorized chats for user {user_id}")
                        return True
        else:
            logger.warning(f"Chats file not found at {CHATS_FILE}")
        
        logger.info(f"Chat {chat_id} not found in any authorized chats")
        return False
            
    except Exception as e:
        logger.error(f"Error checking chat authorization: {e}")
        return False

async def diagnose_authorization(user_id: int) -> Dict:
    """Diagnose authorization status for a user by checking all sources"""
    result = {
        "user_id": user_id,
        "mongodb_status": None,
        "json_status": None,
        "is_admin": False,
        "overall_authorized": False,
        "error": None
    }
    
    try:
        # Check MongoDB
        user = users_collection.find_one({"user_id": user_id})
        if user:
            expiry_date = user.get("subscription_expiry")
            if expiry_date:
                is_valid = get_utc_now() <= expiry_date.replace(tzinfo=pytz.UTC)
                result["mongodb_status"] = {
                    "found": True,
                    "expiry_date": expiry_date.isoformat(),
                    "is_valid": is_valid
                }
        else:
            result["mongodb_status"] = {"found": False}

        # Check JSON file
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r') as f:
                users = json.load(f)
                for user_data in users:
                    if user_data.get('user_id') == user_id:
                        try:
                            expiry_date = datetime.fromisoformat(user_data.get('expiry_date'))
                            is_valid = datetime.now(pytz.UTC) <= expiry_date.replace(tzinfo=pytz.UTC)
                            result["json_status"] = {
                                "found": True,
                                "expiry_date": user_data.get('expiry_date'),
                                "is_valid": is_valid
                            }
                            break
                        except (ValueError, TypeError) as e:
                            result["json_status"] = {
                                "found": True,
                                "error": str(e)
                            }
                else:
                    result["json_status"] = {"found": False}
        else:
            result["json_status"] = {"file_exists": False}

        # Check admin status
        result["is_admin"] = user_id in ADMIN_IDS
        
        # Determine overall authorization
        result["overall_authorized"] = (
            (result["mongodb_status"] and result["mongodb_status"].get("is_valid", False)) or
            (result["json_status"] and result["json_status"].get("is_valid", False)) or
            result["is_admin"]
        )
        
    except Exception as e:
        result["error"] = str(e)
        logger.error(f"Error in authorization diagnosis for user {user_id}: {e}")
    
    return result 

async def test_mongodb_connection() -> Dict[str, Any]:
    """Test MongoDB connection and return detailed status"""
    global client, db, users_collection
    result = {
        "mongodb_available": False,
        "client_connected": False,
        "db_accessible": False,
        "collection_writable": False,
        "error": None
    }
    
    try:
        # Check if MongoDB is available
        if client is None:
            result["error"] = "MongoDB client not initialized"
            return result
        
        result["mongodb_available"] = True
        
        # Test connection
        client.admin.command('ping')
        result["client_connected"] = True
        
        # Test database access
        db_names = client.list_database_names()
        result["db_accessible"] = True
        
        # Test collection write
        test_doc = {"_id": "test", "timestamp": datetime.utcnow()}
        test_result = users_collection.insert_one(test_doc)
        if test_result.inserted_id:
            result["collection_writable"] = True
            users_collection.delete_one({"_id": test_result.inserted_id})
        
    except pymongo.errors.ConnectionFailure as e:
        result["error"] = f"Connection failure: {str(e)}"
    except pymongo.errors.OperationFailure as e:
        result["error"] = f"Operation failure: {str(e)}"
    except Exception as e:
        result["error"] = f"Unexpected error: {str(e)}"
    
    return result

async def reconnect_mongodb() -> bool:
    """Attempt to reconnect to MongoDB"""
    global client
    try:
        if client:
            client.close()
        return await init_mongodb_sync()
    except Exception as e:
        logger.error(f"MongoDB reconnection failed: {str(e)}")
        return False 

async def get_nirvana_api() -> str:
    """Get the current Nirvana player API URL"""
    try:
        # Ensure MongoDB connection
        await ensure_mongodb_connected()
        
        if settings_collection is not None:
            setting = settings_collection.find_one({"setting": "nirvana_api"})
            if setting:
                return setting["value"]
        
        return DEFAULT_NIRVANA_API
        
    except Exception as e:
        logger.error(f"Error getting Nirvana API URL: {e}")
        return DEFAULT_NIRVANA_API

async def update_nirvana_api(new_url: str) -> bool:
    """Update the Nirvana player API URL"""
    try:
        # Ensure MongoDB connection
        await ensure_mongodb_connected()
        
        if settings_collection is not None:
            result = settings_collection.update_one(
                {"setting": "nirvana_api"},
                {
                    "$set": {
                        "value": new_url,
                        "last_updated": datetime.utcnow()
                    }
                },
                upsert=True
            )
            success = result.acknowledged
            if success:
                logger.info(f"Successfully updated Nirvana API URL to: {new_url}")
                return True
            else:
                logger.error("Failed to update Nirvana API URL")
                return False
        else:
            logger.error("MongoDB not available")
            return False
            
    except Exception as e:
        logger.error(f"Error updating Nirvana API URL: {e}")
        return False 