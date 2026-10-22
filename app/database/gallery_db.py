import secrets
from datetime import datetime

from app.database.connection import getConnection


def removeGalleryMember(
    gallery_id: int,
    member_id: int,
    current_user_id: int,
    admin_override: bool = False,
):
    """
    Remove a member or pending invitation from a gallery.

    Prevents Owners from removing themselves and prevents
    removal of the last Owner.
    """

    connection = getConnection()

    try:
        cursor = connection.cursor()

        # Start a write transaction before checking membership
        # and Owner counts to avoid concurrent conflicting changes.
        cursor.execute("BEGIN IMMEDIATE")

        # Find the specific membership within the requested gallery.
        cursor.execute(
            """
            SELECT
                id,
                gallery_id,
                email,
                user_id,
                role
            FROM client_gallery_members
            WHERE id = ? AND gallery_id = ?
            """,
            (member_id, gallery_id),
        )

        member = cursor.fetchone()

        if member is None:
            connection.rollback()
            return {"status": "not_found"}

        if (
            member[3] == current_user_id
            and not admin_override
        ):
            connection.rollback()
            return {"status": "self_removal"}

        # Protect the last Owner from being removed.
        if member[4] == "owner" and not admin_override:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM client_gallery_members
                WHERE gallery_id = ?
                  AND role = 'owner'
                """,
                (gallery_id,),
            )

            owner_count = cursor.fetchone()[0]

            if owner_count <= 1:
                connection.rollback()
                return {"status": "last_owner"}

        # Delete only this gallery membership.
        # The user's local account remains untouched.
        cursor.execute(
            """
            DELETE FROM client_gallery_members
            WHERE id = ? AND gallery_id = ?
            """,
            (member_id, gallery_id),
        )

        connection.commit()

        return {
            "status": "ok",
            "member": {
                "id": member[0],
                "gallery_id": member[1],
                "email": member[2],
                "user_id": member[3],
                "role": member[4],
            },
        }

    finally:
        connection.close()

def updateGalleryMemberRole(
    gallery_id: int,
    member_id: int,
    role: str,
    current_user_id: int,
):
    """
    Change a gallery membership's role.

    Prevents self-demotion and prevents demoting the last Owner.
    Uses a write transaction so concurrent changes cannot both
    pass the last-Owner check.
    """

    connection = getConnection()

    try:
        cursor = connection.cursor()

        # Lock the SQLite write transaction before checking Owner count.
        cursor.execute("BEGIN IMMEDIATE")

        # Find the membership by its membership ID and gallery ID.
        cursor.execute(
            """
            SELECT id, gallery_id, email, user_id, role
            FROM client_gallery_members
            WHERE id = ? AND gallery_id = ?
            """,
            (member_id, gallery_id),
        )

        member = cursor.fetchone()

        if member is None:
            connection.rollback()
            return {"status": "not_found"}

        # Do not allow the acting Owner to demote themselves.
        if member[3] == current_user_id and role != "owner":
            connection.rollback()
            return {"status": "self_demotion"}

        # Do not allow the last Owner to lose Owner status.
        if member[4] == "owner" and role != "owner":
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM client_gallery_members
                WHERE gallery_id = ? AND role = 'owner'
                """,
                (gallery_id,),
            )

            owner_count = cursor.fetchone()[0]

            if owner_count <= 1:
                connection.rollback()
                return {"status": "last_owner"}

        # Update only the requested membership's role.
        cursor.execute(
            """
            UPDATE client_gallery_members
            SET role = ?, updated_at = ?
            WHERE id = ? AND gallery_id = ?
            """,
            (
                role,
                datetime.now().isoformat(),
                member_id,
                gallery_id,
            ),
        )

        connection.commit()

        return {
            "status": "ok",
            "member": {
                "id": member[0],
                "gallery_id": member[1],
                "email": member[2],
                "user_id": member[3],
                "role": role,
            },
        }

    finally:
        connection.close()

def generateGalleryToken() -> str:
    """
    Generate a unique token for a gallery.

    Example: /gallery/a8F2kLm9Pq...
    """

    return secrets.token_urlsafe(24)  # Generates a URL-safe token of 24 bytes


