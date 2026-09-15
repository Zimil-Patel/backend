import hashlib
from pathlib import Path

from app.database.connection import getConnection


def calculateFileHash(file_path: str):
    """
    Calculate the SHA-256 hash of a photo file.

    The hash lets us detect duplicate photos even when
    the same photo has been renamed.
    """

    sha256 = hashlib.sha256()

    # Read the file in chunks so large photos don't
    # have to be loaded completely into memory.
    with open(file_path, "rb") as file:
        while True:
            chunk = file.read(1024 * 1024)

            if not chunk:
                break

            sha256.update(chunk)

    return sha256.hexdigest()


def photoHashExists(file_hash: str):
    """
    Check whether a photo with this file hash
    already exists in the database.
    """

    connection = getConnection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT id
        FROM photos
        WHERE file_hash = ?
        """,
        (file_hash,),
    )

    row = cursor.fetchone()

    connection.close()

    return row is not None


def createPhoto(
    event_id: int,
    filename: str,
    file_path: str,
    file_hash: str,
    width: int,
    height: int,
):
    """
    Create a new photo record in the database.
    """

    connection = getConnection()
    cursor = connection.cursor()

    created_at = Path(file_path).stat().st_mtime

    cursor.execute(
        """
        INSERT INTO photos (
            event_id,
            filename,
            file_path,
            file_hash,
            status,
            created_at,
            width,
            height
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_id,
            filename,
            file_path,
            file_hash,
            "PENDING",
            created_at,
            width,
            height,
        ),
    )

    connection.commit()

    photo_id = cursor.lastrowid

    connection.close()

    return photo_id


def updatePhotoThumbnailPath(
    photo_id: int,
    thumbnail_path: str,
):
    """
    Save the generated thumbnail path for a photo.
    """

    connection = getConnection()
    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE photos
        SET thumbnail_path = ?
        WHERE id = ?
        """,
        (
            thumbnail_path,
            photo_id,
        ),
    )

    connection.commit()
    connection.close()


def updatePhotoStatus(
    photo_id: int,
    status: str,
):
    """
    Update the processing status of a photo.
    """

    connection = getConnection()
    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE photos
        SET status = ?
        WHERE id = ?
        """,
        (
            status,
            photo_id,
        ),
    )

    connection.commit()
    connection.close()