"""
Writing Agent - Phase 11
Local text generation, editing, and formatting using Ollama.
No cloud APIs, no costs, fully open source.
"""

import json
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

from brain import ask_nova


class WritingStyle(Enum):
    FORMAL = "formal"
    CASUAL = "casual"
    TECHNICAL = "technical"
    CREATIVE = "creative"
    ACADEMIC = "academic"
    BUSINESS = "business"
    MARKDOWN = "markdown"


class WritingTask(Enum):
    GENERATE = "generate"
    EDIT = "edit"
    REWRITE = "rewrite"
    SUMMARIZE = "summarize"
    EXPAND = "expand"
    OUTLINE = "outline"
    GRAMMAR = "grammar"
    TONE = "tone"


@dataclass
class WritingRequest:
    task: WritingTask
    content: str = ""
    prompt: str = ""
    style: WritingStyle = WritingStyle.FORMAL
    length: str = "medium"  # short, medium, long
    format: str = "text"  # text, markdown, html, json
    context: Dict = None


class WritingAgent:
    def __init__(self):
        self.templates = {
            "email": "Write a professional email: {prompt}",
            "report": "Write a structured report: {prompt}",
            "blog": "Write a blog post: {prompt}",
            "docstring": "Write a docstring for: {prompt}",
            "readme": "Write a README for: {prompt}",
            "changelog": "Write a changelog entry: {prompt}",
            "commit": "Write a git commit message: {prompt}",
            "pr": "Write a pull request description: {prompt}",
        }

    def _build_prompt(self, request: WritingRequest) -> str:
        style_instructions = {
            WritingStyle.FORMAL: "Use formal, professional language. Avoid contractions.",
            WritingStyle.CASUAL: "Use conversational, friendly language. Contractions OK.",
            WritingStyle.TECHNICAL: "Use precise technical terminology. Be specific and detailed.",
            WritingStyle.CREATIVE: "Use engaging, creative language. Show personality.",
            WritingStyle.ACADEMIC: "Use academic style. Cite sources. Objective tone.",
            WritingStyle.BUSINESS: "Use business professional language. Action-oriented.",
            WritingStyle.MARKDOWN: "Format output as Markdown with proper syntax.",
        }

        length_instructions = {
            "short": "Keep it brief (1-2 paragraphs).",
            "medium": "Moderate length (3-5 paragraphs).",
            "long": "Comprehensive (multiple sections).",
        }

        base = f"""You are Nova's Writing Agent. {style_instructions.get(request.style, '')} {length_instructions.get(request.length, '')}

Task: {request.task.value}"""

        if request.format != "text":
            base += f"\nFormat output as {request.format}."

        if request.context:
            base += f"\nContext: {json.dumps(request.context, indent=2)}"

        if request.prompt:
            base += f"\n\nPrompt: {request.prompt}"

        if request.content:
            base += f"\n\nContent to work with:\n{request.content}"

        return base

    def process(self, request: WritingRequest) -> str:
        """Process a writing request."""
        prompt = self._build_prompt(request)
        return ask_nova(prompt)

    # Convenience methods

    def generate(self, prompt: str, style: WritingStyle = WritingStyle.FORMAL,
                 length: str = "medium", format: str = "text") -> str:
        return self.process(WritingRequest(
            task=WritingTask.GENERATE, prompt=prompt, style=style, length=length, format=format
        ))

    def edit(self, content: str, instruction: str = "Improve clarity and flow",
             style: WritingStyle = WritingStyle.FORMAL) -> str:
        return self.process(WritingRequest(
            task=WritingTask.EDIT, content=content, prompt=instruction, style=style
        ))

    def rewrite(self, content: str, style: WritingStyle = WritingStyle.FORMAL) -> str:
        return self.process(WritingRequest(
            task=WritingTask.REWRITE, content=content,
            prompt=f"Rewrite in {style.value} style", style=style
        ))

    def summarize(self, content: str, length: str = "short") -> str:
        return self.process(WritingRequest(
            task=WritingTask.SUMMARIZE, content=content,
            prompt=f"Summarize in {length} form", length=length
        ))

    def expand(self, content: str, style: WritingStyle = WritingStyle.FORMAL) -> str:
        return self.process(WritingRequest(
            task=WritingTask.EXPAND, content=content,
            prompt="Expand with more detail and examples", style=style
        ))

    def outline(self, topic: str, format: str = "markdown") -> str:
        return self.process(WritingRequest(
            task=WritingTask.OUTLINE,
            prompt=f"Create a structured outline for: {topic}",
            format=format
        ))

    def fix_grammar(self, content: str) -> str:
        return self.process(WritingRequest(
            task=WritingTask.GRAMMAR, content=content,
            prompt="Fix grammar, spelling, and punctuation errors"
        ))

    def change_tone(self, content: str, target_style: WritingStyle) -> str:
        return self.process(WritingRequest(
            task=WritingTask.TONE, content=content,
            prompt=f"Change tone to {target_style.value}", style=target_style
        ))

    def from_template(self, template: str, prompt: str, **kwargs) -> str:
        """Use a predefined template."""
        if template in self.templates:
            full_prompt = self.templates[template].format(prompt=prompt)
            return self.generate(full_prompt, **kwargs)
        return f"Unknown template: {template}"

    def write_email(self, prompt: str, **kwargs) -> str:
        return self.from_template("email", prompt, **kwargs)

    def write_report(self, prompt: str, **kwargs) -> str:
        return self.from_template("report", prompt, **kwargs)

    def write_blog(self, prompt: str, **kwargs) -> str:
        return self.from_template("blog", prompt, **kwargs)

    def write_docstring(self, code: str, **kwargs) -> str:
        return self.process(WritingRequest(
            task=WritingTask.GENERATE,
            prompt=f"Write a comprehensive docstring for this code",
            content=code,
            style=WritingStyle.TECHNICAL,
            format="markdown",
            **kwargs
        ))

    def write_readme(self, project_desc: str, **kwargs) -> str:
        return self.from_template("readme", project_desc, **kwargs)

    def write_changelog(self, changes: str, **kwargs) -> str:
        return self.from_template("changelog", changes, **kwargs)

    def write_commit(self, changes: str, **kwargs) -> str:
        return self.from_template("commit", changes, **kwargs)

    def write_pr_description(self, changes: str, **kwargs) -> str:
        return self.from_template("pr", changes, **kwargs)


# Global instance
writing_agent = WritingAgent()


if __name__ == "__main__":
    agent = WritingAgent()

    print("=== Generate ===")
    print(agent.generate("Explain quantum computing to a 10-year-old", style=WritingStyle.CASUAL, length="short"))

    print("\n=== Edit ===")
    text = "The code is not working good. It have many bugs."
    print(agent.edit(text))

    print("\n=== Summarize ===")
    long_text = "Artificial intelligence (AI) is intelligence demonstrated by machines, as opposed to natural intelligence displayed by animals including humans. AI research has been defined as the field of study of intelligent agents, which refers to any system that perceives its environment and takes actions that maximize its chance of achieving its goals."
    print(agent.summarize(long_text))

    print("\n=== Outline ===")
    print(agent.outline("How to build a REST API with FastAPI"))

    print("\n=== Email ===")
    print(agent.write_email("Request meeting with team about project timeline"))

    print("\n=== Docstring ===")
    code = "def fibonacci(n):\n    if n <= 1: return n\n    return fibonacci(n-1) + fibonacci(n-2)"
    print(agent.write_docstring(code))