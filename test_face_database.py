import numpy as np

from app.database import getConnection, saveFace

TEST_PHOTO_ID = 2


def main():

    print("Creating face test embedding")

    embedding = np.random.rand(512).astype(np.float32)

    print(f"Original embedding: {len(embedding)}")

    embedding_bytes = embedding.tobytes()

    print(f"embedding bytes: {len(embedding_bytes)}")

    bbox = "[100, 100, 500, 500]"

    detection_score = 0.95

    face_id = saveFace(
        photo_id=TEST_PHOTO_ID,
        face_index=1,
        bbox=bbox,
        detection_score=detection_score,
        embedding=embedding_bytes,
    )

    print(f"Original embedding: {len(embedding)}")

    connection = getConnection()

    cursor = connection.cursor()

    cursor.execute(
        """
            SELECT id,photo_id,face_index,bbox, detection_score,embedding FROM faces WHERE id = ?
        """,
        (face_id,),
    )

    row = cursor.fetchone()

    if row is None:
        print("ERROR: Face was not found in database.")

        return

    print()
    print("Face retrieved from database:")

    print("Face ID:", row[0])

    print("Photo ID:", row[1])

    print("Face index:", row[2])

    print("Bounding box:", row[3])

    print("Detection score:", row[4])

    restored_embedding = np.frombuffer(
        row[5],
        dtype=np.float32,
    )

    print()
    print("Restored embedding dimensions:", len(restored_embedding))

    same = np.array_equal(
        embedding,
        restored_embedding,
    )

    print("Embedding restored correctly:", same)


if __name__ == "__main__":
    main()
