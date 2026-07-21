import os
from database import (
    record_open
)
from core.search_constants import (
    FILE_ALIASES,
)
from core.session import session
from pathlib import Path
from ui.overlay_manager import overlay_manager
from ui.models.selection_item import SelectionItem
from core.file_icons import get_file_icon
from PySide6.QtWidgets import QApplication

# ==========================================
# CLEAN SEARCH QUERY
# ==========================================

def normalize_search_query(query):

    query = query.lower().strip()

    remove_words = {
        "find",
        "search",
        "show",
        "open",
        "pull",
        "locate",
        "get",
        "give",
        "display",
        "list",


        "me",
        "my",
        "the",
        "all",
        "a",
        "an",


        "file",
        "files",
        "folder",
        "folders",
    }

    words = []

    for word in query.split():

        if word in remove_words:
            continue

        words.append(word)

    normalized = []

    for word in words:

        normalized.append(
            FILE_ALIASES.get(word, word)
        )

    return normalized
# ==========================================
# File size identifier
# ==========================================
def extract_size_filter(query):

    query = query.lower()

    patterns = [
        ("gb", 1024 * 1024 * 1024),
        ("mb", 1024 * 1024),
        ("kb", 1024),
    ]

    for unit, multiplier in patterns:

        if unit in query:
            try:

                number = float(
                    query.split(unit)[0].split()[-1]
                )

                return int(number * multiplier)
            
            except Exception:
                pass
    return None

# ==========================================
# SEARCH MEMORY
# ==========================================

found_files = {}

found_folders = {}

MAX_DISPLAY_RESULTS = 500

# ==========================================
# SAVE LAST SEARCH
# ==========================================


def cache_results(results):

    found_files.clear()

    for i, file in enumerate(results, start=1):

        found_files[str(i)] = file["path"]

        found_files[file["stem"].lower()] = file["path"]

def cache_folder_results(results):

    found_folders.clear()

    for i, folder in enumerate(results, start=1):

        found_folders[str(i)] = folder["path"]

        found_folders[folder["stem"].lower()] = folder["path"]
# ==========================================
# OPEN FILE
# ==========================================

def open_file(name):

    path = found_files.get(name.lower())

    if not path:
        return False

    overlay_manager.hide()

    QApplication.processEvents()

    os.startfile(path)

    record_open(path)

    return True

def open_folder(name):

    path = found_folders.get(name.lower())

    if not path:
        return False
    
    overlay_manager.hide()

    QApplication.processEvents()

    os.startfile(path)

    return True

# ==========================================
# OPEN FILE FROM SESSION
# ==========================================

def open_file_path(path):

    if not path:
        return False
    
    if not os.path.exists(path):
        return False
    
    overlay_manager.hide()

    QApplication.processEvents()

    os.startfile(path)

    record_open(path)

    return True

# ==========================================
# FORMAT RESULTS
# ==========================================

def format_results(results):

    if not results:
        return "I couldn't find any matching files."

    cache_results(results)

    display = []

    for file in results:

        display.append(
            {
                "name": file["name"],
                "stem": file["stem"],
                "path": file["path"],
                "extension": file["extension"],
            }
        )

    session.start(
        session_type="file_search",
        results=display,
        title=f"{len(display)} Results"
    )

    from ui.overlay_manager import overlay_manager

    overlay_manager.show_files(

        display,

        callback=None,

        title=f"{len(display)} Results"

    )

    return f"I found {len(display)} files."

def format_folder_results(results):

    if not results:
        return "I couldn't find any matching folders."
    
    cache_folder_results(results)

    display = []

    for folder in results:

        display.append(
            {
                "name": folder["name"],
                "stem": folder["stem"],
                "path": folder["path"],
                "extension": ""
            }
        )

    session.start(
        session_type="folder_search",
        results=display,
        title=f"{len(display)} Folders"
    )

    overlay_manager.show_files(
        display,
        callback=None,
        title=f"{len(display)} Folders"
    )

    return f"I found {len(display)} folders."

def format_document_results(results):

    if not results:
        return "I couldn't find any matching documents."
    
    display = []

    for document in results:

        display.append(
            {
                "name": Path(document["path"]).name,
                "stem": Path(document["path"]).stem,
                "path": document["path"],
                "extension": document["extension"],
            }
        )

    session.start(
        session_type="document_search",
        results=display,
        title=f"{len(display)} Documents"
    )

    overlay_manager.show_files(
        display,
        callback=None,
        title=f"{len(display)} Documents"
    )

    return f"I found {len(display)} matching documents"

def format_universal_results(results):

    if not results:
        return "I couldn't find anything."
    
    display = []

    for item in results:

        display.append(
            {
                "name": item.get("name", Path(item["path"]).name),
                "stem": item.get("stem", Path(item["path"]).stem),
                "path": item["path"],
                "extension": item.get("extension", ""),
                "type": item.get("type", "file")
            }
        )

    session.start(
        session_type="universal_search",
        results=display,
        title=f"{len(display)} Results"
    )

    overlay_manager.show_files(
        display,
        callback=None,
        title=f"{len(display)} Results"
    )

    return f"I found {len(display)} matching items"