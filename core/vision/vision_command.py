from core.vision.vision_manager import vision_manager
from core.vision.vision_formatter import vision_formatter


class VisionCommands:

    def read_screen(self):
        perception = vision_manager.capture_text()

        return vision_formatter.to_speech(
            perception
        )

    def summarize_screen(self):
        perception = vision_manager.capture_text()

        return vision_formatter.to_speech(
            perception
        )

    def read_region(
        self,
        left,
        top,
        width,
        height
    ):
        perception = vision_manager.capture_region_text(
            left,
            top,
            width,
            height
        )

        return vision_formatter.to_speech(
            perception
        )

    # ==========================
    # AI VISION COMMANDS (Phase 7)
    # ==========================

    def describe_screen(self, detail: str = ""):
        """Describe what's on screen using vision AI."""
        prompt = None
        if detail:
            prompt = f"Focus on: {detail}. Describe what you see."
        return vision_manager.capture_screen_ai(prompt)

    def ask_about_screen(self, question: str):
        """Answer a question about what's on screen."""
        return vision_manager.answer_about_screen(question)

    def read_screen_text(self):
        """Extract text using vision AI."""
        return vision_manager.read_screen_text_ai()

    def find_on_screen(self, description: str):
        """Find a UI element by description."""
        return vision_manager.find_ui_element(description)

    def analyze_code(self):
        """Analyze code visible on screen."""
        return vision_manager.analyze_code_on_screen()

    def analyze_error(self):
        """Analyze errors visible on screen."""
        return vision_manager.analyze_error_on_screen()

    def describe_window(self, detail: str = ""):
        """Describe the active window using vision AI."""
        prompt = None
        if detail:
            prompt = f"Focus on: {detail}. Describe what you see."
        return vision_manager.capture_window_ai(prompt)


vision_commands = VisionCommands()