import queue
import threading
import time
from pathlib import Path

from app.database import updatePhotoStatus

photo_queue = queue.Queue()


# add photo to processing queue
def addPhotoJob(photo_id: int, file_path: str):
    photo_queue.put(
        {
            "photo_id": photo_id,
            "file_path": file_path,
        }
    )

    print(f"Added photo {photo_id} to processing queue")


# process one by one photo from queue
def processPhoto(photo_id: int, file_path: str):

    print(f"Processing photo {photo_id}: {file_path}")

    try:
        updatePhotoStatus(photo_id, "PROCESSING")

        time.sleep(2)

        if not Path(file_path).exists():
            raise FileNotFoundError(f"Photo no longer exists: {file_path}")

        updatePhotoStatus(photo_id, "COMPLETED")

        print(f"Finished photo {photo_id}")

    except Exception as error:
        updatePhotoStatus(photo_id, "FAILED")

        print(f"Failed photo {photo_id}: {error}")


# actual worker
def worker():

    print("Photo processing worker started")

    try:
        while True:
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
