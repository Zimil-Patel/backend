import numpy as np

from app.database import addFaceToCluster, createFaceCluster, getAllFacesClusters

MATCH_THRESHOLD = 0.60


# calculate cosine (THRESHOLD)
def cosineSimilarity(embedding_a, embedding_b):

    a = np.asarray(embedding_a, dtype=np.float32)

    b = np.asarray(embedding_b, dtype=np.float32)

    dot_product = np.dot(a, b)

    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return float(dot_product / (norm_a * norm_b))


# find beset cluster id
def findBestCluster(embedding: bytes):

    clusters = getAllFacesClusters()

    if not clusters:
        return None, 0.0

    best_cluster_id = None

    best_similarity = -1.0

    for row in clusters:
        cluster_id = row[0]

        embedding_bytes = row[1]

        representative = np.frombuffer(embedding_bytes, dtype=np.float32)

        similarity = cosineSimilarity(embedding, representative)

        # print(f"Face similarity → Cluster {cluster_id}: {similarity:.4f}")

        if similarity > best_similarity:
            best_cluster_id = cluster_id
            best_similarity = similarity

#     print(
#     f"BEST CLUSTER → "
#     f"{best_cluster_id} "
#     f"similarity={best_similarity:.4f}"
# )

    if best_similarity < MATCH_THRESHOLD:
        return None, best_similarity

    return best_cluster_id, best_similarity


# assign face to particular similar cluster


def assignFaceToCluster(face_id: int, embedding):

    cluster_id, similarity = findBestCluster(embedding)

    if cluster_id is not None:
        # print(
        #     f"Face {face_id} matched "
        #     f"Cluster {cluster_id} "
        #     f"(similarity: {similarity:.4f})"
        # )

        addFaceToCluster(face_id=face_id, cluster_id=cluster_id, similarity=similarity)

        return cluster_id

    embedding_bytes = embedding.tobytes()

    cluster_id = createFaceCluster(embedding_bytes)

    addFaceToCluster(
        cluster_id=cluster_id,
        face_id=face_id,
        similarity=1.0,
    )

    return cluster_id
