class LayoutAnalyzer:

    def analyze(
        self,
        ocr_blocks
    ):

        if not ocr_blocks:
            return []

        # Sort from top to bottom, then left to right
        sorted_blocks = sorted(
            ocr_blocks,
            key=lambda block: (
                block["bbox"]["top"],
                block["bbox"]["left"]
            )
        )

        return [
            {
                "text": [block["text"]],
                "bbox": block["bbox"],
                "center": block["center"],
                "width": block["width"],
                "height": block["height"],
                "confidence": block["confidence"]
            }
            for block in sorted_blocks
        ]


layout_analyzer = LayoutAnalyzer()