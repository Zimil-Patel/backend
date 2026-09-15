from email.mime import image
import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
from app.services.image_service import getPhotoDimensions

from app.database import (
    calculateFileHash,
    createPhoto,
    getOrCreateEvent,
    getOrCreateProject,
)
from app.processor import addPhotoJob

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic"}


# this function wait until file copying finish
def waitUntilFileCopyFinish(file_path: Path, checks: int = 2, wait_seconds: int = 1):
    """
    Wait until the file size stays the same.

    Why do we do this?

    A large photo might still be copying when Watchdog
    tells us that the file exists.

    We don't want to process an incomplete photo.
    """

    previous_size = -1

    stable_count = 0

    while stable_count < checks:
        if not file_path.exists():
            return False

        current_size = file_path.stat().st_size

        #print(f"checking {file_path.name},{current_size:,} bytes")

        if current_size == previous_size:
            stable_count += 1

        else:
            stable_count = 0

        previous_size = current_size

        time.sleep(wait_seconds)

    return True


class PhotoEventHandler(FileSystemEventHandler):
    def on_created(self, event):

        if event.is_directory:
            return

        path = Path(event.src_path)

        extension = path.suffix.lower()

        if extension not in IMAGE_EXTENSIONS:
            return

        #print(f"New photo detected: {path}")

        is_stable = waitUntilFileCopyFinish(path)

        if not is_stable:
            #print(f"File disappeared {path}")
            return

        #print(f"File is ready {path}")

        # handle into sqlite database
        project_name = path.parent.parent.name
        event_name = path.parent.name

        project_id = getOrCreateProject(project_name)

        event_id = getOrCreateEvent(project_id, event_name)

        #print(f"calculating hash: {path.name}")

        file_hash = calculateFileHash(path)

        photo_width, photo_height = getPhotoDimensions(str(path))

        #print(f"calculated hash: {file_hash}")

        # save photo with hash
        photo_id = createPhoto(
            event_id=event_id,
            filename=path.name,
            file_path=str(
                path.resolve(),
            ),
            file_hash=file_hash,
            width=photo_width,
            height=photo_height
        )

        if photo_id is None:
            return

        addPhotoJob(photo_id=photo_id, file_path=str(path.resolve()))


def start_watcher(photo_root: Path):

    photo_root = photo_root.resolve()

    if not photo_root.exists():
        raise RuntimeError(f"Photo directory does not exist: {photo_root}")

    print(f"Watching: {photo_root}")

    event_handler = PhotoEventHandler()

    observer = Observer()
    observer.schedule(
        event_handler,
        str(photo_root),
        recursive=True,
    )

    observer.start()

    return observer
