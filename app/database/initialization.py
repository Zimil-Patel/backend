from app.database.connection import getConnection


def initializeDatabase():
    """
    Create all database tables required by the photo server.

    This function is responsible only for database structure.
    It does not handle projects, photos, faces, or clusters directly.
    """

    connection = getConnection()
    cursor = connection.cursor()

    # ---------------------------------------------------------
    # PROJECTS
    # ---------------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS projects(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )

    # ---------------------------------------------------------
    # EVENTS
    # ---------------------------------------------------------

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

    # ---------------------------------------------------------
    # PHOTOS
    # ---------------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS photos(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_hash TEXT,
            width INTEGER,
            height INTEGER,
            thumbnail_path TEXT,
            status TEXT NOT NULL,
            is_favourite INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,

            FOREIGN KEY (event_id) REFERENCES events(id),

            UNIQUE(file_path)
        )
        """
    )

    # ---------------------------------------------------------
    # EXISTING PHOTOS TABLE MIGRATION
    #
    # SQLite does not modify an existing table when
    # CREATE TABLE IF NOT EXISTS is used.
    #
    # Therefore we check whether thumbnail_path exists
    # and add it if necessary.
    # ---------------------------------------------------------

    cursor.execute(
        """
        PRAGMA table_info(photos)
        """
    )

    photo_columns = [
        row[1]
        for row in cursor.fetchall()
    ]

    if "thumbnail_path" not in photo_columns:

        cursor.execute(
            """
            ALTER TABLE photos
            ADD COLUMN thumbnail_path TEXT
            """
        )

        print("Added thumbnail_path column to photos table")

    # ---------------------------------------------------------
    # FACES
    # ---------------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS faces(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    # EXISTING FACES TABLE MIGRATION
    # ---------------------------------------------------------

    cursor.execute(
        """
        PRAGMA table_info(faces)
        """
    )

    face_columns = [
        row[1]
        for row in cursor.fetchall()
    ]

    if "thumbnail_path" not in face_columns:

        cursor.execute(
            """
            ALTER TABLE faces
            ADD COLUMN thumbnail_path TEXT
            """
        )

        print("Added thumbnail_path column to faces table")

    # ---------------------------------------------------------
    # FACE CLUSTERS
    # ---------------------------------------------------------

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

    # ---------------------------------------------------------
    # FACE CLUSTER MEMBERS
    # ---------------------------------------------------------

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

    cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,

        firebase_uid TEXT NOT NULL UNIQUE,

        first_name TEXT,
        last_name TEXT,

        email TEXT NOT NULL UNIQUE,

        email_verified INTEGER NOT NULL DEFAULT 0,

        mobile_number TEXT,

        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """
    )

    # Save all table changes.
    connection.commit()

    # Close the database connection.
    connection.close()

    print("Database initialized")