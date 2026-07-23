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


vision_engine = VisionEngine()