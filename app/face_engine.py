from pathlib import Path

import cv2
import insightface

##print("Loading face AI Model...")

face_model = insightface.app.FaceAnalysis(
    name="buffalo_l",
    providers=["CPUExecutionProvider"],
)

face_model.prepare(
    ctx_id=0,
    det_size=(640, 640),
)

##print("Face id model loaded")


def detectFaces(file_path: str):

    ##print(f"Loading image: {file_path}")

    image_path = Path(file_path)

    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {file_path}")

    image = cv2.imread(image_path)

    if image is None:
        raise ValueError(f"Could not load image: {file_path}")

    ##print("Running face detection...")

    detected_faces = face_model.get(image)

    ##print(f"Faces detected: {len(detected_faces)}")

    results = []

    for face_index, face in enumerate(detected_faces, start=1):
        bbox = face.bbox.tolist()

        detection_score = float(face.det_score)

        embedding = face.embedding

        ##print()
        ##print(f"Face {face_index}")

        ##print("Bounding box:", bbox)

        ##print("Detection score:", detection_score)

        ##print("Embedding dimensions:", len(embedding))

        results.append(
            {
                "face_index": face_index,
                "bbox": bbox,
                "detection_score": detection_score,
                "embedding": embedding,
            }
        )

    return results
