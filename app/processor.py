import queue
import threading
from pathlib import Path

from app.database import (
    deleteFacesForPhoto,
    saveFace,
    updateFaceThumbnailPath,
    updatePhotoStatus,
    updatePhotoThumbnailPath
)
from app.face_engine import detectFaces
from app.face_matcher import assignFaceToCluster
from app.services.image_service import createFaceThumbnail, createPhotoThumbnail

photo_queue = queue.Queue()


# add photo to processing queue
def addPhotoJob(photo_id: int, file_path: str):
    photo_queue.put(
        {
            "photo_id": photo_id,
            "file_path": file_path,
        }
    )

    #print(f"Added photo {photo_id} to processing queue")


# process one by one photo from queue
def processPhoto(photo_id: int, file_path: str):

    #print(f"Processing photo {photo_id}: {file_path}")

    try:
        updatePhotoStatus(photo_id, "PROCESSING")

        if not Path(file_path).exists():
            raise FileNotFoundError(f"Photo no longer exists: {file_path}")

        deleteFacesForPhoto(photo_id)

        faces = detectFaces(file_path)

        # -------------------------------------------------
        # CREATE PHOTO THUMBNAIL
        # -------------------------------------------------

        photo_thumbnail_path = (
            Path(__file__).resolve().parent.parent
            / "data"
            / "photo_thumbnails"
            / f"photo_{photo_id}.jpg"
        )

        saved_photo_thumbnail_path = createPhotoThumbnail(
            file_path=file_path,
            output_path=str(photo_thumbnail_path),
        )

        updatePhotoThumbnailPath(
            photo_id=photo_id,
            thumbnail_path=saved_photo_thumbnail_path,
        )

        #print(f"Photo {photo_id}: {len(faces)} faces detected")

        for face in faces:
            face_index = face["face_index"]
            bbox = face["bbox"]
            detection_score = face["detection_score"]
            embedding = face["embedding"]

            embedding_bytes = embedding.tobytes()

            bbox_text = str(bbox)

            face_id = saveFace(
                photo_id=photo_id,
                face_index=face_index,
                bbox=bbox_text,
                detection_score=detection_score,
                embedding=embedding_bytes,
            )

            if face_id is None:
                continue

            thumbnail_path = (
                Path(__file__).resolve().parent.parent
                / "data"
                / "face_thumbnails"
                / f"face_{face_id}.jpg"
            )

            saved_thumbnail_path = createFaceThumbnail(
                file_path=file_path, bbox=bbox, output_path=str(thumbnail_path)
            )

            updateFaceThumbnailPath(
                face_id=face_id, thumbnail_path=saved_thumbnail_path
            )

            cluster_id = assignFaceToCluster(face_id=face_id, embedding=embedding)
            #print(f"Face {face_id} → Cluster {cluster_id}")

        updatePhotoStatus(photo_id, "COMPLETED")

        ##print(f"Finished photo {photo_id}")

    except Exception as error:
        updatePhotoStatus(photo_id, "FAILED")

        print(f"Failed photo {photo_id}: {error}")


# actual worker
def worker():

    #print("Photo processing worker started")

    while True:
        try:
            job = photo_queue.get()

            photo_id = job["photo_id"]
            file_path = job["file_path"]

            processPhoto(photo_id, file_path)

        finally:
            photo_queue.task_done()


# start worker processing in background thread


def startWorker():

    worker_thread = threading.Thread(target=worker, daemon=True, name="PhotoProcessor")

    worker_thread.start()

    return worker_thread
