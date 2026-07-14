class SearchFilter:

    def __init__(self):

        # Original command
        self.original_query = ""

        # Search keyword
        self.keyword = ""

        # File type
        self.file_type = None

        # Extensions
        self.extensions = []

        # Size filters
        self.min_size = None
        self.max_size = None

        # Date filters
        self.modified_after = None
        self.modified_before = None

        # Folder restriction
        self.folder = None

        # Recent files
        self.recent = False

        # Duplicate search
        self.duplicates = False

        # Sorting
        self.sort_by = "name"

        # Maximum results
        self.limit = 20

    def has_keyword(self):

        return bool(self.keyword)

    def has_extension_filter(self):

        return len(self.extensions) > 0

    def has_size_filter(self):

        return (
            self.min_size is not None
            or self.max_size is not None
        )

    def has_date_filter(self):

        return (
            self.modified_after is not None
            or self.modified_before is not None
        )

    def __repr__(self):

        return (
            f"SearchFilter("
            f"keyword={self.keyword}, "
            f"extensions={self.extensions}, "
            f"min_size={self.min_size}, "
            f"max_size={self.max_size})"
        )