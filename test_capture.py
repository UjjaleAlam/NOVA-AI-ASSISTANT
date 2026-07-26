from pprint import pprint

from core.vision.screen_capture import screen_capture
from core.vision.ocr_engine import ocr_engine

image = screen_capture.capture_screen()

blocks = ocr_engine.extract_blocks(image)

pprint(blocks[:5])