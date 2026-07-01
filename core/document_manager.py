from pathlib import Path

from core.document_types import (
    SUPPORTED_DOCUMENTS,
    is_supported,
)

from core.readers import (
    pdf_reader,
    docx_reader,
    pptx_reader,
    xlsx_reader,
    txt_reader,
)

class DocumentManager:

    def __init__(self):

        self.readers = {
            ".pdf": pdf_reader.extract_text,
            ".docx": docx_reader.extract_text,
            ".pptx": pptx_reader.extract_text,
            ".xlsx": xlsx_reader.extract_text,
            ".txt": txt_reader.extract_text,
        }

    # ==========================================

    def extract(self, path):

        if not is_supported(path):

            return ""

        extension = Path(path).suffix.lower()

        reader = self.readers.get(extension)

        if reader is None:

            return ""

        return reader(path)


document_manager = DocumentManager()