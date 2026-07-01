def extract_text(path):
    """
    Extract text from a plain text file.
    """

    try:

        with open(
            path,
            "r",
            encoding="utf-8",
            errors="ignore"
        ) as file:

            return file.read()

    except Exception as e:

        print(f"[TXT Reader] {e}")

        return ""