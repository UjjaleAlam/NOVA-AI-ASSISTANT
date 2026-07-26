import mss
import pygetwindow as gw
from PIL import Image

class WindowCapture:

    def get_active_window(self):

        try:
            return gw.getActiveWindow()

        except Exception:
            return None

    def capture_active_window(self):

        window = self.get_active_window()

        if window is None:
            return None

        if window.width <= 0 or window.height <= 0:
            return None

        with mss.mss() as sct:

            monitor = {
                "left": window.left,
                "top": window.top,
                "width": window.width,
                "height": window.height,
            }

            screenshot = sct.grab(monitor)

            return Image.frombytes(
                "RGB",
                screenshot.size,
                screenshot.rgb
            )


window_capture = WindowCapture()