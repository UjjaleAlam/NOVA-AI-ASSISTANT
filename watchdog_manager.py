import os
import time

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from event_queue import add_event
from event_worker import start_worker
from watch_manager import load_watch_list


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

        if event.is_directory:
            return

        if should_ignore(event.src_path):
            return

        add_event(
            "created",
            event.src_path
        )

        print(f"[WATCHDOG] Created : {event.src_path}")


    def on_modified(self, event):

        if event.is_directory:
            return

        if should_ignore(event.src_path):
            return

        add_event(
            "modified",
            event.src_path
        )

        print(f"[WATCHDOG] Modified : {event.src_path}")


    def on_deleted(self, event):

        if event.is_directory:
            return

        if should_ignore(event.src_path):
            return

        add_event(
            "deleted",
            event.src_path
        )

        print(f"[WATCHDOG] Deleted : {event.src_path}")


    def on_moved(self, event):

        if event.is_directory:
            return

        if should_ignore(event.src_path):
            return

        if should_ignore(event.dest_path):
            return
        
        if event.src_path == event.dest_path:
            return

        add_event(
            "moved",
            event.src_path,
            event.dest_path
        ) 

        print(f"[WATCHDOG] Moved")
        print(f"    From: {event.src_path}")
        print(f"    To  : {event.dest_path}")


# ==========================================================
# WATCHDOG
# ==========================================================

def start_watchdog():

    start_worker()

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