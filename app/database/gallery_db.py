import secrets
from datetime import datetime

from app.database.connection import getConnection


def generateGalleryToken() -> str:
    """
    Generate a unique token for a gallery.

    Example: /gallery/a8F2kLm9Pq...
    """

    return secrets.token_urlsafe(24)  # Generates a URL-safe token of 24 bytes


def createGallery(project_id: int, created_by_user_id: int | None = None):

    connection = getConnection()

    cursor = connection.cursor()

    share_token = generateGalleryToken()

    now = datetime.now().isoformat()

    cursor.execute(
        """
        INSERT INTO client_galleries (
            project_id,
            share_token,
            is_enabled,
            created_by_user_id,
            created_at,
            updated_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            project_id,
            share_token,
            1,  # is_enabled
            created_by_user_id,
            now,
            now,
        ),
    )

    connection.commit()

    gallery_id = cursor.lastrowid

    connection.close()

    return gallery_id


def getGalleryByProjectId(project_id: int):

    connection = getConnection()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT 
         id,
         project_id,
         share_token,
         is_enabled,
         created_by_user_id,
         created_at,
         updated_at
         FROM client_galleries
            WHERE project_id = ?
        """,
        (project_id,),
    )

    gallery = cursor.fetchone()

    connection.close()

    return gallery


def getGalleryBytoken(share_token: str):

    connection = getConnection()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT 
         id,
         project_id,
         share_token,
         is_enabled,
         created_by_user_id,
         created_at,
         updated_at
         FROM client_galleries
            WHERE share_token = ?
        """,
        (share_token,),
    )

    gallery = cursor.fetchone()

    connection.close()

    return gallery


def setGalleryEnabled(
    gallery_id: int,
    is_enabled: bool,
):

    connection = getConnection()

    cursor = connection.cursor()

    now = datetime.now().isoformat()

    cursor.execute(
        """
        UPDATE client_galleries
        SET is_enabled = ?, 
        updated_at = ?
        WHERE id = ?
        """,
        (
            1 if is_enabled else 0,
            now,
            gallery_id,
        ),
    )

    connection.commit()

    updated = cursor.rowcount > 0

    connection.close()

    return updated


def ensureGalleryCreatorIsOwner(gallery_id: int) -> bool:

    connection = getConnection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
                SELECT 
                    client_galleries.created_by_user_id,
                    users.email
                FROM client_galleries
                JOIN users
                    ON users.id = client_galleries.created_by_user_id
                WHERE client_galleries.id = ?
            """,
            (gallery_id,),
        )

        creator = cursor.fetchone()

        if creator is None or not creator[1] or not creator[1].strip():
            return False

        user_id = creator[0]
        email = creator[1].strip()
        now = datetime.now().isoformat()

        cursor.execute(
            """
                INSERT INTO client_gallery_members (
                    gallery_id,
                    email,
                    user_id,
                    role,
                    invited_by_user_id,
                    created_at,
                    updated_at
                )

                VALUES (?, ?, ? , 'owner', ?, ?, ?)

                ON CONFLICT (gallery_id, email)
                DO UPDATE SET
                    user_id = excluded.user_id,
                    role = 'owner',
                    updated_at = excluded.updated_at
            """,
            (
                gallery_id,
                email,
                user_id,
                user_id,
                now,
                now,
            ),
        )

        connection.commit()
        return True

    finally:
        connection.close()


def isGalleryOwner(gallery_id: int, user_id: int):

    connection = getConnection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
                    SELECT 1
                    FROM client_gallery_members
                        WHERE gallery_id = ?
                        AND user_id = ?
                        AND role = 'owner'
                    LIMIT 1
                """,
            (gallery_id, user_id),
        )

        return cursor.fetchone() is not None

    finally:
        connection.close()


def addOrUpdatGalleryMember(gallery_id: int, email: str, role: str, invited_by_user_id: int):

    email = email.strip().lower()
    now = datetime.now().isoformat()

    connection = getConnection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
                SELECT id FROM users
                    WHERE email COLLATE NOCASE = ?
                    LIMIT 1
            """,
            (email,),
        )

        existing_user = cursor.fetchone()

        receipient_user_id = (
            existing_user[0]
            if existing_user is not None
            else None
        )

        cursor.execute(
            """
                INSERT INTO client_gallery_members (
                    gallery_id,
                    email,
                    user_id,
                    role,
                    invited_by_user_id,
                    created_at,
                    updated_at
                )

                VALUES (?, ?, ?, ?, ?, ?, ?)

                ON CONFLICT (gallery_id, email)
                DO UPDATE SET
                    user_id = COALESCE(
                        excluded.user_id,
                        client_gallery_members.user_id
                    ),
                    role = excluded.role,
                    invited_by_user_id = excluded.invited_by_user_id,
                    updated_at = excluded.updated_at

            """,
            (
                gallery_id, email, receipient_user_id, role, invited_by_user_id, now, now,
            ),
        )

        connection.commit()

        cursor.execute(
            """
                SELECT 
                    id,
                    gallery_id,
                    email,
                    user_id,
                    role,
                    invited_by_user_id,
                    created_at,
                    updated_at
                FROM client_gallery_members
                WHERE gallery_id = ?
                    AND email = ?
            """,
            (gallery_id, email,),
        )

        member = cursor.fetchone()

        return {
            "id": member[0],
            "gallery_id": member[1],
            "email": member[2],
            "user_id": member[3],
            "role": member[4],
            "invited_by_user_id": member[5],
            "created_at": member[6],
            "updated_at": member[7],
        }

    finally: 
        connection.close()