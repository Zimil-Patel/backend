# ---------------------------------------------------------
# SPECIFIC FACE MATCH TEST
# ---------------------------------------------------------
#
# This test compares two faces directly from the database.
#
# We are NOT using clusters here.
#
# The goal is to answer:
#
# "Are Face 2 and Face 4 actually similar?"
#
# This helps us verify that the embeddings stored in
# SQLite are correct.
# ---------------------------------------------------------

import numpy as np

from app.database import getConnection
from app.face_matcher import cosineSimilarity


def getFaceEmbedding(face_id: int):
    """
    Get one face's embedding from SQLite.
    """

    connection = getConnection()

    cursor = connection.cursor()

    # Fetch the embedding belonging to this face.
    cursor.execute(
        """
        SELECT embedding
        FROM faces
        WHERE id = ?
        """,
        (face_id,),
    )

    row = cursor.fetchone()

    connection.close()

    # Make sure the requested face actually exists.
    if row is None:
        raise ValueError(f"Face ID {face_id} not found")

    # SQLite stores the embedding as binary data.
    embedding_bytes = row[0]

    # Convert the binary data back into
    # the original 512-dimensional float array.
    embedding = np.frombuffer(
        embedding_bytes,
        dtype=np.float32,
    )

    return embedding


def main():

    # -----------------------------------------------------
    # CHANGE THESE TWO IDs IF NEEDED
    # -----------------------------------------------------

    face_a_id = 2

    face_b_id = 5

    print("Loading Face", face_a_id)

    face_a = getFaceEmbedding(face_a_id)

    print("Loading Face", face_b_id)

    face_b = getFaceEmbedding(face_b_id)

    # -----------------------------------------------------
    # SHOW EMBEDDING INFORMATION
    # -----------------------------------------------------

    print()
    print("================================")
    print("EMBEDDING INFORMATION")
    print("================================")

    print(f"Face {face_a_id} dimensions:", len(face_a))

    print(f"Face {face_b_id} dimensions:", len(face_b))

    # -----------------------------------------------------
    # CALCULATE RAW COSINE SIMILARITY
    # -----------------------------------------------------

    similarity = cosineSimilarity(
        face_a,
        face_b,
    )

    print()
    print("================================")
    print("FACE SIMILARITY")
    print("================================")

    print(f"Face {face_a_id} ↔ Face {face_b_id}")

    print(f"Cosine similarity: {similarity:.4f}")

    # -----------------------------------------------------
    # BASIC INTERPRETATION
    # -----------------------------------------------------

    if similarity >= 0.60:
        print("Result: STRONG MATCH")

    else:
        print("Result: NOT A MATCH")


if __name__ == "__main__":
    main()
