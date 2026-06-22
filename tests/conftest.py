import os
import sys

# Required env for the app/config to import during tests.
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-pytest-only-not-real")
os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")
os.environ.setdefault("MONGO_DB", "tatpas_test")

# Make the backend package importable when running pytest from backend/.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
