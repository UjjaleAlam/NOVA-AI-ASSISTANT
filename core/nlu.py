"""
Natural Language Understanding - Phase 16
Intent classification, entity extraction, slot filling, and dialogue management.
Fully local using Ollama + pattern matching, no cloud dependencies.
"""

import re
import json
import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict, field
from enum import Enum
from collections import defaultdict

from brain import ask_nova


class IntentCategory(Enum):
    """High-level intent categories."""
    FILE_OPERATION = "file_operation"
    APP_CONTROL = "app_control"
    SYSTEM_CONTROL = "system_control"
    INFORMATION_QUERY = "information_query"
    COMMUNICATION = "communication"
    CREATION = "creation"
    ANALYSIS = "analysis"
    NAVIGATION = "navigation"
    SETTINGS = "settings"
    LECTURE = "lecture"
    CODING = "coding"
    RESEARCH = "research"
    WRITING = "writing"
    OFFICE = "office"
    CONTEXT = "context"
    PERSONAL = "personal"
    VISION = "vision"
    UNKNOWN = "unknown"


@dataclass
class Entity:
    """Extracted entity."""
    type: str
    value: str
    start: int
    end: int
    confidence: float = 1.0
    metadata: Dict = field(default_factory=dict)


@dataclass
class Intent:
    """Classified intent with slots."""
    category: IntentCategory
    name: str
    confidence: float
    slots: Dict[str, Any] = field(default_factory=dict)
    entities: List[Entity] = field(default_factory=list)
    raw_text: str = ""


@dataclass
class NLUResult:
    """Complete NLU processing result."""
    intent: Intent
    entities: List[Entity]
    original_text: str
    processed_text: str
    language: str = "en"
    timestamp: float = field(default_factory=time.time)


# ==========================================
# ENTITY EXTRACTORS
# ==========================================

