from fastapi import Header, HTTPException
from firebase_admin import auth
from fastapi import Depends
from app.database.user_db import syncUser

def getCurrentFirebaseUser(authorization: str | None = Header(default = None)):
    if authorization is None:
        raise HTTPException(status_code=401, detail="Authorization header missing")

    parts = authorization.split(" ", 1)

    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid authorization header format")

    id_token = parts[1].strip()

    try:
        decoded_token = auth.verify_id_token(id_token)

        print("Firebase token verified successfully")
        print("Firebase UID:", decoded_token["uid"])

        return decoded_token

    except Exception as error:
        print("Firebase token verification failed")
        print("Error type:", type(error).__name__)
        print("Error:", error)
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def getCurrentLocalUser(
    firebase_user=Depends(getCurrentFirebaseUser),
):
    """Get or synchronize the authenticated user's SQLite record."""

    # Read the verified Firebase user details.
    firebase_uid = firebase_user["uid"]
    email = firebase_user.get("email")
    email_verified = firebase_user.get("email_verified", False)

    display_name = firebase_user.get("name", "") or ""
    name_parts = display_name.strip().split(" ", 1)

    # Synchronize the user and return the local database record.
    return syncUser(
        firebase_uid=firebase_uid,
        first_name=name_parts[0] if name_parts else "",
        last_name=name_parts[1] if len(name_parts) > 1 else "",
        email=email,
        email_verified=email_verified,
    )