def createGallery(project_id: int, created_by_user_id: int | None = None):

    connection = getConnection()

    cursor = connection.cursor()

    share_token = generateGalleryToken()

    now = datetime.now().isoformat()

    cursor.execute(
        """
        INSERT INTO client_galleries (
            project_id,
            share_token,
            is_enabled,
            created_by_user_id,
            created_at,
            updated_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            project_id,
            share_token,
            1,  # is_enabled
            created_by_user_id,
            now,
            now,
        ),
    )

    connection.commit()

    gallery_id = cursor.lastrowid

    connection.close()

    return gallery_id


def getGalleryByProjectId(project_id: int):

    connection = getConnection()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT 
         id,
         project_id,
         share_token,
         is_enabled,
         created_by_user_id,
         created_at,
         updated_at
         FROM client_galleries
            WHERE project_id = ?
        """,
        (project_id,),
    )

    gallery = cursor.fetchone()

    connection.close()

    return gallery


def getGalleryBytoken(share_token: str):

    connection = getConnection()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT 
         id,
         project_id,
         share_token,
         is_enabled,
         created_by_user_id,
         created_at,
         updated_at
         FROM client_galleries
            WHERE share_token = ?
        """,
        (share_token,),
    )

    gallery = cursor.fetchone()

    connection.close()

    return gallery


def setGalleryEnabled(
    gallery_id: int,
    is_enabled: bool,
):

    connection = getConnection()

    cursor = connection.cursor()

    now = datetime.now().isoformat()

    cursor.execute(
        """
        UPDATE client_galleries
        SET is_enabled = ?, 
        updated_at = ?
        WHERE id = ?
        """,
        (
            1 if is_enabled else 0,
            now,
            gallery_id,
        ),
    )

    connection.commit()

    updated = cursor.rowcount > 0

    connection.close()

    return updated


def ensureGalleryCreatorIsOwner(gallery_id: int) -> bool:

    connection = getConnection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
                SELECT 
                    client_galleries.created_by_user_id,
                    users.email
                FROM client_galleries
                JOIN users
                    ON users.id = client_galleries.created_by_user_id
                WHERE client_galleries.id = ?
            """,
            (gallery_id,),
        )

        creator = cursor.fetchone()

        if creator is None or not creator[1] or not creator[1].strip():
            return False

        user_id = creator[0]
        email = creator[1].strip()
        now = datetime.now().isoformat()

        cursor.execute(
            """
                INSERT INTO client_gallery_members (
                    gallery_id,
                    email,
                    user_id,
                    role,
                    invited_by_user_id,
                    created_at,
                    updated_at
                )

                VALUES (?, ?, ? , 'owner', ?, ?, ?)

                ON CONFLICT (gallery_id, email)
                DO UPDATE SET
                    user_id = excluded.user_id,
                    role = 'owner',
                    updated_at = excluded.updated_at
            """,
            (
                gallery_id,
                email,
                user_id,
                user_id,
                now,
                now,
            ),
        )

        connection.commit()
        return True

    finally:
        connection.close()


def isGalleryOwner(gallery_id: int, user_id: int):

    connection = getConnection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
                    SELECT 1
                    FROM client_gallery_members
                        WHERE gallery_id = ?
                        AND user_id = ?
                        AND role = 'owner'
                    LIMIT 1
                """,
            (gallery_id, user_id),
        )

        return cursor.fetchone() is not None

    finally:
        connection.close()


def addOrUpdatGalleryMember(gallery_id: int, email: str, role: str, invited_by_user_id: int):

    email = email.strip().lower()
    now = datetime.now().isoformat()

    connection = getConnection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
                SELECT id FROM users
                    WHERE email COLLATE NOCASE = ?
                    LIMIT 1
            """,
            (email,),
        )

        existing_user = cursor.fetchone()

        receipient_user_id = (
            existing_user[0]
            if existing_user is not None
            else None
        )

        cursor.execute(
            """
                INSERT INTO client_gallery_members (
                    gallery_id,
                    email,
                    user_id,
                    role,
                    invited_by_user_id,
                    created_at,
                    updated_at
                )

                VALUES (?, ?, ?, ?, ?, ?, ?)

                ON CONFLICT (gallery_id, email)
                DO UPDATE SET
                    user_id = COALESCE(
                        excluded.user_id,
                        client_gallery_members.user_id
                    ),
                    role = excluded.role,
                    invited_by_user_id = excluded.invited_by_user_id,
                    updated_at = excluded.updated_at

            """,
            (
                gallery_id, email, receipient_user_id, role, invited_by_user_id, now, now,
            ),
        )

        connection.commit()

        cursor.execute(
            """
                SELECT 
                    id,
                    gallery_id,
                    email,
                    user_id,
                    role,
                    invited_by_user_id,
                    created_at,
                    updated_at
                FROM client_gallery_members
                WHERE gallery_id = ?
                    AND email = ?
            """,
            (gallery_id, email,),
        )

        member = cursor.fetchone()

        return {
            "id": member[0],
            "gallery_id": member[1],
            "email": member[2],
            "user_id": member[3],
            "role": member[4],
            "invited_by_user_id": member[5],
            "created_at": member[6],
            "updated_at": member[7],
        }

    finally: 
        connection.close()

