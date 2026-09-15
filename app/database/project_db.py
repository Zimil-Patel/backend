from datetime import datetime

from app.database.connection import getConnection


def getOrCreateProject(project_name: str):
    """
    Find an existing project by name.

    If the project does not exist, create it and return
    the newly created project ID.
    """

    connection = getConnection()
    cursor = connection.cursor()

    # Check whether this project already exists.
    cursor.execute(
        """
        SELECT id
        FROM projects
        WHERE name = ?
        """,
        (project_name,),
    )

    row = cursor.fetchone()

    # If it already exists, return its ID.
    if row is not None:
        connection.close()
        return row[0]

    # Project doesn't exist, so create it.
    created_at = datetime.now().isoformat()

    cursor.execute(
        """
        INSERT INTO projects(name, created_at)
        VALUES (?, ?)
        """,
        (
            project_name,
            created_at,
        ),
    )

    connection.commit()

    project_id = cursor.lastrowid

    connection.close()

    print(
        f"Created project: {project_name}, ID: {project_id}"
    )

    return project_id