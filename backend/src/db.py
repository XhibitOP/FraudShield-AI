import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()
print("DEBUG MONGODB_URI =", os.getenv("MONGODB_URI"))  # Check if it's loaded properly

def get_db():
    mongodb_uri = os.getenv("MONGODB_URI")
    if not mongodb_uri:
        raise Exception("MONGODB_URI not set in environment variables")

    client = MongoClient(mongodb_uri)
    db = client["transaction"]
    return db
