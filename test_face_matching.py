# ---------------------------------------------------------
# FACE MATCHING TEST
# ---------------------------------------------------------

import numpy as np

from app.database import getConnection
from app.face_matcher import (
    assignFaceToCluster,
)


def main():

    connection = getConnection()

    cursor = connection.cursor()

    # Get every face currently stored in SQLite.
    cursor.execute(
        """
        SELECT
            id,
            embedding
        FROM faces
        ORDER BY id
        """
    )

    faces = cursor.fetchall()

    connection.close()

    print(f"Faces found in database: {len(faces)}")

    # Process every detected face.
    for face_id, embedding_bytes in faces:
        print()
        print("--------------------------------")

        print(f"Processing Face ID: {face_id}")

        # Convert SQLite BLOB back to NumPy.
        embedding = np.frombuffer(
            embedding_bytes,
            dtype=np.float32,
        )

        print("Embedding dimensions:", len(embedding))

        # Assign this face to the most appropriate
        # person cluster.
        cluster_id = assignFaceToCluster(
            face_id=face_id,
            embedding=embedding,
        )

        print(f"Face {face_id} → Cluster {cluster_id}")


if __name__ == "__main__":
    main()
