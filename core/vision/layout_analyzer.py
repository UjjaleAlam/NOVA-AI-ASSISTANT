class LayoutAnalyzer:

    def analyze(
        self,
        text
    ):
        if not text:
            return[]

        blocks = []
        current_block = []

        for line in text.splitlines():
            line = line.strip()

            if not line:

                if current_block:
                    blocks.append(current_block)
                    current_block = []
                continue

            current_block.append(line)

        if current_block:
            blocks.append(current_block)
        return blocks


layout_analyzer = LayoutAnalyzer()