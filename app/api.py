from pathlib import Path

from uuid import uuid4
from fastapi import APIRouter, File, HTTPException, UploadFile, Request
from fastapi.responses import FileResponse

from app.database import getConnection
from app.services.selfie_service import searchSelfie

from app.auth.dependencies import getCurrentLocalUser
from app.database.user_db import updateUserPhotoUrl
from app.services.image_service import saveProfilePhoto
from fastapi import Depends
from app.database.photo_db import setPhotoFavouriteStatus
from datetime import timezone, datetime
from app.database.gallery_db import (
    getGalleryByProjectId,
    createGallery,
    setGalleryEnabled,
    isGalleryOwner,
    addOrUpdatGalleryMember,
    getGalleriesForUser,
    ensureGalleryCreatorIsOwner,
    getGalleryBytoken,
    getGalleryMemberRole,
    getGalleryMembers,
    updateGalleryMemberRole,
    removeGalleryMember,
)

from app.database.sharing_db import (
    createGalleryShareLink,
    getGalleryShareLink,
    getGalleryShareLinks,
    revokeGalleryShareLink,
    createGalleryAccessRequest,
    getGalleryAccessRequests,
    resolveGalleryAccessRequest,
    createGalleryInvitation,
    getGalleryInvitations,
    revokeGalleryInvitation,
    registerDeviceToken,
    removeDeviceToken,
    createUserNotification,
    getUserNotifications,
    markUserNotificationRead,
    linkPendingGalleryInvitationsForUser
)

from typing import Literal
from pydantic import BaseModel


class ShareGalleryRequest(BaseModel):
    email: str
    role: Literal["owner", "viewer"]


class GalleryStatusUpdate(BaseModel):
    is_enabled: bool

class UpdateGalleryMemberRoleRequest(BaseModel):
    role: Literal["owner", "viewer"]


class CreateGalleryShareLinkRequest(BaseModel):
    expires_at_utc: str


class ResolveGalleryAccessRequestBody(BaseModel):
    approve: bool


class DeviceTokenRequest(BaseModel):
    token: str
    platform: str | None = None

PROFILE_PHOTOS_DIR = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "profiles"
)

router = APIRouter()


def requireGalleryPhotoAccess(project_id: int, user_id: int):

    gallery = getGalleryByProjectId(project_id)

    if gallery is None:
        raise HTTPException(status_code=404, detail="Gallery not found or unavailable")

    role = getGalleryMemberRole(gallery_id=gallery[0], user_id=user_id)

    if role is None:
        raise HTTPException(status_code=404, detail="Gallery not found or unavailable")

    if not bool(gallery[3]) and role != "owner":
        raise HTTPException(status_code=404, detail="Gallery not found or unavailable")

    return role


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
def getEventsPhotos(event_id: int, user=Depends(getCurrentLocalUser)):
    connection = getConnection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
                SELECT project_id
                FROM events
                WHERE id = ?
            """,
            (event_id,),
        )

        event = cursor.fetchone()

    finally:
        connection.close()

    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    requireGalleryPhotoAccess(user_id=user["id"], project_id=event[0])

    connection = getConnection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
                SELECT id, 
                filename, 
                status, 
                created_at, 
                height, 
                width, 
                is_favourite 
                FROM photos 
                WHERE event_id = ? 
                ORDER BY id ASC
            """,
            (event_id,),
        )

        rows = cursor.fetchall()

    finally:
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
                "is_favourite": row[6],
            }
        )

    return photos


