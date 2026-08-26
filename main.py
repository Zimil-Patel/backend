import time
from pathlib import Path

from fastapi import FastAPI

from app.api import router
from app.database import initializeDatabase
from app.processor import startWorker
from app.watcher import start_watcher

PROJECT_ROOT = Path(__file__).resolve().parent.parent

PHOTO_ROOT = PROJECT_ROOT / "photo_storage" / "projects"

app = FastAPI(
    title="Stories By Parin Photo server API",
    version="1.0.0",
)

app.include_router(router)


def main():

    print("--------------------------------")
    print("|     Photo server started     |")
    print("--------------------------------")

    initializeDatabase()

    startWorker()

    observer = start_watcher(PHOTO_ROOT)

    try:
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n Stopping photo server...")

        observer.stop()

    observer.join()


if __name__ == "__main__":
    main()
