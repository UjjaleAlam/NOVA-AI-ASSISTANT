from core.search_filter import SearchFilter
from file_manager import (
    FILE_TYPES,
    FILE_ALIASES,
    normalize_search_query,
    extract_size_filter,
)


class SearchParser:

    def parse(self, query):

        query = query.lower().strip()

        search = SearchFilter()

        search.original_query = query

        keywords = normalize_search_query(query)

        search_words = []

        for word in keywords:

            if word in FILE_TYPES:

                search.extensions = FILE_TYPES[word]

            else:

                search_words.append(word)

        search.keyword = " ".join(search_words)

        size = extract_size_filter(query)

        if size:

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

        return search


search_parser = SearchParser()