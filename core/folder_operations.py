import os
from pathlib import Path

from database import insert_folder


DEFAULT_LOCATION = Path.home() / "Documents"


def create_folder(name, location=None):

    if not name.strip():
        return False, "Folder name cannot be empty."

    if location is None:
        location = DEFAULT_LOCATION

    path = Path(location) / name

    if path.exists():
        return False, "Folder already exists."

    try:

        path.mkdir(parents=True)

        insert_folder(str(path))

        return True, f"Created folder '{name}'."

    except Exception as e:

        return False, f"Unable to create folder. {e}"