import os
from database import get_connection

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

    os.startfile(path)

    return True

# ==========================================
# FORMAT RESULTS
# ==========================================


def format_results(results, limit=20):

    cache_results(results[:limit])

    output = []

    for i, file in enumerate(results[:limit], start=1):

        output.append(
            f"{i}. {file['name']}"
        )

    return "\n".join(output)