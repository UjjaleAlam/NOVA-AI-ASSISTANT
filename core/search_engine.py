from database import get_connection
from database import search_document_contents
from database import get_recent_files

class SearchEngine:

    def search(self, search_filter):

        conn = get_connection()

        cursor = conn.cursor()

        sql = """
        SELECT
            name,
            path,
            extension
        FROM files
        """

        conditions = []
        parameters = []

        # -----------------------------
        # Extension filter
        # -----------------------------

        if search_filter.has_extension_filter():

            placeholders = ",".join(
                "?"
                for _ in search_filter.extensions
            )

            conditions.append(
                f"extension IN ({placeholders})"
            )

            parameters.extend(
                search_filter.extensions
            )

        # -----------------------------
        # Minimum size
        # -----------------------------

        if search_filter.min_size is not None:

            conditions.append(
                "size >= ?"
            )

            parameters.append(
                search_filter.min_size
            )

        # -----------------------------
        # Maximum size
        # -----------------------------

        if search_filter.max_size is not None:

            conditions.append(
                "size <= ?"
            )

            parameters.append(
                search_filter.max_size
            )

        # -----------------------------
        # Keyword
        # -----------------------------

        if search_filter.has_keyword():

            conditions.append(
                "LOWER(name) LIKE ?"
            )

            parameters.append(
                f"%{search_filter.keyword}%"
            )

        if conditions:

            sql += "\nWHERE "

            sql += "\nAND ".join(
                conditions
            )

        sql += "\nORDER BY name"

        sql += "\nLIMIT ?"

        parameters.append(
            search_filter.limit
        )

        cursor.execute(
            sql,
            parameters
        )

        rows = cursor.fetchall()

        conn.close()

        return rows
    
    # folder migration

    def search_folders(self, keyword, limit=20):

        conn = get_connection()

        cursor = conn.cursor()

        try:

            cursor.execute(
                """
                SELECT
                    name,
                    path
                FROM folders_fts
                JOIN folders
                ON folders.id = folders_fts.rowid
                WHERE folders_fts MATCH ?
                LIMIT ?
                """,
                (
                    f"{keyword}*",
                    limit
                )
            )

        except Exception:

            cursor.execute(
                """
                SELECT
                    name,
                    path
                FROM folders
                WHERE LOWER(name) LIKE ?
                ORDER BY name
                LIMIT ?
                """,
                (
                    "%{keyword.lower()}%",
                    limit
                )
            )

        rows = cursor.fetchall()

        conn.close()

        results = []

        for name, path in rows:

            results.append(
                {
                    "name": name,
                    "stem": name,
                    "path": path,
                    "extension": ""
                }
            )

        return results
    
    def search_documents(
            self,
            query,
            limit=20
    ):
        
        return search_document_contents(
            query,
            limit
        )
    
    def search_recent(
            self,
            limit=20
    ):
        
        return get_recent_files(limit)


search_engine = SearchEngine()