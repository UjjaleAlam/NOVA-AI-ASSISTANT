from database import (
    search_document_contents,
)

# Later
# from file_manager import search_files
# from file_manager import search_folders
# from database import get_recent_files


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
        return []

    # ==========================================

    def search_folders(
        self,
        query,
        limit=20
    ):

        # TODO
        return []

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
        return []

    # ==========================================

    def search(
        self,
        query,
        limit=20
    ):

        results = []

        # Files
        results.extend(
            self.search_files(
                query,
                limit
            )
        )

        # Folders
        results.extend(
            self.search_folders(
                query,
                limit
            )
        )

        # Documents
        results.extend(
            self.search_documents(
                query,
                limit
            )
        )

        return results


search_manager = SearchManager()