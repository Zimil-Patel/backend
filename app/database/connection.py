import sqlite3
from pathlib import Path


# Find the backend folder.
# __file__ points to:
# app/database/connection.py
#
# parents[0] = app/database
# parents[1] = app
# parents[2] = backend
BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent


# Store the SQLite database inside backend/data/
DATABASE_DIR = BACKEND_ROOT / "data"

DATABASE_PATH = DATABASE_DIR / "photos.db"


# Create the data folder if it doesn't already exist.
DATABASE_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


def getConnection():
    """
    Create and return a connection to the SQLite database.
    """

    connection = sqlite3.connect(DATABASE_PATH)

    return connection