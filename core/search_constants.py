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
    "pic": "images",
    "pics": "images",
    "wallpaper": "images",
    "wallpapers": "images",
    "screenshot": "images",
    "icon": "images",
    "icons": "images",

    # Video
    "video": "videos",
    "videos": "videos",
    "movie": "videos",
    "movies": "videos",
    "clip": "videos",
    "clips": "videos",
    "film": "videos",
    "films": "videos",

    # Music
    "music": "music",
    "song": "music",
    "songs": "music",
    "audio": "music",
    "recording": "music",
    "recordings": "music" ,
    "sound": "music",
    "sounds": "music",

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

    #Archives
    "rar": "zip",
    "7z": "zip",
    "compressed file": "zip",
    "compressed files": "zip",

    #Developers Files
    "markdown": "markdown",
    "md": "markdown",
    "yaml": "yaml",
    "yml": "yaml",
    "log": "log",
    "logs": "log",
    "batch": "bat",
    "powershell": "ps1", 

}

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

    "images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tif", ".tiff", ".ico", ".svg", ".heic"],

    "videos": [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".mpeg", ".mpg", ".m4v", ".3gp"],

    "music": [".mp3", ".wav", ".aac", ".flac", ".ogg", ".m4a", ".wma"],

    "zip": [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"],

    "iso": [".iso"],

    "markdown" : [".md"],

    "yaml" : [".yaml", ".yml"],
    "toml" : [".toml"],
    "ini" : [".ini"],
    "log" : [".log"],
    "bat" : [".bat"],
    "ps1" : [".ps1"],
    "sh" : [".sh"],
}


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


