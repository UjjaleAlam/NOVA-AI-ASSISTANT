class SessionManager:

    def __init__(self):

        self.clear()

    # ==========================================

    def start(
        self,
        session_type,
        results=None,
        title=""
    ):

        self.active = True

        self.session_type = session_type

        self.results = results or []

        self.title = title

    # ==========================================

    def clear(self):

        self.active = False

        self.session_type = None

        self.results = []

        self.title = ""

    # ==========================================

    def is_active(self):

        return self.active

    # ==========================================

    def count(self):

        return len(self.results)

    # ==========================================

    def get(self, index):

        if 0 <= index < len(self.results):

            return self.results[index]

        return None


session = SessionManager()