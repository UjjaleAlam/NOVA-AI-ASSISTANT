from core.vision.screen_capture import screen_capture
from core.vision.ocr_engine import ocr_engine
from core.vision.vision_engine import vision_engine

class VisionManager:

    def capture_text(self):
        image = screen_capture.capture_screen()
        text = ocr_engine.extract_text(image)
        return vision_engine.clean_text(text)

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
        return vision_engine.clean_text(text)


vision_manager = VisionManager()