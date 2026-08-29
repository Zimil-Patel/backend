from io import BytesIO
import ast
from pathlib import Path
from PIL import Image



# Create small thumbnail for faces
def createFaceThumbnail(
        file_path: str,
        bbox: str,
):
    image_path = Path(file_path)

    if not image_path.exists():

        raise FileNotFoundError(f"Image not found: {file_path}")

    coordinates = ast.literal_eval(bbox)

    if len(coordinates) != 4:

        raise ValueError(
            "Bounding box must contain"
            "left, top, right, bottom"
        )

    left, top, right, bottom = coordinates

    image = Image.open(image_path)

    face_width = right - left
    face_height = bottom - top

    horizontal_margin = face_width * 0.25
    vertical_margin = face_height * 0.25

    left = left - horizontal_margin
    top = top - vertical_margin
    right = right + horizontal_margin
    bottom = bottom + vertical_margin

    left = max(0, left)
    top = max(0, top)
    right = min(image.width, right)
    bottom = min(image.height, bottom)

    face_crop = image.crop(
        (left, top, right, bottom,)
    )

    if face_crop.mode != "RGB":

        face_crop = face_crop.convert("RGB")

    face_crop.thumbnail(
        (300, 300)
    )

    image_buffer = BytesIO()

    # Save the face crop as JPEG.
    #
    # quality=85 provides a good balance between
    # image quality and response size.
    face_crop.save(
        image_buffer,
        format='JPEG',
        quality = 85,
    )

    image_buffer.seek(0)


    return image_buffer



