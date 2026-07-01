import fitz  # PyMuPDF


def extract_text(path):
    """
    Extract all text from a PDF.

    Returns:
        str -> Extracted text
        ""  -> If extraction fails
    """

    try:

        document = fitz.open(path)

        pages = []

        for page in document:

            pages.append(page.get_text())

        document.close()

        return "\n".join(pages).strip()

    except Exception as e:

        print(f"[PDF Reader] {e}")

        return ""