class EntityExtractor:
    """Rule-based entity extraction."""

    # File/path patterns
    FILE_PATTERN = re.compile(
        r'(?:[a-zA-Z]:[\\/])?(?:[^<>:"|?*\n\r]+\/?)*[^<>:"|?*\n\r]+\.[a-zA-Z0-9]+',
        re.IGNORECASE
    )

    # URL pattern
    URL_PATTERN = re.compile(
        r'https?://[^\s<>"\']+|www\.[^\s<>"\']+\.[^\s<>"\']+',
        re.IGNORECASE
    )

    # Email pattern
    EMAIL_PATTERN = re.compile(
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    )

    # Time patterns
    TIME_PATTERN = re.compile(
        r'\b(?:[01]?\d|2[0-3]):[0-5]\d(?::[0-5]\d)?\b'
    )

    DATE_PATTERN = re.compile(
        r'\b(?:\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{4}[-/]\d{1,2}[-/]\d{1,2})\b'
    )

    # Number patterns
    NUMBER_PATTERN = re.compile(
        r'\b\d+(?:[.,]\d+)?\b'
    )

    # Version pattern
    VERSION_PATTERN = re.compile(
        r'\bv?\d+\.\d+(?:\.\d+)?(?:-[a-zA-Z0-9]+)?\b'
    )

    # App names (common)
    COMMON_APPS = {
        'chrome', 'firefox', 'edge', 'safari', 'brave', 'opera',
        'vscode', 'visual studio code', 'intellij', 'pycharm', 'webstorm',
        'notepad', 'notepad++', 'sublime', 'vim', 'emacs',
        'terminal', 'cmd', 'powershell', 'bash', 'zsh',
        'discord', 'slack', 'teams', 'zoom', 'skype',
        'spotify', 'vlc', 'mpv', 'potplayer',
        'steam', 'epic games', 'origin', 'uplay',
        'photoshop', 'illustrator', 'figma', 'sketch',
        'word', 'excel', 'powerpoint', 'outlook', 'onenote',
        'explorer', 'finder', 'file explorer',
    }

    def __init__(self):
        self.custom_entities = {}

    def add_custom_entity(self, entity_type: str, pattern: str, flags: int = re.IGNORECASE):
        """Add a custom entity pattern."""
        self.custom_entities[entity_type] = re.compile(pattern, flags)

    def extract(self, text: str) -> List[Entity]:
        """Extract all entities from text."""
        entities = []

        # Built-in extractors
        entities.extend(self._extract_files(text))
        entities.extend(self._extract_urls(text))
        entities.extend(self._extract_emails(text))
        entities.extend(self._extract_times(text))
        entities.extend(self._extract_dates(text))
        entities.extend(self._extract_numbers(text))
        entities.extend(self._extract_versions(text))
        entities.extend(self._extract_apps(text))

        # Custom extractors
        for entity_type, pattern in self.custom_entities.items():
            entities.extend(self._extract_with_pattern(text, entity_type, pattern))

        # Sort by position
        entities.sort(key=lambda e: e.start)

        # Remove overlaps (keep higher confidence)
        entities = self._resolve_overlaps(entities)

        return entities

    def _extract_files(self, text: str) -> List[Entity]:
        entities = []
        for match in self.FILE_PATTERN.finditer(text):
            entities.append(Entity(
                type="file_path",
                value=match.group(),
                start=match.start(),
                end=match.end(),
                confidence=0.8
            ))
        return entities

    def _extract_urls(self, text: str) -> List[Entity]:
        entities = []
        for match in self.URL_PATTERN.finditer(text):
            entities.append(Entity(
                type="url",
                value=match.group(),
                start=match.start(),
                end=match.end(),
                confidence=0.95
            ))
        return entities

    def _extract_emails(self, text: str) -> List[Entity]:
        entities = []
        for match in self.EMAIL_PATTERN.finditer(text):
            entities.append(Entity(
                type="email",
                value=match.group(),
                start=match.start(),
                end=match.end(),
                confidence=0.95
            ))
        return entities

    def _extract_times(self, text: str) -> List[Entity]:
        entities = []
        for match in self.TIME_PATTERN.finditer(text):
            entities.append(Entity(
                type="time",
                value=match.group(),
                start=match.start(),
                end=match.end(),
                confidence=0.9
            ))
        return entities

    def _extract_dates(self, text: str) -> List[Entity]:
        entities = []
        for match in self.DATE_PATTERN.finditer(text):
            entities.append(Entity(
                type="date",
                value=match.group(),
                start=match.start(),
                end=match.end(),
                confidence=0.85
            ))
        return entities

    def _extract_numbers(self, text: str) -> List[Entity]:
        entities = []
        for match in self.NUMBER_PATTERN.finditer(text):
            # Skip if part of version or time
            context = text[max(0, match.start()-3):match.end()+3]
            if re.search(r'v?\d+\.\d+', context) or re.search(r'\d+:\d+', context):
                continue
            entities.append(Entity(
                type="number",
                value=match.group(),
                start=match.start(),
                end=match.end(),
                confidence=0.7
            ))
        return entities

    def _extract_versions(self, text: str) -> List[Entity]:
        entities = []
        for match in self.VERSION_PATTERN.finditer(text):
            entities.append(Entity(
                type="version",
                value=match.group(),
                start=match.start(),
                end=match.end(),
                confidence=0.9
            ))
        return entities

    def _extract_apps(self, text: str) -> List[Entity]:
        entities = []
        text_lower = text.lower()
        for app in self.COMMON_APPS:
            # Word boundary search
            pattern = r'\b' + re.escape(app) + r'\b'
            for match in re.finditer(pattern, text_lower):
                entities.append(Entity(
                    type="application",
                    value=app,
                    start=match.start(),
                    end=match.end(),
                    confidence=0.85
                ))
        return entities

    def _extract_with_pattern(self, text: str, entity_type: str, pattern: re.Pattern) -> List[Entity]:
        entities = []
        for match in pattern.finditer(text):
            entities.append(Entity(
                type=entity_type,
                value=match.group(),
                start=match.start(),
                end=match.end(),
                confidence=0.8
            ))
        return entities

    def _resolve_overlaps(self, entities: List[Entity]) -> List[Entity]:
        """Remove overlapping entities, keeping higher confidence."""
        if not entities:
            return []

        result = [entities[0]]
        for entity in entities[1:]:
            last = result[-1]
            # Check overlap
            if entity.start < last.end:
                # Overlap - keep higher confidence
                if entity.confidence > last.confidence:
                    result[-1] = entity
            else:
                result.append(entity)
        return result


