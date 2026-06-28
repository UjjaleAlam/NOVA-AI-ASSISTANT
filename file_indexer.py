import os
from pathlib import Path
from database import (
    get_connection,
    rebuild_fts,
)


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

    cursor.execute("DELETE FROM folders")

    cursor.execute("DELETE FROM recent_files")

    conn.commit()

    total = 0

    folder_total = 0

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

            for folder in dirs:

                try:

                    folder_path = os.path.join(root, folder)

                    stat = os.stat(folder_path)

                    cursor.execute(
                        """
                        INSERT OR IGNORE INTO folders
                        (
                           name,
                           path,
                           modified
                        )
                        VALUES
                        (?, ?, ?)
                        """,
                        (
                            folder,
                            folder_path,
                            stat.st_mtime
                        )
                    )

                    folder_total += 1

                except Exception:
                    pass

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

                    if total % 5000 == 0:

                        conn.commit()

                        print(f"Indexed {total:,} files...")

                except PermissionError:
                    pass
                except FileNotFoundError:
                    pass
                except Exception:
                    pass

    conn.commit()

    conn.close()

    print("\nRebuilding search index...")

    rebuild_fts()

    cursor = get_connection().cursor()
    cursor.execute("INSERT INTO folders_fts(folders_fts) VALUES('rebuild')")
    cursor.connection.commit()
    cursor.connection.close()

    print(f"\nFinished indexing {total:,} files.")
    print(f"Indexed {folder_total:,} folders.")

if __name__ == "__main__":

     build_file_index()