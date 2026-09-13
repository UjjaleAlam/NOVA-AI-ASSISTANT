"""
Coding Agent - Phase 9
Local code generation, analysis, and editing using Ollama (Qwen3/CodeLlama).
No cloud, no API costs, fully open source.
"""

import ollama
import os
import json
import re
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

CODING_MODEL = "qwen3:8b"  # or "codellama:7b", "deepseek-coder:6.7b"
SYSTEM_PROMPT = """You are Nova's Coding Agent. You help with:
- Writing, editing, and refactoring code
- Explaining code and algorithms
- Debugging and fixing bugs
- Code reviews and best practices
- Generating tests and documentation

Rules:
- Give concise, practical answers
- Show code in markdown blocks with language
- Explain complex parts briefly
- Prefer standard libraries and common patterns
- Ask clarifying questions if needed
- Never use external APIs or cloud services
"""


@dataclass
class CodeContext:
    file_path: str
    content: str
    language: str
    project_context: Dict = None


class CodingAgent:
    def __init__(self, model: str = CODING_MODEL):
        self.model = model

    def _chat(self, messages: List[Dict], options: Dict = None) -> str:
        default_options = {
            "num_predict": 2048,
            "temperature": 0.2,
            "top_p": 0.95
        }
        if options:
            default_options.update(options)

        try:
            response = ollama.chat(
                model=self.model,
                messages=messages,
                options=default_options
            )
            return response["message"]["content"].strip()
        except Exception as e:
            return f"Error: {e}"

    def generate_code(
        self,
        prompt: str,
        language: str = "python",
        context: str = None
    ) -> str:
        """Generate code from a natural language prompt."""
        system = SYSTEM_PROMPT + f"\nTarget language: {language}"
        if context:
            system += f"\n\nProject context:\n{context}"

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt}
        ]
        return self._chat(messages)

    def explain_code(self, code: str, language: str = "python") -> str:
        """Explain what code does."""
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT + "\nExplain code clearly and concisely."},
            {"role": "user", "content": f"Explain this {language} code:\n\n```{language}\n{code}\n```"}
        ]
        return self._chat(messages)

    def review_code(self, code: str, language: str = "python") -> str:
        """Review code for bugs, style, and improvements."""
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT + "\nReview code thoroughly. Find bugs, security issues, performance problems, and style violations."},
            {"role": "user", "content": f"Review this {language} code:\n\n```{language}\n{code}\n```"}
        ]
        return self._chat(messages)

    def fix_code(self, code: str, error: str, language: str = "python") -> str:
        """Fix code based on an error message."""
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT + "\nFix the code. Return only the corrected code."},
            {"role": "user", "content": f"Error: {error}\n\nCode:\n```{language}\n{code}\n```"}
        ]
        return self._chat(messages)

    def refactor_code(self, code: str, instruction: str, language: str = "python") -> str:
        """Refactor code based on instructions."""
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT + "\nRefactor the code as instructed. Return only the refactored code."},
            {"role": "user", "content": f"Instruction: {instruction}\n\nCode:\n```{language}\n{code}\n```"}
        ]
        return self._chat(messages)

    def generate_tests(self, code: str, language: str = "python", framework: str = "pytest") -> str:
        """Generate unit tests for code."""
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT + f"\nGenerate comprehensive {framework} tests. Return only test code."},
            {"role": "user", "content": f"Generate {framework} tests for this {language} code:\n\n```{language}\n{code}\n```"}
        ]
        return self._chat(messages)

    def generate_docs(self, code: str, language: str = "python", style: str = "docstring") -> str:
        """Generate documentation for code."""
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT + f"\nGenerate {style} documentation. Return only the documented code."},
            {"role": "user", "content": f"Add {style} documentation to this {language} code:\n\n```{language}\n{code}\n```"}
        ]
        return self._chat(messages)

    def analyze_file(self, file_path: str) -> Dict:
        """Analyze a code file."""
        if not os.path.exists(file_path):
            return {"error": "File not found"}

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        ext = Path(file_path).suffix.lower()
        lang_map = {
            '.py': 'python', '.js': 'javascript', '.ts': 'typescript',
            '.java': 'java', '.cpp': 'cpp', '.c': 'c', '.cs': 'csharp',
            '.go': 'go', '.rs': 'rust', '.php': 'php', '.rb': 'ruby',
            '.swift': 'swift', '.kt': 'kotlin', '.scala': 'scala',
            '.html': 'html', '.css': 'css', '.sql': 'sql',
            '.sh': 'bash', '.ps1': 'powershell', '.bat': 'batch'
        }
        language = lang_map.get(ext, 'text')

        analysis = self._chat([
            {"role": "system", "content": SYSTEM_PROMPT + "\nAnalyze the code file. Return JSON with: summary, language, complexity, issues, suggestions."},
            {"role": "user", "content": f"Analyze this {language} file:\n\n```{language}\n{content}\n```"}
        ])

        return {
            "file_path": file_path,
            "language": language,
            "lines": len(content.splitlines()),
            "size": len(content),
            "analysis": analysis
        }

    def find_bugs(self, code: str, language: str = "python") -> str:
        """Find potential bugs in code."""
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT + "\nFind bugs, edge cases, and potential issues. Be specific."},
            {"role": "user", "content": f"Find bugs in this {language} code:\n\n```{language}\n{code}\n```"}
        ]
        return self._chat(messages)

    def optimize_code(self, code: str, language: str = "python") -> str:
        """Optimize code for performance."""
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT + "\nOptimize the code for performance. Return only the optimized code."},
            {"role": "user", "content": f"Optimize this {language} code:\n\n```{language}\n{code}\n```"}
        ]
        return self._chat(messages)

    def convert_code(self, code: str, from_lang: str, to_lang: str) -> str:
        """Convert code from one language to another."""
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT + f"\nConvert {from_lang} code to {to_lang}. Preserve logic and idioms."},
            {"role": "user", "content": f"Convert this {from_lang} to {to_lang}:\n\n```{from_lang}\n{code}\n```"}
        ]
        return self._chat(messages)