@router.get("/photos/{photo_id}/image")
def getPhotoImage(photo_id: int, user = Depends(getCurrentLocalUser)):

    connection = getConnection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
                SELECT 
                    photos.file_path,
                    events.project_id
                FROM photos 
                JOIN events
                    ON events.id = photos.event_id
                WHERE photos.id = ?
            """,
            (photo_id,),
        )

        row = cursor.fetchone()

    finally:
        connection.close()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail="Photo not found",
        )

    requireGalleryPhotoAccess(
        project_id=row[1],
        user_id=user["id"]
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
        (
            cluster_id,
            project_id,
        ),
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
                "is_favourite": row[6],
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
def getPhotoThumbnail(photo_id: int, user = Depends(getCurrentLocalUser)):

    connection = getConnection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
                SELECT photos.thumbnail_path, events.project_id
                FROM photos
                JOIN events
                    ON events.id = photos.event_id
                WHERE photos.id = ?
            """,
            (photo_id,),
        )

        row = cursor.fetchone()

    finally:
        connection.close()

    # Photo does not exist.
    if row is None:
        raise HTTPException(
            status_code=404,
            detail="Photo not found",
        )

    requireGalleryPhotoAccess(
        project_id=row[1],
        user_id=user["id"],
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
    user=Depends(getCurrentLocalUser),
):
    """
    Allow only gallery Owners to favourite or unfavourite photos.
    """

    # Find the project associated with this photo.
    connection = getConnection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT events.project_id
            FROM photos
            JOIN events
                ON events.id = photos.event_id
            WHERE photos.id = ?
            """,
            (photo_id,),
        )

        photo = cursor.fetchone()

    finally:
        connection.close()

    # Return 404 if the photo does not exist.
    if photo is None:
        raise HTTPException(
            status_code=404,
            detail="Photo not found",
        )

    project_id = photo[0]

    # Find the gallery associated with this project.
    gallery = getGalleryByProjectId(project_id)

    if gallery is None:
        raise HTTPException(
            status_code=404,
            detail="Gallery not found",
        )

    # Check the signed-in user's role in this gallery.
    role = getGalleryMemberRole(
        gallery_id=gallery[0],
        user_id=user["id"],
    )

    # Don't allow users who aren't members to modify favourites.
    if role is None:
        raise HTTPException(
            status_code=404,
            detail="Gallery not found",
        )

    # Only Owners can change the shared favourite status.
    if role != "owner":
        raise HTTPException(
            status_code=403,
            detail="Only gallery Owners can change favourites",
        )

    # Update the database using your existing helper.
    updated = setPhotoFavouriteStatus(
        photo_id=photo_id,
        is_favourite=is_favourite,
    )

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

    return {"success": True, "user": user}


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
@router.post("/projects/{project_id}/gallery")
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
        (project_id,),
    )

    project = cursor.fetchone()
    connection.close()

    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    gallery = getGalleryByProjectId(project_id)

    if gallery is None:
        createGallery(
            project_id=project_id,
            created_by_user_id=user["id"],
        )

        gallery = getGalleryByProjectId(project_id)

        ensureGalleryCreatorIsOwner(gallery[0])

    return galleryToResponse(gallery)



@router.patch("/projects/{project_id}/gallery")
def updateProjectGalleryStatus(
    project_id: int,
    request: GalleryStatusUpdate,
    user=Depends(getCurrentLocalUser),
):
    gallery = getGalleryByProjectId(project_id)

    if gallery is None:
        raise HTTPException(
            status_code=404,
            detail="Client gallery not found for this project",
        )

    gallery_id = gallery[0]

    if not isGalleryOwner(
        gallery_id=gallery_id,
        user_id=user["id"],
    ):
        raise HTTPException(
            status_code=403,
            detail="Only gallery Owners can change gallery status",
        )

    updated = setGalleryEnabled(
        gallery_id=gallery_id,
        is_enabled=request.is_enabled,
    )

    if not updated:
        raise HTTPException(
            status_code=500,
            detail="Unable to update gallery status",
        )

    gallery = getGalleryByProjectId(project_id)

    return galleryToResponse(gallery)



@router.post("/projects/{project_id}/gallery/members")
def shareProjectGallery(
    project_id: int,
    request: ShareGalleryRequest,
    user=Depends(getCurrentLocalUser),
):
    gallery = getGalleryByProjectId(project_id)

    if gallery is None:
        raise HTTPException(
            status_code=404,
            detail="Client gallery not found for this project",
        )

    gallery_id = gallery[0]
    current_user_id = user["id"]

    if not isGalleryOwner(gallery_id, current_user_id):
        raise HTTPException(
            status_code=403,
            detail="Only gallery Owners can manage access",
        )

    email = request.email.strip().lower()

    if email.count("@") != 1 or "." not in email.rsplit("@", 1)[1]:
        raise HTTPException(
            status_code=422,
            detail="Please provide a valid email address",
        )

    current_email = (user.get("email") or "").strip().lower()

    if email == current_email and request.role != "owner":
        raise HTTPException(
            status_code=400,
            detail="You cannot downgrade your own Owner access here",
        )

    # Record the invitation first.
    invitation = createGalleryInvitation(
        gallery_id=gallery_id,
        email=email,
        role=request.role,
        invited_by_user_id=current_user_id,
    )

    # Find an existing local account. Email verification is not
    # checked at this stage, as requested.
    connection = getConnection()

    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT id
            FROM users
            WHERE email COLLATE NOCASE = ?
            LIMIT 1
            """,
            (email,),
        )
        existing_user = cursor.fetchone()

        if existing_user is not None:
            invited_user_id = existing_user[0]

            # Registered users receive access immediately.
            member = addOrUpdatGalleryMember(
                gallery_id=gallery_id,
                email=email,
                role=request.role,
                invited_by_user_id=current_user_id,
            )

            cursor.execute(
                """
                UPDATE gallery_invitations
                SET invited_user_id = ?,
                    status = 'accepted',
                    updated_at_utc = ?
                WHERE id = ?
                """,
                (
                    invited_user_id,
                    datetime.now(timezone.utc).isoformat(),
                    invitation["id"],
                ),
            )
            connection.commit()

            return {
                "success": True,
                "invitation": {
                    **invitation,
                    "invited_user_id": invited_user_id,
                    "status": "accepted",
                },
                "member": member,
                "access_granted": True,
            }

    finally:
        connection.close()

    # The email has no existing local account, so do not create
    # a membership yet.
    return {
        "success": True,
        "invitation": invitation,
        "access_granted": False,
        "message": "Invitation saved. Access will be available after the user registers.",
    }



