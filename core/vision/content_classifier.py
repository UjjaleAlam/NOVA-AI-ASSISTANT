import re


class ContentClassifier:

    def classify(
        self,
        blocks
    ):

        classified = []

        for block in blocks:

            lines = block["text"]
            text = "\n".join(lines)

            content_type = "text"

            # Error detection
            if re.search(
                r"(traceback|exception|error|failed)",
                text,
                re.IGNORECASE
            ):
                content_type = "error"

            # Table detection
            elif (
                len(lines) >= 3
                and all(len(line.split()) >= 2 for line in lines)
            ):
                content_type = "table"

            new_block = block.copy()
            new_block["type"] = content_type

            classified.append(new_block)

        return classified


content_classifier = ContentClassifier()