FILE_ICONS = {
    ".pdf": "📄",

    ".doc": "📝",
    ".docx": "📝",

    ".xls": "📊",
    ".xlsx": "📊",
    ".csv": "📊",

    ".py": "🐍",

    ".java": "☕",
    ".c": "⚙",
    ".cpp": "⚙",
    ".h": "⚙",
    ".hpp": "⚙",

    ".html": "🌐",
    ".css": "🎨",
    ".js": "📜",

    ".json": "🧩",
    ".xml": "🧩",
    ".sql": "🗄",

    ".jpg": "🖼",
    ".jpeg": "🖼",
    ".png": "🖼",
    ".gif": "🖼",
    ".bmp": "🖼",
    ".webp": "🖼",

    ".mp3": "🎵",
    ".wav": "🎵",
    ".aac": "🎵",
    ".flac": "🎵",

    ".mp4": "🎬",
    ".mkv": "🎬",
    ".avi": "🎬",
    ".mov": "🎬",
    ".wmv": "🎬",

    ".zip": "📦",
    ".rar": "📦",
    ".7z": "📦",

    ".txt": "📃",

    ".iso": "💿",

    "folder": "📁"
}


def get_file_icon(extension: str) -> str:
    """Return an icon for a file extension."""

    if not extension:
        return "📄"

    return FILE_ICONS.get(extension.lower(), "📄")