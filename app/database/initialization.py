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

    # ---------------------------------------------------------
    # USERS
    # ---------------------------------------------------------


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

    cursor.execute("PRAGMA table_info(users)")
    user_columns = {
        row[1] for row in cursor.fetchall()
    }

    if "is_admin" not in user_columns:
        cursor.execute(
            """
            ALTER TABLE users
            ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0
            """
        )


    # ---------------------------------------------------------
    # GALLERIES
    # ---------------------------------------------------------
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS client_galleries(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL UNIQUE,
            share_token TEXT NOT NULL UNIQUE,
            is_enabled INTEGER NOT NULL DEFAULT 1,
            created_by_user_id INTEGER,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (project_id) 
                REFERENCES projects(id)
                ON DELETE CASCADE
        )"""
    )


    # ---------------------------------------------------------
    # GALLERY MENBERS
    # ---------------------------------------------------------
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS client_gallery_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gallery_id INTEGER NOT NULL,
            email TEXT NOT NULL COLLATE NOCASE,
            user_id INTEGER,
            role TEXT NOT NULL DEFAULT 'viewer'
                CHECK (role IN ('owner', 'viewer')),
            invited_by_user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE (gallery_id, email),

            FOREIGN KEY (user_id)
                REFERENCES users(id)
                ON DELETE SET NULL,

            FOREIGN KEY (invited_by_user_id)
                REFERENCES users(id)
                ON DELETE RESTRICT
        )"""
    )

    
    # ---------------------------------------------------------
    # GALLERY SHARING AND NOTIFICATIONS
    # ---------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gallery_share_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gallery_id INTEGER NOT NULL,
            token TEXT NOT NULL UNIQUE,
            created_by_user_id INTEGER NOT NULL,
            expires_at_utc TEXT NOT NULL,
            revoked_at_utc TEXT,
            created_at_utc TEXT NOT NULL,

            FOREIGN KEY (gallery_id)
                REFERENCES client_galleries(id)
                ON DELETE CASCADE,

            FOREIGN KEY (created_by_user_id)
                REFERENCES users(id)
                ON DELETE RESTRICT
        )
    """)


    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gallery_access_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            share_link_id INTEGER NOT NULL,
            gallery_id INTEGER NOT NULL,
            requester_user_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending'
                CHECK (status IN (
                    'pending', 'approved', 'rejected'
                )),
            created_at_utc TEXT NOT NULL,
            resolved_at_utc TEXT,
            resolved_by_user_id INTEGER,

            FOREIGN KEY (share_link_id)
                REFERENCES gallery_share_links(id)
                ON DELETE CASCADE,

            FOREIGN KEY (gallery_id)
                REFERENCES client_galleries(id)
                ON DELETE CASCADE,

            FOREIGN KEY (requester_user_id)
                REFERENCES users(id)
                ON DELETE CASCADE,

            FOREIGN KEY (resolved_by_user_id)
                REFERENCES users(id)
                ON DELETE SET NULL
        )
    """)

    # One pending request per user per gallery.
    # Repeated requests should return the existing pending request.
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS
            uq_pending_gallery_access_request
        ON gallery_access_requests (
            gallery_id,
            requester_user_id
        )
        WHERE status = 'pending'
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gallery_invitations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gallery_id INTEGER NOT NULL,
            email TEXT NOT NULL COLLATE NOCASE,
            role TEXT NOT NULL
                CHECK (role IN ('owner', 'viewer')),
            invited_by_user_id INTEGER NOT NULL,
            invited_user_id INTEGER,
            status TEXT NOT NULL DEFAULT 'pending'
                CHECK (status IN (
                    'pending', 'accepted', 'revoked'
                )),
            created_at_utc TEXT NOT NULL,
            updated_at_utc TEXT NOT NULL,

            UNIQUE (gallery_id, email),

            FOREIGN KEY (gallery_id)
                REFERENCES client_galleries(id)
                ON DELETE CASCADE,

            FOREIGN KEY (invited_by_user_id)
                REFERENCES users(id)
                ON DELETE RESTRICT,

            FOREIGN KEY (invited_user_id)
                REFERENCES users(id)
                ON DELETE SET NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS device_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT NOT NULL UNIQUE,
            platform TEXT,
            created_at_utc TEXT NOT NULL,
            updated_at_utc TEXT NOT NULL,

            FOREIGN KEY (user_id)
                REFERENCES users(id)
                ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            notification_type TEXT NOT NULL,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            data_json TEXT,
            created_at_utc TEXT NOT NULL,
            read_at_utc TEXT,

            FOREIGN KEY (user_id)
                REFERENCES users(id)
                ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS
            idx_gallery_access_requests_pending
        ON gallery_access_requests (
            gallery_id, status, created_at_utc
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS
            idx_user_notifications_unread
        ON user_notifications (
            user_id, read_at_utc, created_at_utc
        )
    """)

    # Persist all schema changes, including the photo_url migration.
    connection.commit()


    # Close the database connection.
    connection.close()

    print("Database initialized")