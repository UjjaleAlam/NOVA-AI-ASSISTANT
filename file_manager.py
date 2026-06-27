import os
from database import get_connection
from core.session import session
from ui.overlay_manager import overlay_manager
from ui.models.selection_item import SelectionItem
from core.file_icons import get_file_icon
from PySide6.QtWidgets import QApplication

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

MAX_DISPLAY_RESULTS = 500

# ==========================================
# SEARCH FILES
# ==========================================
def search_files(keyword):

    keyword = keyword.lower().strip()

    conn = get_connection()

    cursor = conn.cursor()

    extensions = FILE_TYPES.get(keyword)

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
            """,
            extensions
        )

    else:

        cursor.execute(
            """
            SELECT
                name,
                path,
                extension
            FROM files
            WHERE LOWER(name) LIKE ?
            ORDER BY name
            """,
            (f"%{keyword}%",)
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

# ==========================================
# SAVE LAST SEARCH
# ==========================================


def cache_results(results):

    found_files.clear()

    for i, file in enumerate(results, start=1):

        found_files[str(i)] = file["path"]

        found_files[file["stem"].lower()] = file["path"]

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