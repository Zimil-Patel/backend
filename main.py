import time
from pathlib import Path

from app.database import initializeDatabase
from app.watcher import start_watcher

PROJECT_ROOT = Path(__file__).resolve().parent.parent

PHOTO_ROOT = PROJECT_ROOT / "photo_storage" / "projects"


def main():

    print("--------------------------------")
    print("|     Photo server started     |")
    print("--------------------------------")

    initializeDatabase()

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