@router.get("/my-galleries")
def getMyGalleries(user=Depends(getCurrentLocalUser)):

    galleries = getGalleriesForUser(user["id"])

    return {"success": True, "galleries": galleries}


@router.get("/gallery/{share_token}")
def getClientGallery(share_token: str, user=Depends(getCurrentLocalUser)):

    gallery = getGalleryBytoken(share_token)

    if gallery is None or not bool(gallery[3]):
        raise HTTPException(status_code=404, detail="Gallery not found or unavailable")

    role = getGalleryMemberRole(
        gallery_id=gallery[0],
        user_id=user["id"],
    )

    if role is None:
        raise HTTPException(status_code=404, detail="Gallery not found or unavailable")

    connection = getConnection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
                SELECT id, name, created_at
                FROM projects
                WHERE id = ?
            """,
            (gallery[1],),
        )

        project = cursor.fetchone()

        if project is None:
            raise HTTPException(
                status_code=404, detail="Gallery not found or unavailable"
            )

        cursor.execute(
            """
            SELECT id, name, created_at
            FROM events
            WHERE project_id = ?
            ORDER BY id ASC
            """,
            (project[0],),
        )

        event_rows = cursor.fetchall()

    finally:
        connection.close()

    return {
        "success": True,
        "gallery": {
            "id": gallery[0],
            "is_enabled": bool(gallery[3]),
            "created_at": gallery[5],
        },
        "project": {
            "id": project[0],
            "name": project[1],
            "created_at": project[2],
        },
        "role": role,
        "events": [
            {
                "id": event[0],
                "name": event[1],
                "created_at": event[2],
            }
            for event in event_rows
        ],
    }


@router.get(
    "/profiles/{user_id}/image",
    name="getProfilePhotoImage",
)
def getProfilePhotoImage(user_id: int):
    """
    Serve a user's profile photo without requiring authentication.

    Profile photos are publicly readable.
    Uploading or changing a photo still requires authentication.
    """

    # Build the path using the local SQLite user ID.
    # The filename is fixed, so callers cannot specify arbitrary paths.
    image_path = (
        PROFILE_PHOTOS_DIR
        / str(user_id)
        / "profile.jpg"
    )

    # Return 404 when no profile photo exists.
    if not image_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Profile photo not found.",
        )

    # Serve the JPEG without requiring a Firebase ID token.
    return FileResponse(
        image_path,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "public, max-age=300",
        },
    )


@router.post("/auth/me/profile-photo")
def uploadMyProfilePhoto(
    request: Request,
    file: UploadFile = File(...),
    user=Depends(getCurrentLocalUser),
):
    """
    Upload the current user's profile photo.

    The destination is derived from the authenticated local user ID,
    so the client cannot choose another user's profile directory.
    """

    # Store each user's current profile image separately.
    user_directory = PROFILE_PHOTOS_DIR / str(user["id"])
    output_path = user_directory / "profile.jpg"

    try:
        # Start reading from the beginning of the uploaded file.
        file.file.seek(0)

        # Decode, correct orientation, crop, resize, and save the image.
        saveProfilePhoto(
            source_file=file.file,
            output_path=str(output_path),
            size=(512, 512),
        )

    except ValueError as error:
        # The uploaded bytes could not be decoded as a supported image.
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except OSError as error:
        # Report storage-related errors separately from invalid images.
        raise HTTPException(
            status_code=500,
            detail="Unable to save the profile photo.",
        ) from error

    finally:
        # Release the uploaded temporary file.
        file.file.close()

    # Generate the URL for the authenticated image-serving endpoint.
    # The changing query value also helps the Flutter image cache
    # distinguish a newly uploaded photo from a previous version.
    base_url = str(request.base_url).rstrip("/")

    photo_url = (
        f"{base_url}/profiles/{user['id']}/image"
        f"?v={uuid4().hex}"
    )

    # Save the current photo URL in the local SQLite user record.
    updated = updateUserPhotoUrl(
        firebase_uid=user["firebase_uid"],
        photo_url=photo_url,
    )

    if not updated:
        raise HTTPException(
            status_code=500,
            detail="The photo was saved, but the user record was not updated.",
        )

    return {
        "success": True,
        "photo_url": photo_url,
    }

@router.get("/projects/{project_id}/gallery/members")
def getProjectGalleryMembers(
    project_id: int,
    user=Depends(getCurrentLocalUser),
):
    """
    Return members and pending invitations for a gallery.

    Only gallery Owners can view the member list.
    """

    # Find the gallery associated with this project.
    gallery = getGalleryByProjectId(project_id)

    if gallery is None:
        raise HTTPException(
            status_code=404,
            detail="Gallery not found",
        )

    gallery_id = gallery[0]

    # Retrieve this user's role in the gallery.
    role = getGalleryMemberRole(
        gallery_id=gallery_id,
        user_id=user["id"],
    )

    # Do not reveal gallery membership to non-members.
    if role is None:
        raise HTTPException(
            status_code=404,
            detail="Gallery not found",
        )

    # Viewers can see photos but cannot manage gallery members.
    if role != "owner":
        raise HTTPException(
            status_code=403,
            detail="Only gallery Owners can view the member list",
        )

    # Retrieve registered members and unclaimed invitations.
    members = getGalleryMembers(gallery_id)

    return {
        "success": True,
        "gallery_id": gallery_id,
        "project_id": project_id,
        "members": members,
    }

@router.patch("/projects/{project_id}/gallery/members/{member_id}")
def changeGalleryMemberRole(
    project_id: int,
    member_id: int,
    request: UpdateGalleryMemberRoleRequest,
    user=Depends(getCurrentLocalUser),
):
    """
    Update a gallery member's role.
    Only Owners can perform this operation.
    """

    # Locate the gallery associated with the project.
    gallery = getGalleryByProjectId(project_id)

    if gallery is None:
        raise HTTPException(
            status_code=404,
            detail="Client gallery not found",
        )

    gallery_id = gallery[0]

    # Only a current Owner may change membership roles.
    if not isGalleryOwner(
        gallery_id=gallery_id,
        user_id=user["id"],
    ):
        raise HTTPException(
            status_code=403,
            detail="Only gallery Owners can change member roles",
        )

    # Update the membership, including last-Owner safeguards.
    result = updateGalleryMemberRole(
        gallery_id=gallery_id,
        member_id=member_id,
        role=request.role,
        current_user_id=user["id"],
    )

    if result["status"] == "not_found":
        raise HTTPException(
            status_code=404,
            detail="Gallery member not found",
        )

    if result["status"] == "self_demotion":
        raise HTTPException(
            status_code=400,
            detail="You cannot downgrade your own Owner access",
        )

    if result["status"] == "last_owner":
        raise HTTPException(
            status_code=409,
            detail="The last Owner cannot be demoted",
        )

    return {
        "success": True,
        "member": result["member"],
    }

@router.delete(
    "/projects/{project_id}/gallery/members/{member_id}"
)
def deleteProjectGalleryMember(
    project_id: int,
    member_id: int,
    user=Depends(getCurrentLocalUser),
):
    """
    Remove a gallery member or pending invitation.

    Only Owners can remove membership.
    """

    # Find the gallery associated with the requested project.
    gallery = getGalleryByProjectId(project_id)

    if gallery is None:
        raise HTTPException(
            status_code=404,
            detail="Client gallery not found",
        )

    gallery_id = gallery[0]

    # Verify that the authenticated user is a gallery Owner.
    if not isGalleryOwner(
        gallery_id=gallery_id,
        user_id=user["id"],
    ):
        raise HTTPException(
            status_code=403,
            detail="Only gallery Owners can remove members",
        )

    # Remove the specific membership, with Owner safeguards.
    result = removeGalleryMember(
        gallery_id=gallery_id,
        member_id=member_id,
        current_user_id=user["id"],
    )

    if result["status"] == "not_found":
        raise HTTPException(
            status_code=404,
            detail="Gallery member not found",
        )

    if result["status"] == "self_removal":
        raise HTTPException(
            status_code=400,
            detail="You cannot remove your own gallery membership",
        )

    if result["status"] == "last_owner":
        raise HTTPException(
            status_code=409,
            detail="The last Owner cannot be removed",
        )

    return {
        "success": True,
        "message": "Gallery member removed successfully",
        "removed_member": result["member"],
    }


def _requireGalleryOwnerForProject(project_id: int, user_id: int) -> int:
    """Return the gallery ID after verifying the current user is an Owner."""
    gallery = getGalleryByProjectId(project_id)

    if gallery is None:
        raise HTTPException(status_code=404, detail="Gallery not found")

    gallery_id = gallery[0]

    if not isGalleryOwner(gallery_id, user_id):
        raise HTTPException(
            status_code=403,
            detail="Only gallery Owners can perform this action",
        )

    return gallery_id


def _getGalleryOwnerUserIds(gallery_id: int) -> list[int]:
    """Get local user IDs of all current gallery Owners."""
    connection = getConnection()

    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT user_id
            FROM client_gallery_members
            WHERE gallery_id = ?
              AND role = 'owner'
              AND user_id IS NOT NULL
            """,
            (gallery_id,),
        )
        return list({row[0] for row in cursor.fetchall()})

    finally:
        connection.close()


