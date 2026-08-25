# ---------------------------------------------------------
# FACE ENGINE TEST
# ---------------------------------------------------------

from app.face_engine import detectFaces

# Use one of our existing wedding photos.
IMAGE_PATH = (
    "/Users/buddy/Documents/photo_server/"
    "photo_storage/projects/test_wed/haldi/"
    "2E6A9889.JPG"
)


def main():

    print("Starting face detection test...")

    # Detect all faces in the image.
    faces = detectFaces(IMAGE_PATH)

    print()
    print("================================")

    print(f"Total faces: {len(faces)}")

    print("================================")

    # Display information about every detected face.
    for face in faces:
        print()

        print("Face:", face["face_index"])

        print("Bounding box:", face["bbox"])

        print("Detection score:", face["detection_score"])

        print("Embedding dimensions:", len(face["embedding"]))


if __name__ == "__main__":
    main()
