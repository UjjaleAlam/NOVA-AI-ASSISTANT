from core.search_filter import SearchFilter
from file_manager import (
    normalize_search_query,
    extract_size_filter,
)
from core.search_constants import (
    FILE_TYPES,
)


class SearchParser:

    def parse(self, query):

        query = query.lower().strip()

        search = SearchFilter()

        search.original_query = query

        keywords = normalize_search_query(query)

        search_words = []

        # ---------------------------------------
        # File Type Detection
        # ---------------------------------------

        for word in keywords:

            if word in FILE_TYPES:

                search.file_type = word
                search.extensions = FILE_TYPES[word]

            else:

                search_words.append(word)

        # ---------------------------------------
        # Size Detection
        # ---------------------------------------

        size = extract_size_filter(query)

        if size is not None:

            if (
                "larger than" in query
                or "bigger than" in query
            ):

                search.min_size = size

            elif (
                "smaller than" in query
                or "less than" in query
            ):

                search.max_size = size

            # Remove size-related words from keyword
            remove_words = {
                "larger",
                "bigger",
                "smaller",
                "less",
                "than",
                "kb",
                "mb",
                "gb",
            }

            cleaned = []

            for word in search_words:

                if word in remove_words:
                    continue

                if word.replace(".", "").isdigit():
                    continue

                cleaned.append(word)

            search_words = cleaned

        # ---------------------------------------
        # Final Keyword
        # ---------------------------------------

        search.keyword = " ".join(search_words)

        # ---------------------------------------
        # Debug (remove later)
        # ---------------------------------------

        print(search)

        return search


search_parser = SearchParser()