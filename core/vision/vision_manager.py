from core.vision.screen_capture import screen_capture
from core.vision.ocr_engine import ocr_engine
from core.vision.vision_engine import vision_engine
from core.vision.window_capture import window_capture
from core.vision.ollama_vision import ollama_vision


class VisionManager:

    def __init__(self):
        self.last_screenshot = None

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

    # ==========================
    # AI VISION (Phase 7)
    # ==========================

    def capture_screen_ai(self, prompt: str = None):
        """Capture screen and analyze with vision AI."""
        image = screen_capture.capture_screen()
        self.last_screenshot = image
        
        if prompt:
            return ollama_vision.analyze_image(image, prompt)
        return ollama_vision.describe_screen(image)

    def capture_region_ai(self, left, top, width, height, prompt: str = None):
        """Capture region and analyze with vision AI."""
        image = screen_capture.capture_region(left, top, width, height)
        
        if prompt:
            return ollama_vision.analyze_image(image, prompt)
        return ollama_vision.describe_screen(image)

    def capture_window_ai(self, prompt: str = None):
        """Capture active window and analyze with vision AI."""
        image = window_capture.capture_active_window()
        
        if image is None:
            return "I couldn't capture the active window."
        
        if prompt:
            return ollama_vision.analyze_image(image, prompt)
        return ollama_vision.describe_screen(image)

    def answer_about_screen(self, question: str):
        """Answer a question about the last captured screen."""
        if self.last_screenshot is None:
            self.last_screenshot = screen_capture.capture_screen()
        return ollama_vision.answer_question(self.last_screenshot, question)

    def read_screen_text_ai(self):
        """Extract text using vision AI (better than OCR for complex layouts)."""
        if self.last_screenshot is None:
            self.last_screenshot = screen_capture.capture_screen()
        return ollama_vision.extract_text(self.last_screenshot)

    def find_ui_element(self, description: str):
        """Find a UI element by description."""
        if self.last_screenshot is None:
            self.last_screenshot = screen_capture.capture_screen()
        return ollama_vision.find_element(self.last_screenshot, description)

    def analyze_code_on_screen(self):
        """Analyze code visible on screen."""
        if self.last_screenshot is None:
            self.last_screenshot = screen_capture.capture_screen()
        return ollama_vision.analyze_code(self.last_screenshot)

    def analyze_error_on_screen(self):
        """Analyze errors visible on screen."""
        if self.last_screenshot is None:
            self.last_screenshot = screen_capture.capture_screen()
        return ollama_vision.analyze_error(self.last_screenshot)

    def compare_screens(self, before_image):
        """Compare current screen with a previous screenshot."""
        current = screen_capture.capture_screen()
        return ollama_vision.summarize_changes(before_image, current)


vision_manager = VisionManager()