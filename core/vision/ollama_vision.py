"""
Ollama Vision AI - Phase 7
Uses Qwen2-VL or LLaVA via Ollama for local vision understanding.
No cloud, no API costs, fully open source.
"""

import ollama
import base64
import io
from PIL import Image
from typing import Optional, List, Dict, Any
import json


VISION_MODEL = "qwen2-vl:7b"  # or "llava:7b", "llava:13b", "qwen2-vl:2b"
FALLBACK_MODEL = "llava:7b"


class OllamaVision:
    """Local vision AI using Ollama with vision models."""

    def __init__(self, model: str = VISION_MODEL):
        self.model = model
        self._available = None

    def is_available(self) -> bool:
        """Check if vision model is available in Ollama."""
        if self._available is not None:
            return self._available

        try:
            models = ollama.list()
            for m in models.get("models", []):
                name = m.get("name", "") if isinstance(m, dict) else getattr(m, "name", "")
                if self.model in name or FALLBACK_MODEL in name:
                    self._available = True
                    return True
            self._available = False
            return False
        except Exception:
            self._available = False
            return False

    def _ensure_model(self) -> str:
        """Get available model name."""
        if self.is_available():
            return self.model
        try:
            models = ollama.list()
            for m in models.get("models", []):
                name = m.get("name", "") if isinstance(m, dict) else getattr(m, "name", "")
                if "llava" in name.lower() or "qwen2-vl" in name.lower():
                    return name
        except Exception:
            pass
        return FALLBACK_MODEL

    def _image_to_base64(self, image: Image.Image) -> str:
        """Convert PIL image to base64 string."""
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    def analyze_image(
        self,
        image: Image.Image,
        prompt: str = "Describe what you see in this image in detail.",
        system_prompt: Optional[str] = None
    ) -> str:
        """Analyze an image with a custom prompt."""
        model = self._ensure_model()

        if not self.is_available():
            return f"Vision model not available. Please pull {VISION_MODEL} or {FALLBACK_MODEL} in Ollama."

        try:
            image_b64 = self._image_to_base64(image)

            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})

            messages.append({
                "role": "user",
                "content": prompt,
                "images": [image_b64]
            })

            response = ollama.chat(
                model=model,
                messages=messages,
                options={
                    "num_predict": 512,
                    "temperature": 0.3
                }
            )

            return response["message"]["content"].strip()

        except Exception as e:
            return f"Vision analysis failed: {e}"

    def describe_screen(self, image: Image.Image) -> str:
        """Describe what's on the screen."""
        prompt = """Describe what you see on this screen. Include:
- Applications and windows visible
- Text content (menus, buttons, titles)
- Layout and organization
- Any notable UI elements

Be concise but comprehensive. Focus on actionable information for a user."""
        return self.analyze_image(image, prompt)

    def answer_question(self, image: Image.Image, question: str) -> str:
        """Answer a specific question about the image."""
        prompt = f"Answer this question about the image: {question}"
        return self.analyze_image(image, prompt)

    def extract_text(self, image: Image.Image) -> str:
        """Extract all readable text from the image."""
        prompt = """Extract ALL readable text from this image. 
Include text from: menus, buttons, window titles, dialogs, 
code editors, terminal output, web pages, documents.
Preserve formatting where possible. Return only the extracted text."""
        return self.analyze_image(image, prompt)

    def find_element(self, image: Image.Image, description: str) -> str:
        """Find a specific UI element by description."""
        prompt = f"""Find the UI element matching: "{description}"
Return its location (top-left, center, bottom-right, etc.), 
what text it contains, and what type of element it is 
(button, link, input, menu, tab, etc.)."""
        return self.analyze_image(image, prompt)

    def analyze_code(self, image: Image.Image) -> str:
        """Analyze code visible on screen."""
        prompt = """Analyze the code visible in this image.
Identify: language, framework, key functions/classes,
potential issues, and what the code does.
Be specific and technical."""
        return self.analyze_image(image, prompt)

    def analyze_error(self, image: Image.Image) -> str:
        """Analyze error messages on screen."""
        prompt = """Analyze any error messages, stack traces, or warnings visible.
Identify: error type, likely cause, file/line if shown,
and suggest fixes. Be specific and actionable."""
        return self.analyze_image(image, prompt)

    def summarize_changes(self, before: Image.Image, after: Image.Image) -> str:
        """Compare two screenshots and summarize changes."""
        model = self._ensure_model()
        if not self.is_available():
            return "Vision model not available."

        try:
            before_b64 = self._image_to_base64(before)
            after_b64 = self._image_to_base64(after)

            response = ollama.chat(
                model=model,
                messages=[{
                    "role": "user",
                    "content": "Compare these two screenshots. What changed? Describe additions, removals, modifications, and state changes.",
                    "images": [before_b64, after_b64]
                }],
                options={"num_predict": 512, "temperature": 0.3}
            )
            return response["message"]["content"].strip()
        except Exception as e:
            return f"Comparison failed: {e}"


# Global instance
ollama_vision = OllamaVision()