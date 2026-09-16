import numpy as np
from datetime import datetime

from app.database.connection import getConnection


def getAllFacesClusters():
    """
    Get all face clusters and their representative embeddings.

    The representative embedding is used when comparing
    a newly detected face against existing clusters.
    """

    connection = getConnection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            id,
            representative_embedding
        FROM face_clusters
        ORDER BY id ASC
        """
    )

    rows = cursor.fetchall()

    connection.close()

    return rows


def createFaceCluster(embedding: bytes):
    """
    Create a new face cluster.

    The first face assigned to a new cluster becomes
    the initial representative embedding.
    """

    connection = getConnection()
    cursor = connection.cursor()

    # SQLite requires both timestamps because the
    # database columns are defined as NOT NULL.
    now = datetime.now().isoformat()

    cursor.execute(
        """
        INSERT INTO face_clusters (
            representative_embedding,
            face_count,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            embedding,
            0,
            now,
            now,
        ),
    )

    connection.commit()

    cluster_id = cursor.lastrowid

    connection.close()

    return cluster_id


def addFaceToCluster(
    cluster_id: int,
    face_id: int,
    similarity: float,
):
    """
    Add a face to a cluster.

    The similarity records how closely the face matched
    the cluster when it was assigned.
    """

    connection = getConnection()
    cursor = connection.cursor()

    # Each cluster member also needs its creation timestamp.
    created_at = datetime.now().isoformat()

    cursor.execute(
        """
        INSERT INTO face_cluster_members (
            cluster_id,
            face_id,
            similarity,
            created_at
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            cluster_id,
            face_id,
            similarity,
            created_at,
        ),
    )

    # Increase the number of faces belonging to this cluster.
    cursor.execute(
        """
        UPDATE face_clusters
        SET face_count = face_count + 1,
            updated_at = ?
        WHERE id = ?
        """,
        (
            created_at,
            cluster_id,
        ),
    )

    connection.commit()

    connection.close()

    # Recalculate the representative after adding
    # the new face to the cluster.
    updateClusterRepresentative(cluster_id)


def updateClusterRepresentative(cluster_id: int):
    """
    Recalculate the representative embedding of a cluster.

    Instead of permanently using the first face as the
    representative, we calculate the normalized mean of
    all embeddings belonging to this cluster.

    This makes clustering less dependent on processing order.
    """

    connection = getConnection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT faces.embedding
        FROM face_cluster_members
        JOIN faces
            ON faces.id = face_cluster_members.face_id
        WHERE face_cluster_members.cluster_id = ?
        """,
        (cluster_id,),
    )

    rows = cursor.fetchall()

    # Nothing to calculate if the cluster has no faces.
    if not rows:
        connection.close()
        return

    # Convert every stored embedding from bytes
    # back into a NumPy float32 array.
    embeddings = []

    for row in rows:
        embedding = np.frombuffer(
            row[0],
            dtype=np.float32,
        )

        embeddings.append(embedding)

    # Calculate the average embedding.
    mean_embedding = np.mean(
        embeddings,
        axis=0,
    )

    # Normalize the representative embedding.
    norm = np.linalg.norm(mean_embedding)

    if norm != 0:
        mean_embedding = mean_embedding / norm

    # Convert the NumPy array back into bytes
    # before storing it in SQLite.
    representative_embedding = mean_embedding.astype(
        np.float32
    ).tobytes()

    # Save the new representative and update the timestamp.
    updated_at = datetime.now().isoformat()

    cursor.execute(
        """
        UPDATE face_clusters
        SET representative_embedding = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            representative_embedding,
            updated_at,
            cluster_id,
        ),
    )

    connection.commit()

    connection.close()