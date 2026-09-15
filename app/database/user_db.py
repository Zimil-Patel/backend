from datetime import datetime

from app.database.connection import getConnection


def getUserByFirebaseUid(firebase_uid: str):
    """
    Find a local user using their Firebase UID.

    Firebase UID is the permanent connection between
    Firebase Authentication and our local user record.
    """

    connection = getConnection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            id,
            firebase_uid,
            first_name,
            last_name,
            email,
            email_verified,
            mobile_number,
            created_at,
            updated_at
        FROM users
        WHERE firebase_uid = ?
        """,
        (firebase_uid,),
    )

    row = cursor.fetchone()

    connection.close()

    if row is None:
        return None

    return {
        "id": row[0],
        "firebase_uid": row[1],
        "first_name": row[2],
        "last_name": row[3],
        "email": row[4],
        "email_verified": bool(row[5]),
        "mobile_number": row[6],
        "created_at": row[7],
        "updated_at": row[8],
    }


def createUser(
    firebase_uid: str,
    first_name: str | None,
    last_name: str | None,
    email: str,
    email_verified: bool,
):
    """
    Create a new local user after Firebase authentication.
    """

    connection = getConnection()
    cursor = connection.cursor()

    now = datetime.now().isoformat()

    cursor.execute(
        """
        INSERT INTO users (
            firebase_uid,
            first_name,
            last_name,
            email,
            email_verified,
            mobile_number,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            firebase_uid,
            first_name,
            last_name,
            email,
            1 if email_verified else 0,
            None,
            now,
            now,
        ),
    )

    connection.commit()

    user_id = cursor.lastrowid

    connection.close()

    return user_id


def updateUser(
    firebase_uid: str,
    first_name: str | None,
    last_name: str | None,
    email: str,
    email_verified: bool,
):
    """
    Update the local user profile.

    This keeps the local profile synchronized with
    the information supplied by Firebase.
    """

    connection = getConnection()
    cursor = connection.cursor()

    now = datetime.now().isoformat()

    cursor.execute(
        """
        UPDATE users
        SET
            first_name = ?,
            last_name = ?,
            email = ?,
            email_verified = ?,
            updated_at = ?
        WHERE firebase_uid = ?
        """,
        (
            first_name,
            last_name,
            email,
            1 if email_verified else 0,
            now,
            firebase_uid,
        ),
    )

    connection.commit()

    connection.close()


def syncUser(
    firebase_uid: str,
    first_name: str | None,
    last_name: str | None,
    email: str,
    email_verified: bool,
):
    """
    Create the user if they don't exist.

    Otherwise update the existing local user.

    Returns the complete local user record.
    """

    existing_user = getUserByFirebaseUid(firebase_uid)

    if existing_user is None:
        createUser(
            firebase_uid=firebase_uid,
            first_name=first_name,
            last_name=last_name,
            email=email,
            email_verified=email_verified,
        )
    else:
        updateUser(
            firebase_uid=firebase_uid,
            first_name=first_name,
            last_name=last_name,
            email=email,
            email_verified=email_verified,
        )

    return getUserByFirebaseUid(firebase_uid)