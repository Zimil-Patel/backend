import tempfile
from pathlib import Path

import numpy as np

from app.database import getConnection
from app.face_engine import detectFaces
from app.face_matcher import (
    cosineSimilarity,
    getAllFacesClusters,
)

MATCH_THRESHOLD = 0.6


def searchSelfie(selfie_bytes: bytes, project_id: int):

    temporary_file = tempfile.NamedTemporaryFile(
        suffix=".jpg",
        delete=False,
    )

    temporary_path = Path(temporary_file.name)

    try:
        # Write the uploaded selfie into the temporary file.
        temporary_file.write(selfie_bytes)

        temporary_file.close()

        # -------------------------------------------------
        # DETECT FACES IN SELFIE
        # -------------------------------------------------

        detected_faces = detectFaces(str(temporary_path))

        face_count = len(detected_faces)

        # No face was found.
        if face_count == 0:
            return {
                "success": False,
                "reason": "NO_FACE",
                "message": ("No face was detected. Please take another photo."),
            }

        if face_count > 1:
            return {
                "success": False,
                "reason": "MULTIPLE_FACES",
                "message": ("Please take a photo that contains only one face."),
            }

        # Exactly one face.
        selfie_face = detected_faces[0]

        # Get the 512-dimensional embedding.
        selfie_embedding = selfie_face["embedding"]

        clusters = getAllFacesClusters()

        if not clusters:
            return {
                "success": False,
                "reason": "NO INDEXED FACES",
                "message": "No face clusters are available yet.",
            }

        best_cluster_id = None
        best_similarity = -1.0

        for row in clusters:
            cluster_id = row[0]
            embedding_bytes = row[1]

            representative_embedding = np.frombuffer(embedding_bytes, dtype=np.float32)

            similarity = cosineSimilarity(
                selfie_embedding,
                representative_embedding,
            )

            print(f"Selfie similarity → Cluster {cluster_id}: {similarity:.4f}")

            if similarity > best_similarity:
                best_similarity = similarity
                best_cluster_id = cluster_id

        if best_similarity < MATCH_THRESHOLD:
            return {
                "success": False,
                "reason": "NO_MATCH",
                "message": ("We could not find a matching person in this project."),
                "similarity": round(
                    best_similarity,
                    4,
                ),
            }

        cursor = getConnection().cursor()

        cursor.execute(
            """
                SELECT DISTINCT 
                    p.id,
                    p.filename,
                    p.status,
                    p.created_at

                FROM face_cluster_members AS fcm

                JOIN faces AS f
                    ON f.id = fcm.face_id

                JOIN photos AS p
                    ON p.id = f.photo_id

                JOIN events AS e
                    ON e.id = p.event_id

                WHERE fcm.cluster_id = ?
                    AND e.project_id = ?

                ORDER BY p.id ASC
            """,
            (
                best_cluster_id,
                project_id,
            ),
        )

        photos_row = cursor.fetchall()

        cursor.connection.close()

        photos = []

        for row in photos_row:
            photos.append(
                {
                    "id": row[0],
                    "filename": row[1],
                    "status": row[2],
                    "create_at": row[3],
                }
            )

        return {
            "success": True,
            "cluster_id": best_cluster_id,
            "photos_count": len(photos),
            "photos": photos,
        }

    finally:
        if temporary_path.exists():
            temporary_path.unlink()
