from pathlib import Path

from core.document_manager import document_manager
from core.document_types import is_supported
from database import save_document


class DocumentIndexer:

    def __init__(self):
        pass

    # ==========================================

    def index_document(
        self,
        cursor,
        path
    ):
        print(f"[INDEXER] Processiong: {path}")

        if not is_supported(path):
            print("[INDEXER] Unsupported file")
            return False
        
        print("[INDEXER] Supported document")

        text = document_manager.extract(path)

        print(f"[INDEXER] Extracted {len(text)} characters")

        if not text:
            print("[INDEXER] No text extracted")
            return False

        extension = Path(path).suffix.lower()

        save_document(
            cursor,
            path,
            extension,
            text
        )

        print("[INDEXER] Saved to database")

        return True


document_indexer = DocumentIndexer()