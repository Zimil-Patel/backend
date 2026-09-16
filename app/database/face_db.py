from app.database.connection import getConnection
from datetime import datetime

def saveFace(
    photo_id: int,
    face_index: int,
    bbox: str,
    detection_score: float,
    embedding: bytes,
):
    """
    Save one detected face in the database.

    Each detected face belongs to exactly one photo.
    The embedding is stored as bytes so SQLite can store it.
    """

    connection = getConnection()
    cursor = connection.cursor()

    created_at = datetime.now().isoformat()

    cursor.execute(
        """
        INSERT INTO faces (
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
            created_at
        ),
    )

    connection.commit()

    face_id = cursor.lastrowid

    connection.close()

    return face_id


def deleteFacesForPhoto(photo_id: int):
    """
    Delete all previously detected faces for a photo.

    This is useful when a photo is processed again,
    so old face records don't remain in the database.
    """

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


def updateFaceThumbnailPath(
    face_id: int,
    thumbnail_path: str,
):
    """
    Save the generated face-thumbnail path.
    """

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