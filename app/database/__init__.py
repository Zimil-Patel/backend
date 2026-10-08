from .connection import (
    DATABASE_PATH,
    getConnection,
)

from .initialization import initializeDatabase

from .project_db import getOrCreateProject

from .event_db import getOrCreateEvent

from .photo_db import (
    calculateFileHash,
    photoHashExists,
    createPhoto,
    updatePhotoThumbnailPath,
    updatePhotoStatus,
    setPhotoFavouriteStatus,
)

from .face_db import (
    saveFace,
    deleteFacesForPhoto,
    updateFaceThumbnailPath,
)

from .cluster_db import (
    getAllFacesClusters,
    createFaceCluster,
    addFaceToCluster,
    updateClusterRepresentative,
)

from .user_db import (
    getUserByFirebaseUid,
    createUser,
    updateUser,
    syncUser,
)

from .gallery_db import (
    createGallery,
    getGalleryByProjectId,
    getGalleryBytoken,
    setGalleryEnabled,
)