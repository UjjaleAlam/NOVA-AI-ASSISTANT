import os
from pathlib import Path
from database import get_connection


def get_drives():
    drives = []

    for drive in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        path = f"{drive}:\\"
        if os.path.exists(path):
            drives.append(path)

    return drives


def build_file_index():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM files")

    conn.commit()

    total = 0

    drives = get_drives()

    print("Drives Found:")
    for drive in drives:
        print(" ", drive)

    print("\nStarting scan...\n")

    for drive in drives:

        for root, dirs, files in os.walk(
            drive,
            topdown=True,
            onerror=lambda e: None
        ):

            # Skip protected/system folders
            dirs[:] = [
                d for d in dirs
                if d.lower() not in {
                    "$recycle.bin",
                    "system volume information",
                    "windows",
                    "programdata"
                }
            ]

            for file in files:

                try:

                    path = os.path.join(root, file)

                    stat = os.stat(path)

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
                        VALUES
                        (?, ?, ?, ?, ?)
                        """,
                        (
                            file,
                            path,
                            Path(file).suffix.lower(),
                            stat.st_size,
                            stat.st_mtime
                        )
                    )

                    total += 1

                    if total % 1000 == 0:

                        conn.commit()

                        print(f"Indexed {total:,} files...")

                except Exception:
                    pass

    conn.commit()

    conn.close()

    print(f"\nFinished indexing {total:,} files.")

if __name__ == "__main__":

     build_file_index()