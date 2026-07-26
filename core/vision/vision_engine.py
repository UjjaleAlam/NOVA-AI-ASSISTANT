class VisionEngine:

    def clean_text(
        self,
        text
    ):
        if not text:
            return ""

        lines = []
        seen = set()

        for line in text.splitlines():
            line = line.strip()

            if not line:
                continue

            if line in seen:
                continue

            seen.add(line)

            lines.append(line)

        return "\n".join(lines)

    def summarize_text(
        self,
        text
    ):
        pass

    def detect_application(
            self,
            window_title
    ):
        if not window_title:
            return "unknown"

        title = window_title.lower()
        applications = {

            "visual studio code": "vscode",
            "code": "vscode",

            "chrome": "chrome",
            "edge": "edge",
            "firefox": "firefox",

            "explorer": "explorer",
            "file explorer": "explorer",

            "terminal": "terminal",
            "powershell": "terminal",
            "command prompt": "terminal",
            "cmd": "terminal",

            "notepad": "notepad",
            "word": "word",
            "excel": "excel",
            "powerpoint": "powerpoint",
    
        }

        for keyword, app in applications.items():

            if keyword in title:
                return app

        return "unknown"


vision_engine = VisionEngine()