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


vision_commands = VisionCommands()