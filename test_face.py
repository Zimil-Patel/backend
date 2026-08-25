# Import our face detection test function.
from app.face_engine.detector import testImage

# ---------------------------------------------------------
# CHANGE THIS PATH
# ---------------------------------------------------------

# Put the path of ONE real photograph from your shoot here.
#
# We are using a direct path for this first test.
# Later the processing worker will provide this automatically.
IMAGE_PATH = (
    "/Users/buddy/Documents/photo_server/"
    "photo_storage/projects/test_wed/haldi/"
    "2E6A9889.JPG"
)


# ---------------------------------------------------------
# RUN TEST
# ---------------------------------------------------------

if __name__ == "__main__":
    # Run face detection on our test photograph.
    testImage(IMAGE_PATH)
