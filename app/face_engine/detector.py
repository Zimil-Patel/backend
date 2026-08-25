import cv2
from insightface.app import FaceAnalysis


# create face model application
def createFaceEngine():

    print("Loading face AI model...")

    app = FaceAnalysis(name="buffalo_l")

    app.prepare(ctx_id=1)

    print("Face AI model loaded")

    return app


# process image
def detectFaces(app, image_path: str):

    print(f"Loading image: {image_path}")

    image = cv2.imread(image_path)

    if image is None:
        raise ValueError(f"Could not read image: {image_path}")

    print("Running face detection...")

    faces = app.get(image)

    print(f"Faces detected: {len(faces)}")

    return faces


# testing function
def testImage(image_path: str):

    app = createFaceEngine()

    faces = detectFaces(app, image_path)

    for index, face in enumerate(faces):
        print()
        print(f"======== FACE {index + 1} ========")
        print(f"Bounding box: {face.bbox}")
        print(f"Detection score: {face.det_score}")

        if face.embedding is not None:
            print(f"Embedding dimensions: {len(face.embedding)}")
            print("Embedding sample:", face.embedding[:5])

        else:
            print("Embedding: NOT AVAILABLE")

    return faces
