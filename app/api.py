from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.database import getConnection

router = APIRouter()


@router.get("/")
def apiHome():
    return {"message": "Stories By Parin's server is running"}


@router.get("/projects")
def getProjects():
    connection = getConnection()
    cursor = connection.cursor()

    cursor.execute(
        """
            SELECT id, name, created_at FROM projects ORDER BY id DESC
        """
    )

    rows = cursor.fetchall()

    connection.close()

    projects = []

    for row in rows:
        projects.append({"id": row[0], "name": row[1], "created_at": row[2]})

    return projects


@router.get("/projects/{project_id}/events")
def getEvents(project_id: int):
    connection = getConnection()
    cursor = connection.cursor()

    cursor.execute(
        """
            SELECT id, name, created_at FROM events WHERE project_id = ? ORDER BY id ASC
        """,
        (project_id,),
    )

    rows = cursor.fetchall()

    connection.close()

    events = []

    for row in rows:
        events.append({"id": row[0], "name": row[1], "crated_at": row[2]})

    return events


@router.get("/events/{event_id}/photos")
def getEventsPhotos(event_id: int):
    connection = getConnection()
    cursor = connection.cursor()

    cursor.execute(
        """
            SELECT id, filename, status, created_at FROM photos WHERE event_id = ? ORDER BY id ASC
        """,
        (event_id,),
    )

    rows = cursor.fetchall()

    connection.close()

    photos = []

    for row in rows:
        photos.append(
            {
                "id": row[0],
                "filename": row[1],
                "status": row[2],
                "created_at": row[3],
            }
        )

    return photos


@router.get("/photos/{photo_id}/image")
def getPhotoImage(photo_id: int):

    connection = getConnection()

    cursor = connection.cursor()

    cursor.execute(
        """
            SELECT file_path FROM photos WHERE id = ?
        """,
        (photo_id,),
    )

    row = cursor.fetchone()

    connection.close()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail="Photo not found",
        )

    file_path = Path(row[0])

    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Photo not found",
        )

    return FileResponse(file_path)


@router.get("/faces/{face_id}/photos")
def getPhotosForFace(face_id: int):

    connection = getConnection()

    cursor = connection.cursor()

    cursor.execute(
        """
            SELECT cluster_id FROM face_cluster_members WHERE face_id = ? LIMIT 1
        """,
        (face_id,),
    )

    cluster_row = cursor.fetchone()

    if cluster_row is None:
        connection.close()

        return []

    cluster_id = cluster_row[0]

    cursor.execute(
        """
            SELECT DISTINCT 
                photos.id,
                photos.filename,
                photos.status,
                photos.created_at
            FROM face_cluster_members
            JOIN faces
                ON faces.id = face_cluster_members.face_id
            JOIN photos
                ON photos.id = faces.photo_id
            WHERE face_cluster_members.cluster_id = ?
            ORDER BY photos.id ASC
        """,
        (cluster_id,),
    )

    rows = cursor.fetchall()

    connection.close()

    photos = []

    for row in rows:
        photos.append(
            {"id": row[0], "filename": row[1], "status": row[2], "created_at": row[3]}
        )

    return photos


@router.get("/clusters")
def getClusters():

    connection = getConnection()

    cursor = connection.cursor()

    cursor.execute(
        """
            SELECT id, face_count, created_at, updated_at FROM face_clusters ORDER BY id ASC
        """
    )

    rows = cursor.fetchall()

    connection.close()

    clusters = []

    for row in rows:
        clusters.append(
            {
                "id": row[0],
                "face_count": row[1],
                "created_at": row[2],
                "updated_at": row[3],
            }
        )

    return clusters