# ==========================================
# INTENT CLASSIFIER
# ==========================================

class IntentClassifier:
    """Classify user intent using patterns and LLM fallback."""

    # Intent patterns (regex -> intent_name, category)
    INTENT_PATTERNS = [
        # File operations
        (r'\b(?:find|search|locate|show|get|pull|list)\s+(?:file|document|pdf|image|video|audio|code|python)\b', "find_files", IntentCategory.FILE_OPERATION),
        (r'\b(?:open|launch|start)\s+(?:file|document|folder)\b', "open_file", IntentCategory.FILE_OPERATION),
        (r'\b(?:create|make|new)\s+(?:file|folder|document)\b', "create_file", IntentCategory.FILE_OPERATION),
        (r'\b(?:delete|remove|trash)\s+(?:file|folder)\b', "delete_file", IntentCategory.FILE_OPERATION),
        (r'\b(?:copy|move|rename)\s+(?:file|folder)\b', "manage_file", IntentCategory.FILE_OPERATION),

        # App control
        (r'\b(?:open|launch|start)\s+(?:app|application|program)\b', "open_app", IntentCategory.APP_CONTROL),
        (r'\b(?:close|quit|exit|kill)\s+(?:app|application|program)\b', "close_app", IntentCategory.APP_CONTROL),
        (r'\b(?:switch|change)\s+to\s+\w+', "switch_app", IntentCategory.APP_CONTROL),

        # System control
        (r'\b(?:shutdown|restart|reboot|sleep|hibernate|lock)\b', "system_power", IntentCategory.SYSTEM_CONTROL),
        (r'\b(?:volume\s+(?:up|down|mute|unmute)|mute|unmute)\b', "volume_control", IntentCategory.SYSTEM_CONTROL),
        (r'\b(?:brightness\s+(?:up|down|set))\b', "brightness_control", IntentCategory.SYSTEM_CONTROL),
        (r'\b(?:maximize|minimize|restore|resize)\s+(?:window|app)\b', "window_control", IntentCategory.SYSTEM_CONTROL),

        # Information queries
        (r'\b(?:what|who|where|when|why|how)\s+(?:is|are|was|were)\b', "factual_query", IntentCategory.INFORMATION_QUERY),
        (r'\b(?:explain|describe|define|meaning of)\b', "explanation", IntentCategory.INFORMATION_QUERY),
        (r'\b(?:weather|temperature|forecast)\b', "weather", IntentCategory.INFORMATION_QUERY),
        (r'\b(?:time|date|clock)\b', "datetime_query", IntentCategory.INFORMATION_QUERY),

        # Web/Search
        (r'\b(?:search|google|look up|find)\s+(?:for|about)?\s*\w+', "web_search", IntentCategory.INFORMATION_QUERY),
        (r'\b(?:youtube|video)\s+(?:search|play)\b', "youtube_search", IntentCategory.INFORMATION_QUERY),

        # Coding
        (r'\b(?:write|generate|create)\s+(?:code|function|class|script)\b', "generate_code", IntentCategory.CODING),
        (r'\b(?:explain|review|debug|fix|optimize)\s+(?:code|function|error)\b', "analyze_code", IntentCategory.CODING),
        (r'\b(?:test|pytest|unit test)\s+\w+', "generate_tests", IntentCategory.CODING),

        # Research
        (r'\b(?:research|investigate|look into)\b', "research", IntentCategory.RESEARCH),
        (r'\b(?:compare|versus|vs\.)\b', "compare", IntentCategory.RESEARCH),

        # Writing
        (r'\b(?:write|compose|draft)\s+(?:email|report|blog|article|summary)\b', "write_content", IntentCategory.WRITING),
        (r'\b(?:edit|improve|rewrite|proofread|summarize)\b', "edit_content", IntentCategory.WRITING),
        (r'\b(?:translate|translation)\b', "translate", IntentCategory.WRITING),

        # Lecture
        (r'\b(?:start|begin|record)\s+(?:lecture|recording|meeting)\b', "start_lecture", IntentCategory.LECTURE),
        (r'\b(?:pause|stop|end|finish)\s+(?:lecture|recording|meeting)\b', "end_lecture", IntentCategory.LECTURE),

        # Office
        (r'\b(?:create|make|new)\s+(?:document|spreadsheet|presentation|csv|json)\b', "create_document", IntentCategory.OFFICE),
        (r'\b(?:convert|export)\s+(?:to|as)\s+(?:pdf|csv|excel|word|markdown)\b', "convert_document", IntentCategory.OFFICE),

        # Context/Memory
        (r'\b(?:remember|recall|forget|memory)\b', "memory", IntentCategory.CONTEXT),
        (r'\b(?:preference|prefer|setting)\b', "preference", IntentCategory.CONTEXT),

        # Personal
        (r'\b(?:habit|routine|suggestion)\b', "personal", IntentCategory.PERSONAL),

        # Vision
        (r'\b(?:describe|analyze|read|what.*screen|what.*see)\b', "vision", IntentCategory.VISION),

        # Settings
        (r'\b(?:set|change|configure)\s+(?:temperature|context|model|gpu)\b', "settings", IntentCategory.SETTINGS),
    ]

    def __init__(self):
        self.compiled_patterns = [
            (re.compile(pattern, re.IGNORECASE), intent_name, category)
            for pattern, intent_name, category in self.INTENT_PATTERNS
        ]

    def classify(self, text: str, entities: List[Entity] = None) -> Intent:
        """Classify intent from text."""
        text_lower = text.lower().strip()

        # Pattern matching
        best_match = None
        best_confidence = 0.0

        for pattern, intent_name, category in self.compiled_patterns:
            match = pattern.search(text_lower)
            if match:
                # Confidence based on match length and position
                match_len = match.end() - match.start()
                text_len = len(text_lower)
                confidence = min(0.6 + (match_len / text_len) * 0.3, 0.9)

                if confidence > best_confidence:
                    best_confidence = confidence
                    best_match = (intent_name, category, match)

        if best_match:
            intent_name, category, match = best_match
            slots = self._extract_slots(text, entities, intent_name)
            return Intent(
                category=category,
                name=intent_name,
                confidence=best_confidence,
                slots=slots,
                entities=entities or [],
                raw_text=text
            )

        # Fallback to LLM classification
        return self._llm_classify(text, entities)

    def _extract_slots(self, text: str, entities: List[Entity], intent_name: str) -> Dict:
        """Extract slots based on intent and entities."""
        slots = {}

        # Map entities to slots based on intent
        slot_mapping = {
            "find_files": {"file_type": "file_path", "query": "text"},
            "open_file": {"file_path": "file_path"},
            "open_app": {"app_name": "application"},
            "close_app": {"app_name": "application"},
            "web_search": {"query": "text"},
            "generate_code": {"language": "text", "requirement": "text"},
            "analyze_code": {"code": "text", "issue": "text"},
            "write_content": {"content_type": "text", "topic": "text"},
            "edit_content": {"content": "text", "instruction": "text"},
            "research": {"topic": "text", "depth": "text"},
            "compare": {"item_a": "text", "item_b": "text"},
            "create_document": {"doc_type": "text", "title": "text"},
            "start_lecture": {"title": "text"},
            "system_power": {"action": "text"},
            "volume_control": {"action": "text", "level": "number"},
        }

        mapping = slot_mapping.get(intent_name, {})

        for slot_name, entity_type in mapping.items():
            if entity_type == "text":
                # Extract relevant text portion
                slots[slot_name] = self._extract_slot_text(text, intent_name)
            else:
                # Find matching entity
                for ent in entities or []:
                    if ent.type == entity_type:
                        slots[slot_name] = ent.value
                        break

        return slots

    def _extract_slot_text(self, text: str, intent_name: str) -> str:
        """Extract relevant text for a slot."""
        # Remove trigger words
        triggers = {
            "find_files": ["find", "search", "locate", "show", "get", "pull", "list", "file", "files", "document", "documents", "all", "my"],
            "web_search": ["search", "google", "look up", "find", "for", "about"],
            "generate_code": ["write", "generate", "create", "code", "function", "class", "script", "in", "using"],
            "research": ["research", "investigate", "look into", "about", "on"],
            "write_content": ["write", "compose", "draft", "email", "report", "blog", "article", "summary", "about", "on"],
        }

        ignore_words = triggers.get(intent_name, [])
        words = [w for w in text.split() if w.lower() not in ignore_words]
        return " ".join(words).strip()

    def _llm_classify(self, text: str, entities: List[Entity] = None) -> Intent:
        """Fallback LLM-based classification."""
        prompt = f"""Classify this user command into an intent category and extract key information.

Command: "{text}"

Categories: {', '.join([c.value for c in IntentCategory])}

Return JSON with:
- category: one of the categories
- name: specific intent name
- confidence: 0.0-1.0
- slots: key-value pairs of extracted parameters

Be concise."""

        try:
            response = ask_nova(prompt)
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return Intent(
                    category=IntentCategory(data.get("category", "unknown")),
                    name=data.get("name", "unknown"),
                    confidence=data.get("confidence", 0.5),
                    slots=data.get("slots", {}),
                    entities=entities or [],
                    raw_text=text
                )
        except Exception:
            pass

        # Ultimate fallback
        return Intent(
            category=IntentCategory.UNKNOWN,
            name="unknown",
            confidence=0.1,
            slots={},
            entities=entities or [],
            raw_text=text
        )


