
import json
import secrets
import sqlite3
from datetime import datetime, timezone

from app.database.connection import getConnection


def utcNow() -> datetime:
    """Return the current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def utcNowString() -> str:
    """Return a consistent ISO-8601 UTC timestamp."""
    return utcNow().isoformat()


def parseUtcDateTime(value: str) -> datetime:
    """Parse an ISO timestamp and require an explicit timezone."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("A UTC expiry timestamp is required.")

    parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))

    if parsed.tzinfo is None:
        raise ValueError("Expiry timestamp must include a timezone.")

    return parsed.astimezone(timezone.utc)


def rowToDict(cursor, row):
    """Convert a SQLite row into a dictionary."""
    return {
        description[0]: row[index]
        for index, description in enumerate(cursor.description)
    }


def createGalleryShareLink(
    gallery_id: int,
    created_by_user_id: int,
    expires_at_utc: str,
) -> dict:
    """
    Create a new share link.

    Caller must verify that created_by_user_id is a gallery Owner.
    Every link must have a future expiry timestamp.
    """
    expiry = parseUtcDateTime(expires_at_utc)

    if expiry <= utcNow():
        raise ValueError("Expiry must be in the future.")

    connection = getConnection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            "SELECT id FROM client_galleries WHERE id = ?",
            (gallery_id,),
        )
        if cursor.fetchone() is None:
            return {"status": "gallery_not_found"}

        now = utcNowString()
        token = secrets.token_urlsafe(32)

        cursor.execute(
            """
            INSERT INTO gallery_share_links (
                gallery_id,
                token,
                created_by_user_id,
                expires_at_utc,
                revoked_at_utc,
                created_at_utc
            )
            VALUES (?, ?, ?, ?, NULL, ?)
            """,
            (
                gallery_id,
                token,
                created_by_user_id,
                expiry.isoformat(),
                now,
            ),
        )

        connection.commit()

        return {
            "status": "ok",
            "id": cursor.lastrowid,
            "gallery_id": gallery_id,
            "token": token,
            "created_by_user_id": created_by_user_id,
            "expires_at_utc": expiry.isoformat(),
            "revoked_at_utc": None,
            "created_at_utc": now,
        }

    finally:
        connection.close()


def getGalleryShareLink(token: str) -> dict | None:
    """Return a share link by token, including expired or revoked links."""
    connection = getConnection()

    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT
                id,
                gallery_id,
                token,
                created_by_user_id,
                expires_at_utc,
                revoked_at_utc,
                created_at_utc
            FROM gallery_share_links
            WHERE token = ?
            """,
            (token,),
        )

        row = cursor.fetchone()
        return rowToDict(cursor, row) if row else None

    finally:
        connection.close()


def getGalleryShareLinks(gallery_id: int) -> list[dict]:
    """List all share links for a gallery."""
    connection = getConnection()

    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT
                id,
                gallery_id,
                token,
                created_by_user_id,
                expires_at_utc,
                revoked_at_utc,
                created_at_utc
            FROM gallery_share_links
            WHERE gallery_id = ?
            ORDER BY id DESC
            """,
            (gallery_id,),
        )

        return [rowToDict(cursor, row) for row in cursor.fetchall()]

    finally:
        connection.close()