def _notifyGalleryOwners(
    gallery_id: int,
    notification_type: str,
    title: str,
    body: str,
    data: dict,
):
    """Create an in-app notification for each Owner."""
    for owner_id in _getGalleryOwnerUserIds(gallery_id):
        createUserNotification(
            user_id=owner_id,
            notification_type=notification_type,
            title=title,
            body=body,
            data=data,
        )


# ---------------------------------------------------------
# SHARE LINKS
# ---------------------------------------------------------

@router.post("/projects/{project_id}/gallery/share-links")
def createProjectGalleryShareLink(
    project_id: int,
    request: CreateGalleryShareLinkRequest,
    user=Depends(getCurrentLocalUser),
):
    gallery_id = _requireGalleryOwnerForProject(project_id, user["id"])

    try:
        result = createGalleryShareLink(
            gallery_id=gallery_id,
            created_by_user_id=user["id"],
            expires_at_utc=request.expires_at_utc,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    if result["status"] == "gallery_not_found":
        raise HTTPException(status_code=404, detail="Gallery not found")

    return {
        "success": True,
        "share_link": result,
    }


@router.get("/projects/{project_id}/gallery/share-links")
def listProjectGalleryShareLinks(
    project_id: int,
    user=Depends(getCurrentLocalUser),
):
    gallery_id = _requireGalleryOwnerForProject(project_id, user["id"])

    return {
        "success": True,
        "share_links": getGalleryShareLinks(gallery_id),
    }


@router.delete(
    "/projects/{project_id}/gallery/share-links/{share_link_id}"
)
def deleteProjectGalleryShareLink(
    project_id: int,
    share_link_id: int,
    user=Depends(getCurrentLocalUser),
):
    gallery_id = _requireGalleryOwnerForProject(project_id, user["id"])

    revoked = revokeGalleryShareLink(
        gallery_id=gallery_id,
        share_link_id=share_link_id,
    )

    if not revoked:
        raise HTTPException(
            status_code=404,
            detail="Share link not found or already revoked",
        )

    return {
        "success": True,
        "message": "Share link revoked. Existing requests and memberships are unchanged.",
    }


# ---------------------------------------------------------
# ACCESS REQUESTS
# ---------------------------------------------------------

@router.post("/gallery/share-links/{token}/requests")
def requestGalleryAccess(
    token: str,
    user=Depends(getCurrentLocalUser),
):
    try:
        result = createGalleryAccessRequest(
            token=token,
            requester_user_id=user["id"],
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    error_messages = {
        "invalid_link": (404, "Share link not found"),
        "link_revoked": (410, "This share link has been revoked"),
        "link_expired": (410, "This share link has expired"),
        "gallery_unavailable": (404, "Gallery is unavailable"),
        "already_member": (409, "You already have gallery access"),
    }

    if result["status"] in error_messages:
        status_code, message = error_messages[result["status"]]
        raise HTTPException(status_code=status_code, detail=message)

    if result["status"] == "created":
        _notifyGalleryOwners(
            gallery_id=result["gallery_id"],
            notification_type="gallery_access_request",
            title="New gallery access request",
            body=f"{user.get('email') or 'A user'} requested gallery access.",
            data={
                "gallery_id": result["gallery_id"],
                "request_id": result["id"],
            },
        )

    return {
        "success": True,
        "request": result,
    }


@router.get("/projects/{project_id}/gallery/access-requests")
def listProjectGalleryAccessRequests(
    project_id: int,
    status: str | None = None,
    user=Depends(getCurrentLocalUser),
):
    gallery_id = _requireGalleryOwnerForProject(project_id, user["id"])

    try:
        requests = getGalleryAccessRequests(
            gallery_id=gallery_id,
            status=status,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    return {
        "success": True,
        "gallery_id": gallery_id,
        "requests": requests,
    }


@router.post(
    "/projects/{project_id}/gallery/access-requests/{request_id}/decision"
)
def decideProjectGalleryAccessRequest(
    project_id: int,
    request_id: int,
    request: ResolveGalleryAccessRequestBody,
    user=Depends(getCurrentLocalUser),
):
    gallery_id = _requireGalleryOwnerForProject(project_id, user["id"])

    result = resolveGalleryAccessRequest(
        gallery_id=gallery_id,
        request_id=request_id,
        owner_user_id=user["id"],
        approve=request.approve,
    )

    if result["status"] == "request_not_found":
        raise HTTPException(status_code=404, detail="Access request not found")

    if result["status"] == "requester_not_found":
        raise HTTPException(status_code=404, detail="Requester account not found")

    if result["status"] == "request_already_resolved":
        raise HTTPException(
            status_code=409,
            detail="This access request has already been resolved",
        )

    decision = result["decision"]

    createUserNotification(
        user_id=result["requester_user_id"],
        notification_type=f"gallery_access_{decision}",
        title=(
            "Gallery access approved"
            if decision == "approved"
            else "Gallery access request declined"
        ),
        body=(
            "Your gallery access request was approved."
            if decision == "approved"
            else "Your gallery access request was declined."
        ),
        data={
            "gallery_id": gallery_id,
            "request_id": request_id,
            "decision": decision,
        },
    )

    return {
        "success": True,
        "request": result,
    }


# ---------------------------------------------------------
# INVITATIONS
# ---------------------------------------------------------

@router.get("/projects/{project_id}/gallery/invitations")
def listProjectGalleryInvitations(
    project_id: int,
    user=Depends(getCurrentLocalUser),
):
    gallery_id = _requireGalleryOwnerForProject(project_id, user["id"])

    return {
        "success": True,
        "invitations": getGalleryInvitations(gallery_id),
    }


@router.delete(
    "/projects/{project_id}/gallery/invitations/{invitation_id}"
)
def deleteProjectGalleryInvitation(
    project_id: int,
    invitation_id: int,
    user=Depends(getCurrentLocalUser),
):
    gallery_id = _requireGalleryOwnerForProject(project_id, user["id"])

    revoked = revokeGalleryInvitation(
        gallery_id=gallery_id,
        invitation_id=invitation_id,
    )

    if not revoked:
        raise HTTPException(
            status_code=404,
            detail="Pending invitation not found",
        )

    return {
        "success": True,
        "message": "Invitation revoked",
    }


# ---------------------------------------------------------
# DEVICE TOKENS
# ---------------------------------------------------------

@router.post("/notifications/device-token")
def registerMyDeviceToken(
    request: DeviceTokenRequest,
    user=Depends(getCurrentLocalUser),
):
    try:
        registerDeviceToken(
            user_id=user["id"],
            token=request.token,
            platform=request.platform,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    return {"success": True}


@router.delete("/notifications/device-token")
def unregisterMyDeviceToken(
    request: DeviceTokenRequest,
    user=Depends(getCurrentLocalUser),
):
    removed = removeDeviceToken(
        user_id=user["id"],
        token=request.token,
    )

    return {
        "success": True,
        "removed": removed,
    }


# ---------------------------------------------------------
# IN-APP NOTIFICATIONS
# ---------------------------------------------------------

@router.get("/notifications")
def listMyNotifications(
    limit: int = 50,
    user=Depends(getCurrentLocalUser),
):
    return {
        "success": True,
        "notifications": getUserNotifications(
            user_id=user["id"],
            limit=limit,
        ),
    }


@router.patch("/notifications/{notification_id}/read")
def markMyNotificationRead(
    notification_id: int,
    user=Depends(getCurrentLocalUser),
):
    updated = markUserNotificationRead(
        user_id=user["id"],
        notification_id=notification_id,
    )

    if not updated:
        raise HTTPException(
            status_code=404,
            detail="Notification not found or already read",
        )

    return {
        "success": True,
        "notification_id": notification_id,
        "read": True,
    }
