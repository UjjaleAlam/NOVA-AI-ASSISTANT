SUPPORTED_DOCUMENTS = {
    ".pdf": "PDF",
    ".docx": "Word",
    ".pptx": "PowerPoint",
    ".xlsx": "Excel",
    ".txt": "Text",
}


def is_supported(path):

    from pathlib import Path

    return Path(path).suffix.lower() in SUPPORTED_DOCUMENTS


def get_document_type(path):

    from pathlib import Path

    return SUPPORTED_DOCUMENTS.get(
        Path(path).suffix.lower()
    )