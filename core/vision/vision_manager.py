from core.vision.screen_capture import screen_capture
from core.vision.ocr_engine import ocr_engine
from core.vision.vision_engine import vision_engine
from core.vision.window_capture import window_capture
from core.vision.layout_analyzer import layout_analyzer
from core.vision.content_classifier import content_classifier
class VisionManager:

    def capture_text(self):
        image = screen_capture.capture_screen()
        text = ocr_engine.extract_text(image)
        clean_text = vision_engine.clean_text(text)

        blocks = layout_analyzer.analyze(
            clean_text
        )

        return content_classifier.classify(
            blocks
        )

    def capture_region_text(
        self,
        left,
        top,
        width,
        height
    ):
        image = screen_capture.capture_region(
            left,
            top,
            width,
            height
        )

        text = ocr_engine.extract_text(image)
        clean_text = vision_engine.clean_text(text)

        blocks = layout_analyzer.analyze(
            clean_text
        )

        return content_classifier.classify(
            blocks
        )

    def capture_active_window_text(self):
        image = window_capture.capture_active_window()

        if image is None:
            return "I couldn't capture the active window."

        text = ocr_engine.extract_text(
            image
        )

        clean_text = vision_engine.clean_text(
            text
        )

        blocks = layout_analyzer.analyze(
            clean_text
        )

        return content_classifier.classify(
            blocks
        )


vision_manager = VisionManager()