from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.database import getConnection
from app.services.selfie_service import searchSelfie

from app.auth.dependencies import getCurrentFirebaseUser, getCurrentLocalUser
from fastapi import Depends
from app.database.user_db import syncUser
from app.database.photo_db import setPhotoFavouriteStatus
from app.database.gallery_db import getGalleryByProjectId, createGallery, setGalleryEnabled
from pydantic import BaseModel


class GalleryStatusUpdate(BaseModel):
    is_enabled: bool

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
        events.append({"id": row[0], "name": row[1], "created_at": row[2]})

    return events


@router.get("/events/{event_id}/photos")
def getEventsPhotos(event_id: int):
    connection = getConnection()
    cursor = connection.cursor()

    cursor.execute(
        """
            SELECT id, filename, status, created_at, height, width, is_favourite FROM photos WHERE event_id = ? ORDER BY id ASC
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
                "height": row[4],
                "width": row[5],
                "is_favourite": row[6]
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


@router.get("/projects/{project_id}/faces/{face_id}/photos")
def getPhotosForFace(face_id: int, project_id: int):

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
            photos.created_at,
            photos.height,
            photos.width,
            photos.is_favourite

        FROM face_cluster_members

        JOIN faces
            ON faces.id = face_cluster_members.face_id

        JOIN photos
            ON photos.id = faces.photo_id

        JOIN events
            ON events.id = photos.event_id

        WHERE face_cluster_members.cluster_id = ?
            AND events.project_id = ?

        ORDER BY photos.id ASC
        """,
        (cluster_id,project_id,),
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
                "height": row[4],
                "width": row[5],
                "is_favourite": row[6]
            }
        )

    return {
        "face_id": face_id,
        "cluster_id": cluster_id,
        "project_id": project_id,
        "photos_count": len(photos),
        "photos": photos,
    }


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


@router.get("/projects/{project_id}/faces")
def getProjectFaces(project_id: int):

    connection = getConnection()

    cursor = connection.cursor()

    # Find all face clusters that have faces inside this project.
    #
    # DISTINCT is important:
    # One person can appear in many photos, but we want
    # that person/cluster only once in the result.
    # -----------------------------------------------------
    # FIND ONE REPRESENTATIVE FACE PER CLUSTER
    # -----------------------------------------------------
    #
    # We use ROW_NUMBER() to rank faces inside each cluster.
    #
    # rn = 1 means:
    # "This is the best face we selected for this cluster."
    #
    # For now, detection_score is our quality criterion.
    # Later we can use a more advanced quality score that
    # includes sharpness, face size, exposure, etc.
    cursor.execute(
        """
        WITH ranked_faces AS (

    SELECT
        fc.id AS cluster_id,
        fcm.face_id,
        f.photo_id,
        f.bbox,
        f.detection_score,

        -- Rank faces inside each cluster.
        -- The highest detection score gets rank 1.
        ROW_NUMBER() OVER (
            PARTITION BY fc.id
            ORDER BY
                f.detection_score DESC,
                f.id ASC
        ) AS rn

    FROM face_clusters AS fc

    -- Connect each cluster to its member faces.
    JOIN face_cluster_members AS fcm
        ON fcm.cluster_id = fc.id

    -- Get the actual face record.
    JOIN faces AS f
        ON f.id = fcm.face_id

    -- Get the photo containing that face.
    JOIN photos AS p
        ON p.id = f.photo_id

    -- Get the event containing that photo.
    JOIN events AS e
        ON e.id = p.event_id

    -- Only include faces belonging to the requested project.
    WHERE e.project_id = ?
)

SELECT
    rf.cluster_id,
    rf.face_id,
    rf.photo_id,
    rf.bbox,
    rf.detection_score,

    -- Count how many UNIQUE photos contain this person
    -- inside the requested project.
    (
        SELECT COUNT(DISTINCT p_count.id)

        FROM face_cluster_members AS fcm_count

        -- Get each face belonging to this cluster.
        JOIN faces AS f_count
            ON f_count.id = fcm_count.face_id

        -- Get the photo containing that face.
        JOIN photos AS p_count
            ON p_count.id = f_count.photo_id

        -- Get the event containing that photo.
        JOIN events AS e_count
            ON e_count.id = p_count.event_id

        -- Only count this particular cluster.
        WHERE fcm_count.cluster_id = rf.cluster_id

        -- And only count photos from this project.
        AND e_count.project_id = ?
    ) AS project_photo_count

        FROM ranked_faces AS rf

        -- Keep only the best representative face for each cluster.
        WHERE rf.rn = 1

        -- MOST PHOTOS FIRST.
        --
        -- Example:
        -- Cluster 12 → 245 photos
        -- Cluster 15 → 180 photos
        -- Cluster 16 → 90 photos
        ORDER BY
            project_photo_count DESC,

            -- If two people have the same number of photos,
            -- use cluster ID as a stable tie-breaker.
            rf.cluster_id ASC
        """,
        (
            project_id,
            project_id,
        ),
    )

    rows = cursor.fetchall()

    connection.close()

    people = []

    for row in rows:
        people.append(
            {
                "cluster_id": row[0],
                "face_id": row[1],
                "photo_id": row[2],
                "bbox": row[3],
                "detection_score": row[4],
                "photo_count": row[5],
            }
        )

    return people


