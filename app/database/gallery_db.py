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


