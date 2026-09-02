import os
import sys
from pathlib import Path

# backend.server reads MONGO_URL at import time; a value must exist before the
# module is imported. Nothing here connects to MongoDB.
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