# Get thumbnail of faces
@router.get("/faces/{face_id}/image")
def getFaceImage(face_id: int):

    connection = getConnection()

    cursor = connection.cursor()

    cursor.execute(
        """
            SELECT 
                thumbnail_path
            FROM faces
            WHERE faces.id = ?
        """,
        (face_id,),
    )

    row = cursor.fetchone()

    connection.close()

    thumbnail_path = row[0]

    if not thumbnail_path:
        raise HTTPException(status_code=404, detail="Face not found")

    thumbnail = Path(thumbnail_path)

    if not thumbnail.exists():
        raise HTTPException(status_code=404, detail="Face thumbnail file not found")

    return FileResponse(
        thumbnail,
        media_type="image/jpeg",
    )


@router.post("/projects/{project_id}/search-selfie")
async def searchProjectBySelfie(project_id: int, selfie: UploadFile = File(...)):

    print(f"File type: {selfie.content_type}")

    # if not selfie.content_type or not selfie.content_type.startswith("image/"):
    #     raise HTTPException(status_code=400, detail="Please upload an image.")

    selfie_bytes = await selfie.read()

    if not selfie_bytes:
        raise HTTPException(status_code=400, detail="Upload image is empty.")

    result = searchSelfie(selfie_bytes=selfie_bytes, project_id=project_id)

    return result


@router.get("/photos/{photo_id}/thumbnail")
def getPhotoThumbnail(photo_id: int):

    connection = getConnection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT thumbnail_path
        FROM photos
        WHERE id = ?
        """,
        (photo_id,),
    )

    row = cursor.fetchone()

    connection.close()

    # Photo does not exist.
    if row is None:
        raise HTTPException(
            status_code=404,
            detail="Photo not found",
        )

    thumbnail_path = row[0]

    # Thumbnail has not been generated yet.
    if not thumbnail_path:
        raise HTTPException(
            status_code=404,
            detail="Photo thumbnail not found",
        )

    thumbnail_file = Path(thumbnail_path)

    # Thumbnail path exists in DB but the actual file is missing.
    if not thumbnail_file.exists():
        raise HTTPException(
            status_code=404,
            detail="Photo thumbnail file not found",
        )

    return FileResponse(thumbnail_file)

@router.put("/photos/{photo_id}/favourite")
def setPhotoFavourite(
    photo_id: int,
    is_favourite: bool,
):
    """
    Favourite or unfavourite a photo.

    True  -> Favourite the photo
    False -> Unfavourite the photo
    """

    updated = setPhotoFavouriteStatus(
        photo_id=photo_id,
        is_favourite=is_favourite,
    )

    # If no photo exists with this ID, return 404.
    if not updated:
        raise HTTPException(
            status_code=404,
            detail="Photo not found",
        )

    return {
        "success": True,
        "photo_id": photo_id,
        "is_favourite": is_favourite,
    }

### Authtentication
@router.get("/auth/me")
def getCurrentUser(user=Depends(getCurrentLocalUser)):

    return {
        "success": True,
        "user": user
    }


def galleryToResponse(gallery):
    """Convert a database gallery row into an API response."""

    return {
        "success": True,
        "gallery": {
            "id": gallery[0],
            "project_id": gallery[1],
            "share_token": gallery[2],
            "is_enabled": bool(gallery[3]),
            "created_by_user_id": gallery[4],
            "created_at": gallery[5],
            "updated_at": gallery[6],
        },
    }

# create gallery 
@router.post('/projects/{project_id}/gallery')
def createProjectGallery(
    project_id: int,
    user=Depends(getCurrentLocalUser),
):

    connection = getConnection()
    cursor = connection.cursor()

    cursor.execute(
        """
            SELECT id FROM
            projects
            WHERE id = ?
        """,
        (
            project_id,
        ),
    )

    project = cursor.fetchone()
    connection.close()

    if project is None:

        raise HTTPException(
            status_code=404,
            detail="Project not found"
        )

    gallery = getGalleryByProjectId(project_id)

    if gallery is None:

        createGallery(project_id=project_id, created_by_user_id=user['id'],)

        gallery = getGalleryByProjectId(project_id)

    return galleryToResponse(gallery)

#update is enabled in gallery
@router.patch('/projects/{project_id}/gallery')
def updatePrjectGalleryStatus(
    project_id: int,
    request: GalleryStatusUpdate,
    user=Depends(getCurrentLocalUser)
):
    gallery = getGalleryByProjectId(project_id)

    if gallery is None:
        raise HTTPException(
            status_code=404,
            detail="Client gallery not found for this project",
        )

    updated = setGalleryEnabled(
        gallery_id=gallery[0],
        is_enabled=request.is_enabled,

    )

    gallery = getGalleryByProjectId(project_id)

    return galleryToResponse(gallery)
