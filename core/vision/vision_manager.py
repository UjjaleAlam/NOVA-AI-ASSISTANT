from core.vision.screen_capture import screen_capture
from core.vision.ocr_engine import ocr_engine
from core.vision.vision_engine import vision_engine
from core.vision.window_capture import window_capture
class VisionManager:

    def capture_text(self):
        image = screen_capture.capture_screen()
        ocr_blocks = ocr_engine.extract_blocks(image)

        return vision_engine.process(ocr_blocks)

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

        ocr_blocks = ocr_engine.extract_blocks(image)

        return vision_engine.process(ocr_blocks)

    def capture_active_window_text(self):
        image = window_capture.capture_active_window()

        if image is None:
            return "I couldn't capture the active window."

        ocr_blocks = ocr_engine.extract_blocks(image)

        return vision_engine.process(ocr_blocks)


vision_manager = VisionManager()