def linkPendingGalleryInvitations(
        user_id: int,
        email: str
):

    email = email.strip().lower()

    if not email:
        return 0

    connection = getConnection()
    try: 
        cursor = connection.cursor()

        now = datetime.now().isoformat()

        cursor.execute(
            """
                UPDATE client_gallery_members
                    SET user_id = ?,
                    updated_at = ? 
                WHERE 
                    email COLLATE NOCASE = ? 
                    AND user_id IS NULL
            """,
            (user_id,now,email,),
        )

        connection.commit()

        return cursor.rowcount
    finally:
        connection.close()


def getGalleriesForUser(user_id: int):

    connection = getConnection()

    try:
        cursor = connection.cursor()

        print(f"USER ID: {user_id}")

        cursor.execute(
            """
            SELECT
                g.id,
                g.project_id,
                p.name,
                m.role,
                g.is_enabled,
                g.created_at,
                g.updated_at
            FROM client_gallery_members AS m
            INNER JOIN client_galleries AS g
                ON g.id = m.gallery_id
            INNER JOIN projects AS p
                ON p.id = g.project_id
            WHERE m.user_id = ? AND g.is_enabled = ?
            ORDER BY g.created_at DESC, g.id DESC
            """,
            (user_id, 1),
        )

        rows = cursor.fetchall()

        print(rows)

        return [
            {
                "id": row[0],
                "project_id": row[1],
                "project_name": row[2],
                "role": row[3],
                "is_enabled": row[4],
                "created_at": row[5],
                "updated_at": row[6],
            }
            for row in rows
        ]

    finally:
        connection.close()

def getGalleryMemberRole(
    gallery_id: int,
    user_id: int
) -> str | None:

    connection = getConnection()

    try:

        cursor = connection.cursor()

        cursor.execute(
            """
                SELECT role
                    FROM client_gallery_members
                    WHERE gallery_id = ?
                        AND user_id = ?
                    LIMIT 1
            """,
            (gallery_id, user_id,),
        )

        row = cursor.fetchone()

        return row[0] if row else None

    finally:
        connection.close()

def getGalleryMembers(gallery_id: int):

    connection = getConnection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
                SELECT
                    m.id,
                    m.gallery_id,
                    m.email,
                    m.user_id,
                    m.role,
                    m.invited_by_user_id,
                    m.created_at,
                    m.updated_at,
                    users.id,
                    users.first_name,
                    users.last_name,
                    users.photo_url
                FROM client_gallery_members AS m
                LEFT JOIN users
                    ON users.id = m.user_id
                WHERE m.gallery_id = ?
                ORDER BY
                    CASE m.role
                        WHEN 'owner' THEN 0
                        ELSE 1
                    END,
                    LOWER(m.email) ASC
            """,
            (gallery_id,),
        )

        rows = cursor.fetchall()

        members = []

        for row in rows:
            is_registered = row[8] is not None

            full_name = (
                f"{row[9] or ''} {row[10] or ''}".strip()
                if is_registered
                else ""
            )

            members.append(
                {
                    "id": row[0],
                    "gallery_id": row[1],
                    "email": row[2],
                    "user_id": row[3],
                    "role": row[4],
                    "invited_by_user_id": row[5],
                    "created_at": row[6],
                    "updated_at": row[7],
                    "is_registered": is_registered,
                    "first_name": row[9],
                    "last_name": row[10],
                    "full_name": full_name or None,
                    "photo_url": row[11],
                }
            )

        return members


    finally:
        connection.close()