from pathlib import Path

import cv2
import insightface
import numpy as np

from PIL import Image, ImageOps
from pillow_heif import register_heif_opener


# ---------------------------------------------------------
# ENABLE HEIC / HEIF SUPPORT
# ---------------------------------------------------------
#
# This allows Pillow to open .HEIC and .HEIF files.
#
# Normal JPG/JPEG/PNG files will still use OpenCV below.
register_heif_opener()


# ---------------------------------------------------------
# LOAD FACE AI MODEL
# ---------------------------------------------------------

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


# ---------------------------------------------------------
# DETECT FACES
# ---------------------------------------------------------

def detectFaces(file_path: str):

    ##print(f"Loading image: {file_path}")

    image_path = Path(file_path)

    if not image_path.exists():
        raise FileNotFoundError(
            f"Image not found: {file_path}"
        )

    # Get the file extension.
    extension = image_path.suffix.lower()

    # -----------------------------------------------------
    # LOAD HEIC / HEIF WITH PILLOW
    # -----------------------------------------------------
    #
    # OpenCV's cv2.imread() cannot load your HEIC files.
    #
    # Therefore, only HEIC/HEIF files use Pillow.
    if extension in {".heic", ".heif"}:

        image = Image.open(image_path)

        # Respect the camera's EXIF orientation.
        image = ImageOps.exif_transpose(image)

        # Convert to RGB.
        image = image.convert("RGB")

        # Convert Pillow image to NumPy array.
        image = np.array(image)

        # Pillow uses RGB.
        # OpenCV / InsightFace expects BGR.
        image = cv2.cvtColor(
            image,
            cv2.COLOR_RGB2BGR,
        )

    # -----------------------------------------------------
    # EXISTING IMAGE LOADING
    # -----------------------------------------------------
    #
    # Keep the existing OpenCV path for all other formats.
    else:

        image = cv2.imread(
            str(image_path)
        )

    # Make sure the image was loaded successfully.
    if image is None:
        raise ValueError(
            f"Could not load image: {file_path}"
        )

    ##print("Running face detection...")

    detected_faces = face_model.get(image)

    ##print(f"Faces detected: {len(detected_faces)}")

    results = []

    for face_index, face in enumerate(
        detected_faces,
        start=1,
    ):
        bbox = face.bbox.tolist()

        detection_score = float(
            face.det_score
        )

        embedding = face.embedding

        results.append(
            {
                "face_index": face_index,
                "bbox": bbox,
                "detection_score": detection_score,
                "embedding": embedding,
            }
        )

    return results