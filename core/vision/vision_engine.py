from core.vision.layout_analyzer import layout_analyzer
from core.vision.content_classifier import content_classifier


class VisionEngine:

    def process(
        self,
        ocr_blocks
    ):

        blocks = self.clean_blocks(ocr_blocks)

        blocks = layout_analyzer.analyze(blocks)

        blocks = content_classifier.classify(blocks)

        return blocks

    # ==========================================
    # CLEAN OCR BLOCKS
    # ==========================================

    def clean_blocks(
        self,
        blocks
    ):

        cleaned = []
        seen = set()

        for block in blocks:

            text = block["text"].strip()

            if not text:
                continue

            if text in seen:
                continue

            seen.add(text)

            new_block = block.copy()
            new_block["text"] = text

            cleaned.append(new_block)

        return cleaned

    # ==========================================
    # FUTURE FEATURES
    # ==========================================

    def summarize(
        self,
        perception
    ):
        pass


vision_engine = VisionEngine()