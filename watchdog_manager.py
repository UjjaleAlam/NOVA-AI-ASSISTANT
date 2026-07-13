import os
import time

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from watch_manager import load_watch_list
from database import (
    insert_file,
    update_file,
    delete_file,
    insert_folder,
    delete_folder,
    get_connection,
)
from core.document_indexer import document_indexer
from core.document_types import is_supported


# ==========================================================
# IGNORE SETTINGS
# ==========================================================

IGNORE_FOLDERS = {
    "database",
    "__pycache__",
    "venv",
    ".git",
    "node_modules",
    "$recycle.bin",
    "system volume information"
}

IGNORE_FILES = {
    "thumbs.db",
    "desktop.ini"
}

IGNORE_EXTENSIONS = {
    ".db",
    ".db-journal",
    ".db-wal",
    ".db-shm",
    ".tmp",
    ".temp",
    ".part",
    ".crdownload",
    ".download",
    ".bak",
    ".old"
}

IGNORE_PREFIXES = (
    "~$",
)


# ==========================================================
# FILTER
# ==========================================================

def should_ignore(path):

    path = os.path.abspath(path)
    lower_path = path.lower()

    filename = os.path.basename(lower_path)
    extension = os.path.splitext(filename)[1]

    # Ignore folders
    for folder in IGNORE_FOLDERS:

        if f"\\{folder.lower()}\\" in lower_path:

            return True

    # Ignore filenames
    if filename in IGNORE_FILES:

        return True

    # Ignore extensions
    if extension in IGNORE_EXTENSIONS:

        return True

    # Ignore Office temporary files
    for prefix in IGNORE_PREFIXES:

        if filename.startswith(prefix):

            return True

    return False


# ==========================================================
# EVENT HANDLER
# ==========================================================

class NovaFileHandler(FileSystemEventHandler):

    def on_created(self, event):

        insert_file(event.src_path)

        folder = os.path.dirname(event.src_path)
        insert_folder(folder)

        if is_supported(event.src_path):

            conn = get_connection()
            cursor = conn.cursor()

            document_indexer.index_document(
                cursor,
                event.src_path
            )

            conn.commit()
            conn.close()

        print(f"[WATCHDOG] Created : {event.src_path}")

    def on_modified(self, event):

        update_file(event.src_path)

        if is_supported(event.src_path):

            conn = get_connection()
            cursor = conn.cursor()

            document_indexer.index_document(
                cursor,
                event.src_path
            )

            conn.commit()
            conn.close()

        print(f"[WATCHDOG] Modified : {event.src_path}")


    def on_deleted(self, event):

        delete_file(event.src_path)

        print(f"[WATCHDOG] Deleted : {event.src_path}")

    def on_moved(self, event):

        delete_file(event.src_path)

        insert_file(event.dest_path)

        if is_supported(event.dest_path):

            conn = get_connection()
            cursor = conn.cursor()

            document_indexer.index_document(
                cursor,
                event.dest_path
            )

            conn.commit()
            conn.close()

        print(f"[WATCHDOG] Moved")
        print(f"    From: {event.src_path}")
        print(f"    To: {event.dest_path}")
        
# ==========================================================
# WATCHDOG
# ==========================================================

def start_watchdog():

    observer = Observer()

    handler = NovaFileHandler()

    WATCH_FOLDERS = load_watch_list()

    print("\n====================================")
    print("         NOVA WATCHDOG")
    print("====================================\n")

    if not WATCH_FOLDERS:

        print("No folders available to watch.")

        return
    
    for folder in WATCH_FOLDERS:

        try:

            observer.schedule(
                handler,
                folder,
                recursive=True
            )

            print(f"Watching : {folder}")

        except Exception as e:

            print(f"Failed   : {folder}")

            print(e)

    observer.start()

    print("\nNova Watchdog Running...")
    print("Press CTRL + C to stop.\n")

    try:

        while True:

            time.sleep(1)

    except KeyboardInterrupt:

        print("\nStopping Watchdog...")

        observer.stop()

    observer.join()


if __name__ == "__main__":

    start_watchdog()