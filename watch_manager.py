import json
import os

from database import get_connection


WATCHLIST_FILE = "watch_list.json"


SYSTEM_KEYWORDS = {

    "windows",
    "program files",
    "program files (x86)",
    "programdata",
    "system volume information",
    "$recycle.bin",
    "appdata",
    ".git",
    "__pycache__",
    "venv",
    "node_modules",
    "python312",
    "steam",
    "nvidia",
    "intel",
    "amd",
    "drivers",
    "microsoft"

}


USER_PRIORITY = {

    "desktop": 100,
    "documents": 100,
    "downloads": 95,
    "pictures": 90,
    "videos": 90,
    "music": 85,
    "projects": 120,
    "college": 120,
    "workspace": 120,
    "github": 110

}


def should_ignore(folder):

    lower = folder.lower()

    for keyword in SYSTEM_KEYWORDS:

        if keyword in lower:
            return True

    return False


def calculate_score(folder, count):

    score = count

    lower = folder.lower()

    for keyword, bonus in USER_PRIORITY.items():

        if keyword in lower:
            score += bonus

    return score


def discover_watch_folders(limit=20):

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT path
        FROM files
        """
    )

    folders = {}

    for (path,) in cursor.fetchall():

        try:

            folder = os.path.dirname(path)

            if should_ignore(folder):
                continue

            folders[folder] = folders.get(folder, 0) + 1

        except Exception:
            pass

    conn.close()

    ranked = []

    for folder, count in folders.items():

        ranked.append(

            (
                folder,
                calculate_score(folder, count)
            )

        )

    ranked.sort(

        key=lambda x: x[1],
        reverse=True

    )

    return [

        folder

        for folder, score in ranked[:limit]

    ]


def save_watch_list():

    folders = discover_watch_folders()

    with open(

        WATCHLIST_FILE,
        "w",
        encoding="utf-8"

    ) as f:

        json.dump(

            folders,
            f,
            indent=4

        )

    print(

        f"\nSaved {len(folders)} watch folders."

    )


def load_watch_list():

    if not os.path.exists(

        WATCHLIST_FILE

    ):

        save_watch_list()

    with open(

        WATCHLIST_FILE,
        "r",
        encoding="utf-8"

    ) as f:

        return json.load(f)


if __name__ == "__main__":

    save_watch_list()

    print()

    for folder in load_watch_list():

        print(folder)