# ==========================================
# DIALOGUE MANAGER
# ==========================================

class DialogueManager:
    """Manage multi-turn dialogue state."""

    def __init__(self):
        self.context_stack = []
        self.current_topic = None
        self.pending_slots = {}
        self.history = []

    def add_turn(self, user_text: str, nlu_result: NLUResult, response: str):
        """Add a dialogue turn."""
        turn = {
            "user": user_text,
            "intent": nlu_result.intent.name,
            "entities": [asdict(e) for e in nlu_result.entities],
            "response": response,
            "timestamp": time.time()
        }
        self.history.append(turn)

        # Manage context stack
        if nlu_result.intent.category == IntentCategory.INFORMATION_QUERY:
            self.current_topic = nlu_result.intent.name

        # Check for follow-up
        if self._is_followup(nlu_result):
            self._handle_followup(nlu_result)

    def _is_followup(self, nlu_result: NLUResult) -> bool:
        """Check if this is a follow-up to previous turn."""
        if not self.history:
            return False

        last_intent = self.history[-1]["intent"]
        # Same category or explicit follow-up words
        followup_words = ["it", "that", "this", "them", "those", "more", "also", "then", "next"]
        return any(w in nlu_result.original_text.lower() for w in followup_words)

    def _handle_followup(self, nlu_result: NLUResult):
        """Handle follow-up by inheriting context."""
        last_turn = self.history[-1]
        # Inherit entities from previous turn if not specified
        for entity_dict in last_turn["entities"]:
            entity = Entity(**entity_dict)
            # Check if entity type not in current
            if not any(e.type == entity.type for e in nlu_result.entities):
                nlu_result.entities.append(entity)

    def get_context_summary(self) -> str:
        """Get a summary of dialogue context."""
        if not self.history:
            return "No previous context."

        recent = self.history[-3:]
        summary = "Recent dialogue:\n"
        for turn in recent:
            summary += f"User: {turn['user'][:100]}\n"
            summary += f"Intent: {turn['intent']}\n"
        return summary

    def clear_context(self):
        """Clear dialogue context."""
        self.context_stack = []
        self.current_topic = None
        self.pending_slots = {}


