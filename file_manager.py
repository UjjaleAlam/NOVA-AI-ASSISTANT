import os
from database import (
    get_connection,
    record_open
)
from core.search_constants import (
    USER_FOLDER_SCORES,
    LOW_PRIORITY_SCORES,
    PREFERRED_EXTENSIONS,
    FILE_ALIASES,
    FILE_TYPES,
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
# SEARCH FILES
# ==========================================
def search_files(keyword, limit=500):

    keywords = normalize_search_query(keyword)

    size_filter = extract_size_filter(keyword)

    is_large = "larger than" in keyword or "bigger than" in keyword
    is_small = "smaller than" in keyword or "less than" in keyword

    if not keywords:
        return []
    
    conn = get_connection()

    cursor = conn.cursor()

    extensions = None
    search_words = []

    for word in keywords:

        if word in FILE_TYPES:
            extensions = FILE_TYPES[word]

        else:

            search_words.append(word)

    # ------------------------------------
    # SIZE Search
    # ------------------------------------

    if size_filter is not None:
        operator = ">=" if is_large else "<="

        cursor.execute(
            f"""
            SELECT
                name,
                path,
                extension
            FROM files
            WHERE size {operator} ?
            ORDER BY size DESC
            LIMIT ?
            """,
            (
                size_filter,
                limit
            )
        )

        rows = cursor.fetchall()

        conn.close()

        results = []

        for name, path, extension in rows:

            results.append(
                {
                    "name": name,
                    "stem": os.path.splitext(name)[0],
                    "path": path,
                    "extension": extension
                }
            )

            return results
        
    # -------------------------------------
    # Normal Search
    # -------------------------------------

    if extensions:

        placeholders = ",".join("?" * len(extensions))

        cursor.execute(
            f"""
            SELECT
                name,
                path,
                extension
            FROM files
            WHERE extension IN ({placeholders})
            ORDER BY name
            LIMIT ?
            """,
            (*extensions, limit)
        )

    else:

        try:
           
           search_query = " ".join(
               f"{word}*"
               for word in search_words
           )

           cursor.execute(
               f"""
               SELECT
                   files.name,
                   files.path,
                   files.extension
               FROM files_fts
               JOIN files
               ON files.id = files_fts.rowid
               WHERE files_fts MATCH ?
               LIMIT {int(limit)}
               """,
               (search_query,)
            )
        
        except Exception:

            cursor.execute(
                """
                SELECT 
                    name,
                    path,
                    extension
                From files

                WHERE LOWER(name) LIKE ?

                ORDER BY name

                LIMIT ?

                """,
                (f"%{' '.join(search_words)}%", limit)
            )
    rows = cursor.fetchall()

    conn.close()

    results = []

    for name, path, extension in rows:

        results.append(
            {
                "name": name,
                "stem": os.path.splitext(name)[0],
                "path": path,
                "extension": extension
            }
        )

    results = rank_results(
        results,
        " ".join(search_words)
    )

    return results

def search_folders(keyword, limit=500):

    keyword = keyword.lower().strip()

    conn = get_connection()

    cursor = conn.cursor()

    try:

        cursor.execute(
            """
            SELECT
             
                folders.name,
                folders.path

            FROM folders_fts

            JOIN folders

            ON folders.id = folders_fts.rowid

            WHERE folders_fts MATCH ?

            LIMIT ?
            """,
            (f"{keyword}*", limit)
        )

    except Exception:

        cursor.execute(
            """
            SELECT

               name,

               path
            
            FROM folders

            WHERE LOWER(name) LIKE ?

            ORDER BY name

            LIMIT ?
            """,
            (f"%{keyword}%", limit)
        )

    rows = cursor.fetchall()

    conn.close()

    results = []

    for name, path in rows:

        results.append(
            {
                "name": name,
                "stem": name,
                "path": path,
                "extension": ""
            }
        )

    return rank_results(results, keyword)

# =========================================
# SEARCH RECENT FILES
# =========================================

def search_recent_files(limit=10):

    from database import get_recent_files

    return get_recent_files(limit)

# ==========================================
# SMART SEARCH RANKING
# ==========================================

def rank_results(results, keyword):

    keyword = keyword.lower()

    def score(file):

        score = 0

        name = file["name"].lower()

        stem = file["stem"].lower()

        path = file["path"].lower()

        extension = file["extension"].lower()

        # --------------------------------------
        # NAME MATCHING
        # --------------------------------------

        if stem == keyword:
            score += 3000

        elif name == keyword:
            score += 2800

        elif stem.startswith(keyword):
            score += 2000

        elif keyword in stem:
            score += 1200

        # ---------------------------------------
        # Exact word match
        # ---------------------------------------

        words = (
            stem.replace("_", " ")
                .replace("-", " ")
                .split()
        )

        if keyword in words:
            score += 700

        # ---------------------------------------
        # Preferred extensions
        # ---------------------------------------

        score += PREFERRED_EXTENSIONS.get(extension, 0)

        # ---------------------------------------
        # User Folder Bonus
        # ---------------------------------------

        for folder, bonus in USER_FOLDER_SCORES.items():
            if folder in path:
                score += bonus
                break
        
        # ----------------------------------------
        # Lower Priority System Files
        # ----------------------------------------

        for folder, penalty in LOW_PRIORITY_SCORES.items():
            if folder in path:
                score += penalty
                break

        # ----------------------------------------
        # Slight preference for shallower paths
        # ----------------------------------------

        depth = path.count("\\")

        score -= depth * 3

        return score
    
    return sorted(
        results,
        key=score,
        reverse=True
    )

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