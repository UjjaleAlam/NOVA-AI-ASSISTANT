from PIL import Image
import mss


class ScreenCapture:

    def capture_screen(self):

        with mss.mss() as sct:

            screenshot = sct.grab(
                sct.monitors[1]
            )

            image = Image.frombytes(
                "RGB",
                screenshot.size,
                screenshot.rgb
            )

            return image

    def capture_primary_monitor(self):
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            screenshot = sct.grab(monitor)

            return Image.frombytes(
                "RGB",
                screenshot.size,
                screenshot.rgb
            )

    def capture_region(
        self,
        left,
        top,
        width,
        height
    ):
        with mss.mss() as sct:
            monitor = {
                "left": left,
                "top": top,
                "width": width,
                "height": height,
            }

            screenshot = sct.grab(monitor)

            return Image.frombytes(
                "RGB",
                screenshot.size,
                screenshot.rgb
            )


screen_capture = ScreenCapture()