def revokeGalleryShareLink(
    gallery_id: int,
    share_link_id: int,
) -> bool:
    """
    Revoke a link to prevent new requests.
    Existing requests and gallery memberships are not deleted.

    Caller must verify that the current user is an Owner.
    """
    connection = getConnection()

    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            UPDATE gallery_share_links
            SET revoked_at_utc = ?
            WHERE id = ?
              AND gallery_id = ?
              AND revoked_at_utc IS NULL
            """,
            (utcNowString(), share_link_id, gallery_id),
        )

        connection.commit()
        return cursor.rowcount > 0

    finally:
        connection.close()


def createGalleryAccessRequest(
    token: str,
    requester_user_id: int,
) -> dict:
    """
    Submit an access request through a valid share link.

    Reuses an existing pending request for the same gallery/user.
    A revoked or expired link blocks new requests only.
    """
    connection = getConnection()

    try:
        cursor = connection.cursor()
        cursor.execute("BEGIN IMMEDIATE")

        cursor.execute(
            """
            SELECT
                id,
                gallery_id,
                expires_at_utc,
                revoked_at_utc
            FROM gallery_share_links
            WHERE token = ?
            """,
            (token,),
        )
        link = cursor.fetchone()

        if link is None:
            connection.rollback()
            return {"status": "invalid_link"}

        link_id, gallery_id, expires_at, revoked_at = link

        if revoked_at is not None:
            connection.rollback()
            return {"status": "link_revoked"}

        if parseUtcDateTime(expires_at) <= utcNow():
            connection.rollback()
            return {"status": "link_expired"}

        cursor.execute(
            """
            SELECT is_enabled
            FROM client_galleries
            WHERE id = ?
            """,
            (gallery_id,),
        )
        gallery = cursor.fetchone()

        if gallery is None or not bool(gallery[0]):
            connection.rollback()
            return {"status": "gallery_unavailable"}

        cursor.execute(
            """
            SELECT role
            FROM client_gallery_members
            WHERE gallery_id = ? AND user_id = ?
            LIMIT 1
            """,
            (gallery_id, requester_user_id),
        )

        if cursor.fetchone() is not None:
            connection.rollback()
            return {"status": "already_member"}

        cursor.execute(
            """
            SELECT id, share_link_id, gallery_id, requester_user_id,
                   status, created_at_utc, resolved_at_utc,
                   resolved_by_user_id
            FROM gallery_access_requests
            WHERE gallery_id = ?
              AND requester_user_id = ?
              AND status = 'pending'
            LIMIT 1
            """,
            (gallery_id, requester_user_id),
        )

        existing = cursor.fetchone()

        if existing is not None:
            result = rowToDict(cursor, existing)
            connection.commit()
            result["status"] = "already_pending"
            return result

        now = utcNowString()

        cursor.execute(
            """
            INSERT INTO gallery_access_requests (
                share_link_id,
                gallery_id,
                requester_user_id,
                status,
                created_at_utc
            )
            VALUES (?, ?, ?, 'pending', ?)
            """,
            (link_id, gallery_id, requester_user_id, now),
        )

        request_id = cursor.lastrowid

        cursor.execute(
            """
            SELECT id, share_link_id, gallery_id, requester_user_id,
                   status, created_at_utc, resolved_at_utc,
                   resolved_by_user_id
            FROM gallery_access_requests
            WHERE id = ?
            """,
            (request_id,),
        )
        result = rowToDict(cursor, cursor.fetchone())

        connection.commit()
        result["status"] = "created"
        return result

    except (sqlite3.Error, ValueError):
        connection.rollback()
        raise

    finally:
        connection.close()


def getGalleryAccessRequests(
    gallery_id: int,
    status: str | None = None,
) -> list[dict]:
    """List access requests. Caller must verify Owner access."""
    if status not in (None, "pending", "approved", "rejected"):
        raise ValueError("Invalid request status.")

    connection = getConnection()

    try:
        cursor = connection.cursor()

        query = """
            SELECT
                r.id,
                r.share_link_id,
                r.gallery_id,
                r.requester_user_id,
                r.status,
                r.created_at_utc,
                r.resolved_at_utc,
                r.resolved_by_user_id,
                u.email,
                u.first_name,
                u.last_name,
                u.photo_url
            FROM gallery_access_requests AS r
            JOIN users AS u ON u.id = r.requester_user_id
            WHERE r.gallery_id = ?
        """
        params: list = [gallery_id]

        if status is not None:
            query += " AND r.status = ?"
            params.append(status)

        query += " ORDER BY r.created_at_utc DESC, r.id DESC"

        cursor.execute(query, params)
        return [rowToDict(cursor, row) for row in cursor.fetchall()]

    finally:
        connection.close()


def resolveGalleryAccessRequest(
    gallery_id: int,
    request_id: int,
    owner_user_id: int,
    approve: bool,
) -> dict:
    """
    Approve or reject a request.

    Approval and membership creation happen in one SQLite transaction.
    Caller must verify that owner_user_id is a gallery Owner.
    """
    connection = getConnection()

    try:
        cursor = connection.cursor()
        cursor.execute("BEGIN IMMEDIATE")

        cursor.execute(
            """
            SELECT requester_user_id, status
            FROM gallery_access_requests
            WHERE id = ? AND gallery_id = ?
            """,
            (request_id, gallery_id),
        )
        request = cursor.fetchone()

        if request is None:
            connection.rollback()
            return {"status": "request_not_found"}

        requester_user_id, current_status = request

        if current_status != "pending":
            connection.rollback()
            return {"status": "request_already_resolved"}

        cursor.execute(
            """
            SELECT email
            FROM users
            WHERE id = ?
            """,
            (requester_user_id,),
        )
        requester = cursor.fetchone()

        if requester is None or not requester[0]:
            connection.rollback()
            return {"status": "requester_not_found"}

        now = utcNowString()

        if approve:
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
                VALUES (?, ?, ?, 'viewer', ?, ?, ?)
                ON CONFLICT (gallery_id, email)
                DO UPDATE SET
                    user_id = excluded.user_id,
                    updated_at = excluded.updated_at
                """,
                (
                    gallery_id,
                    requester[0].strip().lower(),
                    requester_user_id,
                    owner_user_id,
                    now,
                    now,
                ),
            )

            new_status = "approved"
        else:
            new_status = "rejected"

        cursor.execute(
            """
            UPDATE gallery_access_requests
            SET status = ?,
                resolved_at_utc = ?,
                resolved_by_user_id = ?
            WHERE id = ?
              AND gallery_id = ?
              AND status = 'pending'
            """,
            (new_status, now, owner_user_id, request_id, gallery_id),
        )

        if cursor.rowcount != 1:
            connection.rollback()
            return {"status": "request_already_resolved"}

        connection.commit()

        return {
            "status": "ok",
            "request_id": request_id,
            "gallery_id": gallery_id,
            "requester_user_id": requester_user_id,
            "decision": new_status,
            "resolved_at_utc": now,
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def createGalleryInvitation(
    gallery_id: int,
    email: str,
    role: str,
    invited_by_user_id: int,
) -> dict:
    """
    Create or update an email invitation.

    The API must restrict this operation to gallery Owners.
    This function records the invitation; it does not grant access
    or create a client_gallery_members row.
    """
    normalized_email = email.strip().lower()

    if not normalized_email or "@" not in normalized_email:
        raise ValueError("A valid email address is required.")

    if role not in ("owner", "viewer"):
        raise ValueError("Role must be 'owner' or 'viewer'.")

    connection = getConnection()

    try:
        cursor = connection.cursor()
        now = utcNowString()

        cursor.execute(
            """
            INSERT INTO gallery_invitations (
                gallery_id,
                email,
                role,
                invited_by_user_id,
                invited_user_id,
                status,
                created_at_utc,
                updated_at_utc
            )
            VALUES (?, ?, ?, ?, NULL, 'pending', ?, ?)
            ON CONFLICT (gallery_id, email)
            DO UPDATE SET
                role = excluded.role,
                invited_by_user_id = excluded.invited_by_user_id,
                invited_user_id = NULL,
                status = 'pending',
                updated_at_utc = excluded.updated_at_utc
            """,
            (
                gallery_id,
                normalized_email,
                role,
                invited_by_user_id,
                now,
                now,
            ),
        )

        connection.commit()

        cursor.execute(
            """
            SELECT id, gallery_id, email, role, invited_by_user_id,
                   invited_user_id, status, created_at_utc, updated_at_utc
            FROM gallery_invitations
            WHERE gallery_id = ? AND email = ?
            """,
            (gallery_id, normalized_email),
        )

        return rowToDict(cursor, cursor.fetchone())

    finally:
        connection.close()


def getGalleryInvitations(gallery_id: int) -> list[dict]:
    """List invitations. Caller must verify Owner access."""
    connection = getConnection()

    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT id, gallery_id, email, role, invited_by_user_id,
                   invited_user_id, status, created_at_utc, updated_at_utc
            FROM gallery_invitations
            WHERE gallery_id = ?
            ORDER BY created_at_utc DESC, id DESC
            """,
            (gallery_id,),
        )

        return [rowToDict(cursor, row) for row in cursor.fetchall()]

    finally:
        connection.close()


def revokeGalleryInvitation(
    gallery_id: int,
    invitation_id: int,
) -> bool:
    """Revoke a pending invitation without changing existing memberships."""
    connection = getConnection()

    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            UPDATE gallery_invitations
            SET status = 'revoked',
                updated_at_utc = ?
            WHERE id = ?
              AND gallery_id = ?
              AND status = 'pending'
            """,
            (utcNowString(), invitation_id, gallery_id),
        )

        connection.commit()
        return cursor.rowcount > 0

    finally:
        connection.close()


