"""
Research Agent - Phase 10
Local web search + synthesis using Ollama.
No cloud APIs, no costs, fully open source.
"""

import json
import time
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from urllib.parse import quote_plus
import requests
from bs4 import BeautifulSoup

from core.browser_manager import browser_manager
from brain import ask_nova


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    source: str


@dataclass
class ResearchResult:
    query: str
    summary: str
    sources: List[SearchResult]
    key_findings: List[str]
    timestamp: float


class ResearchAgent:
    def __init__(self):
        self.search_engines = {
            "duckduckgo": "https://duckduckgo.com/html/?q={}",
            "bing": "https://www.bing.com/search?q={}",
            "google": "https://www.google.com/search?q={}",
        }
        self.default_engine = "duckduckgo"
        self.max_results = 10
        self.timeout = 10

    def search_web(self, query: str, engine: str = None, max_results: int = None) -> List[SearchResult]:
        """Search the web and return results."""
        engine = engine or self.default_engine
        max_results = max_results or self.max_results

        url = self.search_engines[engine].format(quote_plus(query))

        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            resp = requests.get(url, headers=headers, timeout=self.timeout)
            soup = BeautifulSoup(resp.text, "html.parser")

            results = []
            if engine == "duckduckgo":
                for link in soup.select(".result__url, .result__snippet"):
                    pass
                for result in soup.select(".result"):
                    title_elem = result.select_one(".result__title")
                    url_elem = result.select_one(".result__url")
                    snippet_elem = result.select_one(".result__snippet")
                    if title_elem and url_elem:
                        title = title_elem.get_text(strip=True)
                        link = url_elem.get_text(strip=True)
                        snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""
                        results.append(SearchResult(title, link, snippet, engine))

            elif engine == "bing":
                for result in soup.select(".b_algo"):
                    title_elem = result.select_one("h2 a")
                    snippet_elem = result.select_one(".b_caption p")
                    if title_elem:
                        title = title_elem.get_text(strip=True)
                        link = title_elem.get("href", "")
                        snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""
                        results.append(SearchResult(title, link, snippet, engine))

            return results[:max_results]

        except Exception as e:
            return [SearchResult("Error", "", str(e), engine)]

    def search_and_extract(self, query: str, max_sources: int = 5) -> List[Dict]:
        """Search and extract content from top results."""
        results = self.search_web(query, max_results=max_sources * 2)

        extracted = []
        for r in results[:max_sources]:
            try:
                headers = {"User-Agent": "Mozilla/5.0"}
                resp = requests.get(r.url, headers=headers, timeout=self.timeout)
                soup = BeautifulSoup(resp.text, "html.parser")

                # Remove script/style
                for tag in soup(["script", "style", "nav", "footer", "header"]):
                    tag.decompose()

                text = soup.get_text(separator=" ", strip=True)
                text = re.sub(r"\s+", " ", text)[:3000]

                extracted.append({
                    "title": r.title,
                    "url": r.url,
                    "snippet": r.snippet,
                    "content": text,
                    "source": r.source
                })
            except Exception:
                extracted.append({
                    "title": r.title,
                    "url": r.url,
                    "snippet": r.snippet,
                    "content": "",
                    "source": r.source
                })

        return extracted

    def synthesize(self, query: str, sources: List[Dict]) -> ResearchResult:
        """Synthesize research findings using LLM."""
        if not sources:
            return ResearchResult(query, "No sources found.", [], [], time.time())

        # Prepare source text for LLM
        source_text = ""
        for i, s in enumerate(sources):
            source_text += f"\n--- Source {i+1}: {s['title']} ({s['url']}) ---\n{s['content'][:1500]}\n"

        prompt = f"""Research query: {query}

Sources:
{source_text}

Synthesize a comprehensive answer. Include:
1. A clear summary (2-3 sentences)
2. Key findings (bullet points)
3. Cite sources by number

Be objective and factual. Note conflicting information."""

        try:
            response = ask_nova(prompt)
        except Exception as e:
            response = f"Synthesis failed: {e}"

        # Parse response for key findings
        key_findings = []
        for line in response.split("\n"):
            line = line.strip()
            if line.startswith(("-", "•", "*", "1.", "2.", "3.")):
                key_findings.append(line.lstrip("-•*1234567890. "))

        return ResearchResult(
            query=query,
            summary=response,
            sources=[SearchResult(s["title"], s["url"], s["snippet"], s["source"]) for s in sources],
            key_findings=key_findings[:10],
            timestamp=time.time()
        )

    def research(self, query: str, depth: str = "standard") -> ResearchResult:
        """Full research pipeline."""
        max_sources = {"quick": 3, "standard": 5, "deep": 10}.get(depth, 5)
        sources = self.search_and_extract(query, max_sources)
        return self.synthesize(query, sources)

    def quick_fact(self, query: str) -> str:
        """Quick fact-check style research."""
        result = self.research(query, depth="quick")
        return result.summary

    def compare(self, topic_a: str, topic_b: str, aspect: str = "") -> ResearchResult:
        """Compare two topics."""
        query = f"Compare {topic_a} vs {topic_b}" + (f" on {aspect}" if aspect else "")
        return self.research(query, depth="standard")

    def latest_news(self, topic: str) -> ResearchResult:
        """Get latest news on a topic."""
        query = f"latest news {topic} 2024"
        return self.research(query, depth="standard")

    def technical_research(self, topic: str) -> ResearchResult:
        """Deep technical research."""
        query = f"{topic} technical details implementation best practices"
        return self.research(query, depth="deep")


# Global instance
research_agent = ResearchAgent()


if __name__ == "__main__":
    agent = ResearchAgent()

    print("=== Quick Fact ===")
    print(agent.quick_fact("What is Python GIL?"))

    print("\n=== Research ===")
    result = agent.research("Best practices for REST API design")
    print(f"Summary: {result.summary[:300]}")
    print(f"Key findings: {result.key_findings}")
    print(f"Sources: {len(result.sources)}")