# ==========================================
# MAIN NLU PROCESSOR
# ==========================================

class NLUProcessor:
    """Main NLU processing pipeline."""

    def __init__(self):
        self.entity_extractor = EntityExtractor()
        self.intent_classifier = IntentClassifier()
        self.dialogue_manager = DialogueManager()

    def process(self, text: str) -> NLUResult:
        """Process text through full NLU pipeline."""
        # Preprocess
        processed = self._preprocess(text)

        # Extract entities
        entities = self.entity_extractor.extract(processed)

        # Classify intent
        intent = self.intent_classifier.classify(processed, entities)

        # Create result
        result = NLUResult(
            intent=intent,
            entities=entities,
            original_text=text,
            processed_text=processed
        )

        # Update dialogue manager
        # Note: response would be added by caller
        # self.dialogue_manager.add_turn(text, result, "")

        return result

    def _preprocess(self, text: str) -> str:
        """Preprocess text for better understanding."""
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text.strip())

        # Expand contractions
        contractions = {
            "can't": "cannot", "won't": "will not", "n't": " not",
            "i'm": "i am", "you're": "you are", "it's": "it is",
            "that's": "that is", "what's": "what is", "where's": "where is",
            "how's": "how is", "who's": "who is", "there's": "there is",
            "i've": "i have", "you've": "you have", "we've": "we have",
            "i'll": "i will", "you'll": "you will", "we'll": "we will",
            "i'd": "i would", "you'd": "you would", "we'd": "we would",
        }
        for contraction, expansion in contractions.items():
            text = re.sub(r'\b' + contraction + r'\b', expansion, text, flags=re.IGNORECASE)

        return text