def registerDeviceToken(
    user_id: int,
    token: str,
    platform: str | None = None,
) -> bool:
    """Save or refresh a device token for push notifications."""
    token = token.strip()

    if not token:
        raise ValueError("Device token is required.")

    connection = getConnection()

    try:
        cursor = connection.cursor()
        now = utcNowString()

        cursor.execute(
            """
            INSERT INTO device_tokens (
                user_id, token, platform, created_at_utc, updated_at_utc
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (token)
            DO UPDATE SET
                user_id = excluded.user_id,
                platform = excluded.platform,
                updated_at_utc = excluded.updated_at_utc
            """,
            (user_id, token, platform, now, now),
        )

        connection.commit()
        return True

    finally:
        connection.close()


def removeDeviceToken(user_id: int, token: str) -> bool:
    """Remove a device token belonging to the authenticated user."""
    connection = getConnection()

    try:
        cursor = connection.cursor()
        cursor.execute(
            "DELETE FROM device_tokens WHERE user_id = ? AND token = ?",
            (user_id, token),
        )

        connection.commit()
        return cursor.rowcount > 0

    finally:
        connection.close()


def createUserNotification(
    user_id: int,
    notification_type: str,
    title: str,
    body: str,
    data: dict | None = None,
) -> int:
    """Store an in-app notification. A notification never grants access."""
    connection = getConnection()

    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO user_notifications (
                user_id,
                notification_type,
                title,
                body,
                data_json,
                created_at_utc
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                notification_type,
                title,
                body,
                json.dumps(data) if data is not None else None,
                utcNowString(),
            ),
        )

        connection.commit()
        return cursor.lastrowid

    finally:
        connection.close()


