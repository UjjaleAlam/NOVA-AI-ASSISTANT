from core.vision.vision_manager import vision_manager

text = vision_manager.capture_region_text(
    200,
    200,
    600,
    400
)

print(text)