# Global instance
nlu_processor = NLUProcessor()


# Convenience functions
def parse(text: str) -> NLUResult:
    return nlu_processor.process(text)

def extract_entities(text: str) -> List[Entity]:
    return nlu_processor.entity_extractor.extract(text)

def classify_intent(text: str, entities: List[Entity] = None) -> Intent:
    return nlu_processor.intent_classifier.classify(text, entities)

def get_dialogue_context() -> str:
    return nlu_processor.dialogue_manager.get_context_summary()

def clear_dialogue_context():
    nlu_processor.dialogue_manager.clear_context()


# Voice command integration
def nlu_debug(text: str) -> str:
    """Debug NLU processing - return formatted result."""
    result = parse(text)

    output = f"Text: {result.original_text}\n"
    output += f"Processed: {result.processed_text}\n"
    output += f"Intent: {result.intent.name} ({result.intent.category.value}) [{result.intent.confidence:.0%}]\n"

    if result.intent.slots:
        output += "Slots:\n"
        for k, v in result.intent.slots.items():
            output += f"  {k}: {v}\n"

    if result.entities:
        output += "Entities:\n"
        for e in result.entities:
            output += f"  {e.type}: '{e.value}' [{e.confidence:.0%}]\n"

    return output


if __name__ == "__main__":
    # Test
    test_phrases = [
        "find all python files in my documents",
        "open chrome browser",
        "search for quantum computing",
        "write a python function for fibonacci",
        "start lecture on machine learning",
        "create a new spreadsheet called budget",
        "set temperature to 0.5",
        "what is the weather today",
        "compare python vs javascript",
        "remind me to call john at 5pm",
    ]

    for phrase in test_phrases:
        print(f"\n{'='*60}")
        print(nlu_debug(phrase))