# Global instance
coding_agent = CodingAgent()


def detect_language(file_path: str) -> str:
    ext = Path(file_path).suffix.lower()
    lang_map = {
        '.py': 'python', '.js': 'javascript', '.ts': 'typescript',
        '.jsx': 'javascript', '.tsx': 'typescript', '.vue': 'vue',
        '.java': 'java', '.cpp': 'cpp', '.cc': 'cpp', '.cxx': 'cpp',
        '.c': 'c', '.h': 'c', '.hpp': 'cpp', '.cs': 'csharp',
        '.go': 'go', '.rs': 'rust', '.php': 'php', '.rb': 'ruby',
        '.swift': 'swift', '.kt': 'kotlin', '.scala': 'scala',
        '.html': 'html', '.htm': 'html', '.css': 'css', '.scss': 'scss',
        '.sql': 'sql', '.sh': 'bash', '.ps1': 'powershell', '.bat': 'batch',
        '.json': 'json', '.yaml': 'yaml', '.yml': 'yaml', '.toml': 'toml',
        '.xml': 'xml', '.md': 'markdown', '.rst': 'rst',
        '.dockerfile': 'dockerfile', '.tf': 'terraform'
    }
    return lang_map.get(ext, 'text')


if __name__ == "__main__":
    # Test
    agent = CodingAgent()

    # Generate code
    print("=== Generate Code ===")
    code = agent.generate_code("Create a Python class for a simple cache with TTL")
    print(code)

    print("\n=== Explain Code ===")
    explanation = agent.explain_code(code)
    print(explanation)

    print("\n=== Review Code ===")
    review = agent.review_code(code)
    print(review)

    print("\n=== Generate Tests ===")
    tests = agent.generate_tests(code)
    print(tests)