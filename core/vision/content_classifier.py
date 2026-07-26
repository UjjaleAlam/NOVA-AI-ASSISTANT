import re


class ContentClassifier:

    def classify(
        self,
        blocks
    ):
        classified = []

        for block in blocks:
            if isinstance(block, dict):
                lines = block["text"]

            else:
                lines = block

            text = "\n".join(lines)
            content_type = "text"

            #code
            if re.search(
                r"(traceback|exception|error|failed)",
                text,
                re.IGNORECASE
            ):
                content_type = "error"

            #table
            elif len(lines) >= 3 and all(
                len(line.split()) >= 2
                for line in lines
            ):
                content_type = "error"

            classified.append(
                {
                    "text": lines,
                    "type": content_type
                }
            )

        return classified

content_classifier = ContentClassifier()