from core.vision.vision_manager import vision_manager


class VisionCommands:

    def read_screen(self):
        return vision_manager.capture_text()

    def read_region(
        self,
        left,
        top,
        width,
        height
    ):
        return vision_manager.capture_region_text(
            left,
            top,
            width,
            height
        )


vision_commands = VisionCommands()