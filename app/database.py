import hashlib
import sqlite3
from datetime import datetime
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent

DATABASE_DIR = BACKEND_ROOT / "data"

DATABASE_PATH = DATABASE_DIR / "photos.db"

# Create the database directory if it doesn't already exist.
#
# exist_ok=True means:
# "If the directory already exists, that's okay."
DATABASE_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# make connection
def getConnection():

    connection = sqlite3.connect(DATABASE_PATH)

    return connection


# initialize database and create all tables
def initializeDatabase():

    connection = getConnection()

    cursor = connection.cursor()

    # create project table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS projects(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )

    # create event table and give reference to project table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS events(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL,

            FOREIGN KEY (project_id) REFERENCES projects(id),
            UNIQUE(project_id, name)
        )
        """
    )

    # create photo table and give references to events
    cursor.execute(
        """
            CREATE TABLE IF NOT EXISTS photos(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                filename TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_hash TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,

                FOREIGN KEY (event_id) REFERENCES events(id),

                UNIQUE(file_path)
            )
        """
    )

    connection.commit()

    connection.close()

    print(f"Database initialized: {DATABASE_PATH}")


# crate project or get project
def getOrCreateProject(project_name: str):

    connection = getConnection()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT id FROM projects WHERE name = ?
        """,
        (project_name,),
    )

    row = cursor.fetchone()

    if row is not None:
        connection.close()
        return row[0]

    created_at = datetime.now().isoformat()

    cursor.execute(
        """
        INSERT INTO projects(name, created_at) VALUES (?, ?)
        """,
        (
            project_name,
            created_at,
        ),
    )

    connection.commit()

    project_id = cursor.lastrowid

    connection.close()

    print(f"Created project: {project_name}, ID: {project_id}")

    return project_id


# create event or get event
def getOrCreateEvent(project_id: int, event_name: str):

    connection = getConnection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT id FROM events WHERE name = ? AND project_id = ?
        """,
        (
            event_name,
            project_id,
        ),
    )

    row = cursor.fetchone()

    if row is not None:
        connection.close()
        return row[0]

    created_at = datetime.now().isoformat()

    cursor.execute(
        """
        INSERT INTO events (name, project_id, created_at) VALUES (?, ?, ?)
        """,
        (
            event_name,
            project_id,
            created_at,
        ),
    )

    connection.commit()

    event_id = cursor.lastrowid

    connection.close()

    print(f"Created event: {event_name}, ID: {event_id}")

    return event_id


def calculateFileHash(file_path: Path):

    sha256 = hashlib.sha256()

    # Open the image in binary mode.
    #
    # "rb" means:
    # r = read
    # b = binary
    #
    # Images are binary data, so we must use binary mode.

    with open(file_path, "rb") as file:
        while True:
            # read 1mb data
            chuck = file.read(1024 * 1024)

            if not chuck:
                break

            sha256.update(chuck)

    return sha256.hexdigest()


# check if hash already exists (photo already exists
def photoHashExists(file_hash: str):

    connection = getConnection()

    cursor = connection.cursor()

    cursor.execute(
        """
            SELECT id FROM photos WHERE file_hash = ? LIMIT 1
        """,
        (file_hash,),
    )

    row = cursor.fetchone()

    connection.close()

    return row is not None


# store photo
def createPhoto(
    event_id: str, filename: str, file_path: str, file_hash: str | None = None
):

    # check hash
    if photoHashExists(file_hash):
        print(f"Duplicate photo detected: {filename}")
        return None

    connection = getConnection()

    cursor = connection.cursor()

    created_at = datetime.now().isoformat()

    try:
        cursor.execute(
            """
            INSERT INTO photos(event_id, filename, file_path, file_hash, status, created_at) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                filename,
                file_path,
                file_hash,
                "READY",
                created_at,
            ),
        )

        connection.commit()

        photo_id = cursor.lastrowid

        print(f"Indexed photo: {filename} ID: {photo_id}")

        return photo_id

    except sqlite3.IntegrityError:
        print(f"Photo could not be inserted: {file_path}")

        return None

    finally:
        connection.close()


def updatePhotoStatus(photo_id: int, status: str):

    connection = getConnection()

    cursor = connection.cursor()

    cursor.execute(
        """
            UPDATE photos SET status = ? WHERE id = ?
        """,
        (status, photo_id),
    )

    connection.commit()

    connection.close()

    print(f"Photo {photo_id} status → {status}")
