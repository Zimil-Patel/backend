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
    updateUserPhotoUrl
)

from .gallery_db import (
    createGallery,
    getGalleryByProjectId,
    getGalleryBytoken,
    setGalleryEnabled,
    ensureGalleryCreatorIsOwner,
    isGalleryOwner,
    addOrUpdatGalleryMember,
    linkPendingGalleryInvitations,
    getGalleriesForUser,
    getGalleryMemberRole,
    getGalleryMembers,
    updateGalleryMemberRole,
    removeGalleryMember,
)

from .sharing_db import (
    createGalleryShareLink,
    getGalleryShareLink,
    getGalleryShareLinks,
    revokeGalleryShareLink,
    createGalleryAccessRequest,
    getGalleryAccessRequests,
    resolveGalleryAccessRequest,
    createGalleryInvitation,
    getGalleryInvitations,
    revokeGalleryInvitation,
    registerDeviceToken,
    removeDeviceToken,
    createUserNotification,
    getUserNotifications,
    markUserNotificationRead,
    linkPendingGalleryInvitationsForUser
)