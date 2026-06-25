import sqlite3
import os
from pathlib import Path

DATABASE_FOLDER = "database"
DATABASE_NAME = "file_index.db"

os.makedirs(DATABASE_FOLDER, exist_ok=True)

DATABASE_PATH = os.path.join(
    DATABASE_FOLDER,
    DATABASE_NAME
)


def get_connection():

    return sqlite3.connect(DATABASE_PATH)


def initialize_database():

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS files(

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            name TEXT,

            path TEXT UNIQUE,

            extension TEXT,

            size INTEGER,

            modified REAL

        )
    """)

    # Search indexes
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_name
        ON files(name)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_extension
        ON files(extension)
    """)

    conn.commit()
    conn.close()


# ==========================================
# DATABASE HELPERS
# ==========================================

def file_exists(path):

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute(
        "SELECT 1 FROM files WHERE path=?",
        (path,)
    )

    exists = cursor.fetchone() is not None

    conn.close()

    return exists


def insert_file(path):

    if not os.path.isfile(path):
        return

    try:

        stat = os.stat(path)

        conn = get_connection()

        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR IGNORE INTO files
            (
                name,
                path,
                extension,
                size,
                modified
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                os.path.basename(path),
                path,
                Path(path).suffix.lower(),
                stat.st_size,
                stat.st_mtime
            )
        )

        conn.commit()
        conn.close()

    except Exception:
        pass


def update_file(path):

    if not os.path.isfile(path):
        return

    try:

        stat = os.stat(path)

        conn = get_connection()

        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE files
            SET
                size=?,
                modified=?
            WHERE path=?
            """,
            (
                stat.st_size,
                stat.st_mtime,
                path
            )
        )

        conn.commit()
        conn.close()

    except Exception:
        pass


def delete_file(path):

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM files WHERE path=?",
        (path,)
    )

    conn.commit()
    conn.close()


if __name__ == "__main__":

    initialize_database()

    print("Database ready.")