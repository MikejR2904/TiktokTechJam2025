from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = "google_reviews_db"

client = MongoClient(MONGO_URI)
db = client[DB_NAME]

reviews_collection = db["reviews"]
users_collection = db["users"]
places_collection = db["places"]

print("Successfully connected to MongoDB.")
