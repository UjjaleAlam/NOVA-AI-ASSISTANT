from core.search_parser import search_parser
from core.search_engine import search_engine
from pathlib import Path

from database import (
    search_document_contents,
)
from database import get_recent_files
from file_manager import search_folders
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
        
        search_filter = search_parser.parse(query)

        search_filter.limit = limit

        rows = search_engine.search(search_filter)

        results = []

        for name, path, extension in rows:

            results.append(
                {
                    "name": name,
                    "stem": Path(name).stem,
                    "path": path,
                    "extension": extension,
                }
            )

        return results

    # ==========================================

    def search_folders(
        self,
        query,
        limit=20
    ):
        
        return search_engine.search_folders(
            query,
            limit
            )

    # ==========================================

    def search_documents(
        self,
        query,
        limit=20
    ):

        return search_engine.search_documents(
            query,
            limit
        )

    # ==========================================

    def search_recent(
        self,
        limit=20
    ):

        # TODO
        return search_engine.search_recent(limit)

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