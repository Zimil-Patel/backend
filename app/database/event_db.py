from datetime import datetime

from app.database.connection import getConnection


def getOrCreateEvent(project_id: int, event_name: str):
    """
    Find an existing event inside a project.

    If the event does not exist, create it and return
    the newly created event ID.
    """

    connection = getConnection()
    cursor = connection.cursor()

    # Check whether this event already exists
    # inside the specified project.
    cursor.execute(
        """
        SELECT id
        FROM events
        WHERE name = ? AND project_id = ?
        """,
        (
            event_name,
            project_id,
        ),
    )

    row = cursor.fetchone()

    # Event already exists.
    if row is not None:
        connection.close()
        return row[0]

    # Event doesn't exist, so create it.
    created_at = datetime.now().isoformat()

    cursor.execute(
        """
        INSERT INTO events (
            name,
            project_id,
            created_at
        )
        VALUES (?, ?, ?)
        """,
        (
            event_name,
            project_id,
            created_at,
        ),
    )

    connection.commit()

    event_id = cursor.lastrowid

    connection.close()

    print(
        f"Created event: {event_name}, ID: {event_id}"
    )

    return event_id