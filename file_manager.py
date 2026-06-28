import os
from database import (
    get_connection,
    record_open
)
from core.session import session
from ui.overlay_manager import overlay_manager
from ui.models.selection_item import SelectionItem
from core.file_icons import get_file_icon
from PySide6.QtWidgets import QApplication


# ==========================================
# FILE ALIAS
# ==========================================

FILE_ALIASES = {

    # Word
    "word": "word",
    "words": "word",
    "document": "word",
    "documents": "word",
    "doc": "word",
    "docs": "word",
    "docx": "word",

    # PDF
    "pdf": "pdf",
    "pdfs": "pdf",

    # Excel
    "excel": "excel",
    "sheet": "excel",
    "sheets": "excel",
    "spreadsheet": "excel",
    "spreadsheets": "excel",
    "xlsx": "excel",
    "xls": "excel",
    "csv": "excel",

    # PowerPoint
    "powerpoint": "powerpoint",
    "ppt": "powerpoint",
    "pptx": "powerpoint",
    "presentation": "powerpoint",
    "presentations": "powerpoint",
    "slides": "powerpoint",

     # Images
    "image": "images",
    "images": "images",
    "photo": "images",
    "photos": "images",
    "picture": "images",
    "pictures": "images",

    # Video
    "video": "videos",
    "videos": "videos",
    "movie": "videos",
    "movies": "videos",

    # Music
    "music": "music",
    "song": "music",
    "songs": "music",
    "audio": "music",

    # Python
    "python": "python",
    "py": "python",

    # HTML
    "html": "html",

    # CSS
    "css": "css",

    # JS
    "javascript": "javascript",
    "js": "javascript",

    # Zip
    "zip": "zip",
    "archive": "zip",
    "archives": "zip",

    # Text
    "text": "text",
    "txt": "text",

    #Folder
    "folder": "folder",
    "folders": "folder",
    "directory": "folder",
    "directories": "folder",

}

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
# FILE TYPES
# ==========================================

FILE_TYPES = {
    "pdf": [".pdf"],

    "word": [".doc", ".docx"],

    "excel": [".xls", ".xlsx", ".csv"],

    "powerpoint": [".ppt", ".pptx"],

    "text": [".txt"],

    "python": [".py"],

    "java": [".java"],

    "c": [".c"],

    "cpp": [".cpp", ".h", ".hpp"],

    "html": [".html"],

    "css": [".css"],

    "javascript": [".js"],

    "json": [".json"],

    "xml": [".xml"],

    "sql": [".sql"],

    "images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"],

    "videos": [".mp4", ".mkv", ".avi", ".mov", ".wmv"],

    "music": [".mp3", ".wav", ".aac", ".flac"],

    "zip": [".zip", ".rar", ".7z"],

    "iso": [".iso"]
}

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

USER_FOLDER_SCORES = {
    "\\documents\\": 1000,
    "\\desktop\\": 950,
    "\\downloads\\": 900,
    "\\pictures\\": 900,
    "\\videos\\": 700,
    "\\music\\": 600,
    "\\projects\\": 500,
}

LOW_PRIORITY_SCORES = {
    "\\windows\\": -3000,
    "\\program files\\": -2500,
    "\\program files (x86)\\": -2500,
    "\\appdata\\": -2200,
    "\\onedrive\\": -1500,
    "\\microsoft\\": -300,
}

PREFERRED_EXTENSIONS = {
    ".pdf": 300,
    ".doc": 290,
    ".docx": 280,
    ".xls": 270,
    ".xlsx": 270,
    ".ppt": 240,
    ".pptx": 250,
    ".txt": 220,
    ".csv": 230,
    ".py": 210,
    ".ipynb": 200,
}

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