import ast
from pathlib import Path

from PIL import Image, ImageOps

from pillow_heif import register_heif_opener
register_heif_opener()


# ---------------------------------------------------------
# CREATE FACE THUMBNAIL
# ---------------------------------------------------------
#
# This function creates a thumbnail and saves it to disk.
#
# We do this during photo processing, NOT every time the
# client requests the thumbnail.
def createFaceThumbnail(
    file_path: str,
    bbox: str,
    output_path: str,
):
    """
    Create and save a face thumbnail.

    Parameters:
        file_path:
            Original photograph path.

        bbox:
            Stored face bounding box.

        output_path:
            Where the generated thumbnail should be saved.
    """

    # Convert the original path to a Path object.
    image_path = Path(file_path)

    # Make sure the original photo exists.
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {file_path}")

    # Convert the stored bbox text back into coordinates.
    # ---------------------------------------------------------

    # NORMALIZE BOUNDING BOX
    # ---------------------------------------------------------
    #
    # Depending on where this function is called from,
    # bbox may already be a Python list OR it may be a string
    # read from SQLite.
    #
    # We support both formats.

    if isinstance(bbox, str):
        # SQLite currently stores bbox as text.
        coordinates = ast.literal_eval(bbox)

    else:
        # The bbox is already a Python list/tuple.
        coordinates = bbox

    # A bbox must contain:
    #
    # left, top, right, bottom
    if len(coordinates) != 4:
        raise ValueError("Bounding box must contain left, top, right, bottom")

    left, top, right, bottom = coordinates

    # Open the original image.
    image = Image.open(image_path)

    # IMPORTANT:
    #
    # Normalize EXIF orientation before using the stored
    # bounding-box coordinates.
    #
    # This fixes the rotation/coordinate problem we found
    # with your camera JPGs.
    image = ImageOps.exif_transpose(image)

    # -----------------------------------------------------
    # FACE SIZE
    # -----------------------------------------------------

    face_width = right - left
    face_height = bottom - top

    # -----------------------------------------------------
    # MARGINS
    # -----------------------------------------------------
    #
    # More room above the face preserves hair.
    # Less room below reduces clothing.

    top_margin = face_height * 0.35

    bottom_margin = face_height * 0.15

    side_margin = face_width * 0.20

    # Expand the original face bounding box.
    crop_left = left - side_margin
    crop_top = top - top_margin
    crop_right = right + side_margin
    crop_bottom = bottom + bottom_margin

    # -----------------------------------------------------
    # KEEP INSIDE IMAGE
    # -----------------------------------------------------

    crop_left = max(
        0,
        crop_left,
    )

    crop_top = max(
        0,
        crop_top,
    )

    crop_right = min(
        image.width,
        crop_right,
    )

    crop_bottom = min(
        image.height,
        crop_bottom,
    )

    # -----------------------------------------------------
    # CROP
    # -----------------------------------------------------

    face_crop = image.crop(
        (
            int(crop_left),
            int(crop_top),
            int(crop_right),
            int(crop_bottom),
        )
    )

    # Convert to RGB so JPEG output is reliable.
    if face_crop.mode != "RGB":
        face_crop = face_crop.convert("RGB")

    # -----------------------------------------------------
    # RESIZE
    # -----------------------------------------------------

    face_crop.thumbnail((300, 300))

    # -----------------------------------------------------
    # CREATE OUTPUT DIRECTORY
    # -----------------------------------------------------

    thumbnail_path = Path(output_path)

    thumbnail_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # -----------------------------------------------------
    # SAVE THUMBNAIL
    # -----------------------------------------------------

    face_crop.save(
        thumbnail_path,
        format="JPEG",
        quality=85,
    )

    # #print(f"Face thumbnail saved: {thumbnail_path}")

    # Return the final path so the caller can store it.
    return str(thumbnail_path.resolve())


def createPhotoThumbnail(
    file_path: str,
    output_path: str,
    max_size: tuple[int, int] = (600, 600),
):
    """
    Create a smaller JPEG thumbnail for a normal photo.

    The original photo is never modified.

    max_size controls the maximum width and height
    of the generated thumbnail.
    """

    image_path = Path(file_path)

    if not image_path.exists():
        raise FileNotFoundError(
            f"Photo not found: {file_path}"
        )

    # Open the original image.
    image = Image.open(image_path)

    # Respect the camera's EXIF orientation.
    image = ImageOps.exif_transpose(image)

    # Convert to RGB so the thumbnail can always be saved as JPEG.
    if image.mode != "RGB":
        image = image.convert("RGB")

    # Reduce the image while keeping its aspect ratio.
    image.thumbnail(max_size)

    # Make sure the output directory exists.
    output_file = Path(output_path)
    output_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Save the smaller image.
    image.save(
        output_file,
        format="JPEG",
        quality=82,
        optimize=True,
    )

    return str(output_file)

def getPhotoDimensions(file_path: str):
    """
    Get the photo dimensions after applying EXIF orientation.

    Some cameras/phones store a portrait photo as landscape pixel
    dimensions and use EXIF orientation to tell viewers to rotate it.

    We apply the EXIF orientation first so the width and height
    stored in the database represent the way the photo is actually
    displayed.
    """
    image_path = Path(file_path)

    if not image_path.exists():
        raise FileNotFoundError(
            f"Photo not found: {file_path}"
        )

    with Image.open(image_path) as image:
        # Apply EXIF orientation before reading dimensions.
        oriented_image = ImageOps.exif_transpose(image)

        return (
            oriented_image.width,
            oriented_image.height,
        )