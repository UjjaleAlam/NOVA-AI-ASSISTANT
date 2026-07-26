import numpy as np
import easyocr


class OCREngine:

    def __init__(self):

        self.reader = easyocr.Reader(
            ["en"],
            gpu=False
        )

    # ==========================================
    # RAW EASYOCR OUTPUT
    # ==========================================

    def extract_raw(
        self,
        image
    ):

        image = np.array(image)

        return self.reader.readtext(
            image,
            detail=1
        )

    # ==========================================
    # NOVA OCR OBJECTS
    # ==========================================

    def extract_blocks(
        self,
        image
    ):

        raw_results = self.extract_raw(image)

        blocks = []

        for bbox, text, confidence in raw_results:

            left = int(min(point[0] for point in bbox))
            top = int(min(point[1] for point in bbox))
            right = int(max(point[0] for point in bbox))
            bottom = int(max(point[1] for point in bbox))

            width = right - left
            height = bottom - top

            blocks.append(
                {
                    "text": text,

                    "bbox": {
                        "left": left,
                        "top": top,
                        "right": right,
                        "bottom": bottom,
                    },

                    "center": {
                        "x": int(left + width / 2),
                        "y": int(top + height / 2),
                    },

                    "width": width,
                    "height": height,

                    "confidence": float(confidence)
                }
            )

        return blocks

    # ==========================================
    # TEXT (Compatibility)
    # ==========================================

    def extract_text(
        self,
        image
    ):

        blocks = self.extract_blocks(image)

        return "\n".join(
            block["text"]
            for block in blocks
        )


ocr_engine = OCREngine()