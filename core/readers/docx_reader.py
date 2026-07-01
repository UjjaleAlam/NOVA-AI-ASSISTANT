from docx import Document


def extract_text(path):
    """
    Extract all text from a Word document.

    Returns:
        str -> Extracted text
        ""  -> If extraction fails
    """

    try:

        document = Document(path)

        paragraphs = []

        for paragraph in document.paragraphs:

            text = paragraph.text.strip()

            if text:

                paragraphs.append(text)

        return "\n".join(paragraphs)

    except Exception as e:

        print(f"[DOCX Reader] {e}")

        return ""