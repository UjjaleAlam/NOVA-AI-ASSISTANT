from importlib.metadata import files

from database import (
    search_document_contents,
)
from database import get_recent_files
from file_manager import(
    search_files,
    search_folders,
)

# Later
# from database import get_recent_files(done)


class SearchManager:

    def __init__(self):

        pass

    # ==========================================

    def search_files(
        self,
        query,
        limit=20
    ):

        # TODO
        return search_files(query, limit)

    # ==========================================

    def search_folders(
        self,
        query,
        limit=20
    ):

        # TODO
        return search_folders(query, limit)

    # ==========================================

    def search_documents(
        self,
        query,
        limit=20
    ):

        return search_document_contents(
            query,
            limit
        )

    # ==========================================

    def search_recent(
        self,
        limit=20
    ):

        # TODO
        return get_recent_files(limit)

    # ==========================================

    def search(
        self,
        query,
        limit=20
    ):

        results = []

        files = self.search_files(
        query,
        limit
       )

        for item in files:
            item["type"] = "file"

        results.extend(files)

        folders = self.search_folders(
             query,
             limit
        )

        for item in folders:
             item["type"] = "folder"

        results.extend(folders)

        documents = self.search_documents(
            query,
            limit
        )

        for item in documents:
            item["type"] = "document"

        results.extend(documents)

        return results

search_manager = SearchManager()