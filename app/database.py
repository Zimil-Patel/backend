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


    # cursor.execute(
    #     '''
    #         CREATE TABLE IF NOT EXISTS galleries(
    #             id INTEGER PRIMARY KEY AUTOINCREMENT,
                
    #         )
    #     '''
    # )

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

    # create faces table
    cursor.execute(
        """
            CREATE TABLE IF NOT EXISTS faces(
                id INTEGER  PRIMARY KEY AUTOINCREMENT,
                photo_id INTEGER NOT NULL,
                face_index INTEGER NOT NULL,
                bbox TEXT NOT NULL,
                detection_score REAL NOT NULL,
                embedding BLOB NOT NULL,
                created_at TEXT NOT NULL,
                thumbnail_path TEXT,

                FOREIGN KEY (photo_id) REFERENCES photos(id),

                UNIQUE(photo_id, face_index)
            )
        """
    )

    # ---------------------------------------------------------
    # ADD THUMBNAIL PATH TO EXISTING FACES TABLE
    # ---------------------------------------------------------
    #
    # This is needed because our faces table may already exist
    # from earlier development.
    #
    # SQLite will not add a new column automatically when using
    # CREATE TABLE IF NOT EXISTS.

    cursor.execute(
        """
        PRAGMA table_info(faces)
        """
    )

    face_columns = [row[1] for row in cursor.fetchall()]

    # Add thumbnail_path only if it doesn't already exist.
    if "thumbnail_path" not in face_columns:
        cursor.execute(
            """
            ALTER TABLE faces
            ADD COLUMN thumbnail_path TEXT
            """
        )

        print("Added thumbnail_path column to faces table")

    # create face cluster
    cursor.execute(
        """
            CREATE TABLE IF NOT EXISTS face_clusters(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                representative_embedding BLOB NOT NULL,
                face_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """
    )

    # create face cluster members table
    cursor.execute(
        """
            CREATE TABLE IF NOT EXISTS face_cluster_members(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                face_id INTEGER NOT NULL UNIQUE,
                cluster_id INTEGER NOT NULL,
                similarity REAL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (face_id) REFERENCES faces(id),
                FOREIGN KEY (cluster_id) REFERENCES face_clusters(id),
                UNIQUE(face_id, cluster_id)
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


# save face
def saveFace(
    photo_id: int, face_index: int, bbox: str, detection_score: float, embedding: bytes
):

    connection = getConnection()

    cursor = connection.cursor()

    created_at = datetime.now().isoformat()

    try:
        cursor.execute(
            """
            INSERT INTO faces(
                photo_id,
                face_index,
                bbox,
                detection_score,
                embedding,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                photo_id,
                face_index,
                bbox,
                detection_score,
                embedding,
                created_at,
            ),
        )

        connection.commit()

        face_id = cursor.lastrowid

        print(f"Saved face {face_index} for photo {photo_id}, Face ID: {face_id}")

        return face_id

    except sqlite3.IntegrityError:
        print(f"Face {face_index} already exists for photo {photo_id}")

        return None
    finally:
        connection.close()


def deleteFacesForPhoto(photo_id: int):

    connection = getConnection()

    cursor = connection.cursor()

    cursor.execute(
        """
        DELETE FROM faces
        WHERE photo_id = ?
        """,
        (photo_id,),
    )

    connection.commit()

    connection.close()

    print(f"Deleted old face records for photo {photo_id}")


# get all faces in face cluster table
def getAllFacesClusters():

    connection = getConnection()
    cursor = connection.cursor()

    cursor.execute(
        """
            SELECT id, representative_embedding, face_count FROM face_clusters ORDER BY id
        """
    )

    rows = cursor.fetchall()

    connection.close()

    return rows


# create new face cluster
def createFaceCluster(embedding: bytes):

    connection = getConnection()

    cursor = connection.cursor()

    created_at = datetime.now().isoformat()

    cursor.execute(
        """
            INSERT INTO face_clusters(representative_embedding, face_count, created_at, updated_at) VALUES (?, ?, ? ,?)
        """,
        (embedding, 0, created_at, created_at),
    )

    connection.commit()

    cluster_id = cursor.lastrowid

    connection.close()

    print(f"Created face cluster: {cluster_id}")

    return cluster_id


# add member faces to cluster
def addFaceToCluster(face_id: int, cluster_id: int, similarity: float | None = None):

    connection = getConnection()

    cursor = connection.cursor()

    created_at = datetime.now().isoformat()

    cursor.execute(
        """
            INSERT INTO face_cluster_members(face_id, cluster_id, similarity, created_at) VALUES (?,?,?,?)
        """,
        (face_id, cluster_id, similarity, created_at),
    )

    cursor.execute(
        """
            UPDATE face_clusters SET face_count = face_count + 1, updated_at = ? WHERE id = ?
        """,
        (created_at, cluster_id),
    )

    connection.commit()

    connection.close()


def updateFaceThumbnailPath(face_id: int, thumbnail_path: str):

    connection = getConnection()

    cursor = connection.cursor()

    cursor.execute(
        """
            UPDATE faces
            SET thumbnail_path = ?
            WHERE id = ?
        """,
        (
            thumbnail_path,
            face_id,
        ),
    )

    connection.commit()

    connection.close()

    print(f"Thumbnail path saved for Face {face_id}")