def getUserNotifications(
    user_id: int,
    limit: int = 50,
) -> list[dict]:
    """Return notifications only for the requested user."""
    safe_limit = max(1, min(int(limit), 100))
    connection = getConnection()

    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT id, user_id, notification_type, title, body,
                   data_json, created_at_utc, read_at_utc
            FROM user_notifications
            WHERE user_id = ?
            ORDER BY created_at_utc DESC, id DESC
            LIMIT ?
            """,
            (user_id, safe_limit),
        )

        results = []

        for row in cursor.fetchall():
            item = rowToDict(cursor, row)
            try:
                item["data"] = (
                    json.loads(item["data_json"])
                    if item["data_json"]
                    else None
                )
            except (TypeError, json.JSONDecodeError):
                item["data"] = None

            results.append(item)

        return results

    finally:
        connection.close()


def markUserNotificationRead(
    user_id: int,
    notification_id: int,
) -> bool:
    """Mark one of the authenticated user's notifications as read."""
    connection = getConnection()

    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            UPDATE user_notifications
            SET read_at_utc = ?
            WHERE id = ?
              AND user_id = ?
              AND read_at_utc IS NULL
            """,
            (utcNowString(), notification_id, user_id),
        )

        connection.commit()
        return cursor.rowcount > 0

    finally:
        connection.close()



def linkPendingGalleryInvitationsForUser(
    user_id: int,
    email: str,
) -> int:
    """
    Link pending email invitations when a user signs in.

    Email verification is intentionally not required yet.
    Membership creation and invitation acceptance are committed
    together. Existing membership roles are preserved.
    """
    normalized_email = (email or "").strip().lower()

    if not normalized_email:
        return 0

    connection = getConnection()
    linked_count = 0

    try:
        cursor = connection.cursor()
        cursor.execute("BEGIN IMMEDIATE")

        # Ensure the supplied email belongs to this local user.
        cursor.execute(
            """
            SELECT email
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        )
        user_row = cursor.fetchone()

        if (
            user_row is None
            or not user_row[0]
            or user_row[0].strip().lower() != normalized_email
        ):
            connection.rollback()
            return 0

        cursor.execute(
            """
            SELECT
                id,
                gallery_id,
                email,
                role,
                invited_by_user_id
            FROM gallery_invitations
            WHERE email = ? COLLATE NOCASE
              AND status = 'pending'
            ORDER BY id ASC
            """,
            (normalized_email,),
        )

        invitations = cursor.fetchall()
        now = utcNowString()

        for invitation in invitations:
            (
                invitation_id,
                gallery_id,
                invitation_email,
                role,
                invited_by_user_id,
            ) = invitation

            # Check whether a membership already exists for this email.
            cursor.execute(
                """
                SELECT id, user_id
                FROM client_gallery_members
                WHERE gallery_id = ?
                  AND email = ? COLLATE NOCASE
                LIMIT 1
                """,
                (gallery_id, normalized_email),
            )

            membership = cursor.fetchone()

            if membership is None:
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
                    """,
                    (
                        gallery_id,
                        invitation_email.strip().lower(),
                        user_id,
                        role,
                        invited_by_user_id,
                        now,
                        now,
                    ),
                )

            elif membership[1] is None:
                # Attach an unclaimed membership to this user.
                # Keep its existing role unchanged.
                cursor.execute(
                    """
                    UPDATE client_gallery_members
                    SET user_id = ?,
                        updated_at = ?
                    WHERE id = ?
                      AND user_id IS NULL
                    """,
                    (user_id, now, membership[0]),
                )

            elif membership[1] != user_id:
                # Never attach another account's membership.
                # Leave this invitation pending for investigation.
                continue

            # Accept only after membership creation/linking succeeded.
            cursor.execute(
                """
                UPDATE gallery_invitations
                SET invited_user_id = ?,
                    status = 'accepted',
                    updated_at_utc = ?
                WHERE id = ?
                  AND status = 'pending'
                """,
                (user_id, now, invitation_id),
            )

            if cursor.rowcount == 1:
                linked_count += 1

        connection.commit()
        return linked_count

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

