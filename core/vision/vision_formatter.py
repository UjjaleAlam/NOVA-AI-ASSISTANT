class VisionFormatter:

    def to_speech(
        self,
        perception
    ):

        if not perception:
            return "I couldn't read anything on the screen."

        parts = []

        for block in perception:

            text = " ".join(block["text"])

            if block["type"] == "error":
                parts.append(f"Error detected: {text}")

            elif block["type"] == "table":
                parts.append("A table is visible.")

            else:
                parts.append(text)

        return ". ".join(parts)


vision_formatter = VisionFormatter()