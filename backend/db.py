"""MongoDB client and database handle.

This lives apart from server.py so that feature modules can reach the database
without importing the application module, which would be circular.
"""
import os

from pymongo import AsyncMongoClient

from backend import config  # noqa: F401  imported so .env is loaded before MONGO_URL is read

mongo_url = os.environ["MONGO_URL"]
client = AsyncMongoClient(mongo_url)
db = client[os.environ.get("DB_NAME", "audioraq")]
