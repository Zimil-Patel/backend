import ast
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

from app.database import getConnection

FACE_ID = 29


def main():

    connection = getConnection()
    cursor = connection.cursor()

    # Find the original photo and bounding box for Face 29.
    cursor.execute(
        """
        SELECT
            faces.photo_id,
            faces.bbox,
            photos.file_path
        FROM faces
        JOIN photos
            ON photos.id = faces.photo_id
        WHERE faces.id = ?
        """,
        (FACE_ID,),
    )

    row = cursor.fetchone()

    connection.close()

    if row is None:
        print(f"Face {FACE_ID} not found")
        return

    photo_id = row[0]
    bbox_text = row[1]
    file_path = Path(row[2])

    print(f"Face ID: {FACE_ID}")
    print(f"Photo ID: {photo_id}")
    print(f"Photo: {file_path}")
    print(f"BBox: {bbox_text}")

    # Open the original photo.
    image = Image.open(file_path)

    image = ImageOps.exif_transpose(image)

    print(f"Image size: {image.width} x {image.height}")

    # Convert bbox text back into Python values.
    left, top, right, bottom = ast.literal_eval(bbox_text)

    print(
        "BBox coordinates:",
        left,
        top,
        right,
        bottom,
    )

    # Draw a red rectangle around the stored face location.
    draw = ImageDraw.Draw(image)

    draw.rectangle(
        (
            int(left),
            int(top),
            int(right),
            int(bottom),
        ),
        outline="red",
        width=20,
    )

    # Save debug image in the backend folder.
    output_path = Path("debug_face_29.jpg")

    image.save(
        output_path,
        format="JPEG",
        quality=90,
    )

    print(f"Debug image saved: {output_path.resolve()}")


if __name__ == "__main__":
    main()
