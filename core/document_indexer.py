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

        if not is_supported(path):

            return False

        text = document_manager.extract(path)

        if not text:

            return False

        extension = Path(path).suffix.lower()

        save_document(

            path,

            extension,

            text

        )

        return True


document_indexer = DocumentIndexer()