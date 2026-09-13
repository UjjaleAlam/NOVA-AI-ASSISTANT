"""
Lecture Intelligence - Phase 15
Audio capture, transcription, note generation, and summarization.
Fully local using faster-whisper, no cloud dependencies.
"""

import numpy as np
import sounddevice as sd
import queue
import threading
import time
import json
import os
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from enum import Enum
from collections import defaultdict

from faster_whisper import WhisperModel

from brain import ask_nova
from core.context_engine import get_current_session


class LectureState(Enum):
    IDLE = "idle"
    RECORDING = "recording"
    PAUSED = "paused"
    PROCESSING = "processing"
    COMPLETE = "complete"


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str
    speaker: Optional[str] = None
    confidence: float = 1.0


@dataclass
class LectureNote:
    timestamp: float
    timestamp_str: str
    topic: str
    content: str
    type: str = "note"  # note, action_item, key_point, question, definition
    tags: List[str] = field(default_factory=list)


@dataclass
class LectureSession:
    id: str
    title: str
    started_at: float
    ended_at: Optional[float] = None
    state: LectureState = LectureState.IDLE
    segments: List[TranscriptSegment] = field(default_factory=list)
    notes: List[LectureNote] = field(default_factory=list)
    summary: str = ""
    key_topics: List[str] = field(default_factory=list)
    action_items: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)


class AudioCapture:
    """Continuous audio capture with VAD."""

    def __init__(self, sample_rate: int = 16000, chunk_size: int = 4096):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.audio_queue = queue.Queue()
        self.stream = None
        self.recording = False
        self.paused = False
        self._callback = None

    def set_callback(self, callback: Callable[[np.ndarray], None]):
        self._callback = callback

    def start(self):
        if self.recording:
            return
        self.recording = True
        self.paused = False

        def audio_callback(indata, frames, time_info, status):
            if status:
                print(f"Audio status: {status}")
            if not self.paused and self.recording:
                self.audio_queue.put(bytes(indata))
                if self._callback:
                    self._callback(indata.copy())

        self.stream = sd.RawInputStream(
            samplerate=self.sample_rate,
            blocksize=self.chunk_size,
            dtype='int16',
            channels=1,
            callback=audio_callback
        )
        self.stream.start()

    def pause(self):
        self.paused = True

    def resume(self):
        self.paused = False

    def stop(self) -> bytes:
        self.recording = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

        # Collect all audio data
        audio_data = bytearray()
        while not self.audio_queue.empty():
            try:
                audio_data.extend(self.audio_queue.get_nowait())
            except queue.Empty:
                break
        return bytes(audio_data)

    def get_audio_chunk(self, timeout: float = 0.1) -> Optional[bytes]:
        try:
            return self.audio_queue.get(timeout=timeout)
        except queue.Empty:
            return None


class TranscriptionEngine:
    """Real-time transcription with faster-whisper."""

    def __init__(self, model_size: str = "base.en", device: str = "auto"):
        self.model_size = model_size
        self.device = device if device != "auto" else ("cuda" if self._has_cuda() else "cpu")
        self.compute_type = "float16" if self.device == "cuda" else "int8"
        self.model = None
        self._load_model()

    def _has_cuda(self) -> bool:
        try:
            import torch
            return torch.cuda.is_available()
        except Exception:
            return False

    def _load_model(self):
        print(f"Loading Whisper model: {self.model_size} on {self.device}...")
        self.model = WhisperModel(
            self.model_size,
            device=self.device,
            compute_type=self.compute_type
        )
        print("Model loaded.")

    def transcribe_chunk(self, audio_data: bytes) -> List[TranscriptSegment]:
        """Transcribe a chunk of audio."""
        if not audio_data or len(audio_data) < 3200:  # ~0.1s at 16kHz
            return []

        audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0

        try:
            segments, info = self.model.transcribe(
                audio_np,
                language="en",
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500),
                word_timestamps=True
            )

            results = []
            for seg in segments:
                results.append(TranscriptSegment(
                    start=seg.start,
                    end=seg.end,
                    text=seg.text.strip(),
                    confidence=seg.avg_logprob if hasattr(seg, 'avg_logprob') else 1.0
                ))
            return results
        except Exception as e:
            print(f"Transcription error: {e}")
            return []

    def transcribe_full(self, audio_data: bytes) -> List[TranscriptSegment]:
        """Transcribe complete audio with better accuracy."""
        if not audio_data:
            return []

        audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0

        try:
            segments, info = self.model.transcribe(
                audio_np,
                language="en",
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=300),
                word_timestamps=True,
                beam_size=5
            )

            results = []
            for seg in segments:
                results.append(TranscriptSegment(
                    start=seg.start,
                    end=seg.end,
                    text=seg.text.strip(),
                    confidence=seg.avg_logprob if hasattr(seg, 'avg_logprob') else 1.0
                ))
            return results
        except Exception as e:
            print(f"Full transcription error: {e}")
            return []


class NoteGenerator:
    """Generate structured notes from transcripts."""

    def __init__(self):
        self.topic_keywords = {
            "definition": ["define", "definition", "means", "is a", "is an", "refers to"],
            "action_item": ["todo", "action item", "follow up", "remember to", "need to", "should", "must", "will do"],
            "key_point": ["important", "key point", "main point", "crucial", "essential", "remember"],
            "question": ["?", "question", "wonder", "curious", "how does", "why does", "what is"],
            "example": ["example", "for instance", "such as", "like", "e.g.", "i.e."],
            "reference": ["reference", "citation", "source", "paper", "study", "research shows"],
        }

    def classify_segment(self, text: str) -> str:
        """Classify a transcript segment into note type."""
        text_lower = text.lower()
        scores = {}
        for note_type, keywords in self.topic_keywords.items():
            scores[note_type] = sum(1 for kw in keywords if kw in text_lower)

        if scores:
            best = max(scores, key=scores.get)
            if scores[best] > 0:
                return best
        return "note"

    def extract_topics(self, text: str) -> List[str]:
        """Extract key topics from text using LLM."""
        prompt = f"""Extract 5-10 key topics/themes from this lecture transcript.
Return only a JSON array of strings.

Transcript:
{text[:3000]}"""

        try:
            response = ask_nova(prompt)
            # Parse JSON from response
            import re
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception:
            pass
        return []

    def generate_summary(self, text: str, length: str = "medium") -> str:
        """Generate a summary of the lecture."""
        length_map = {
            "short": "2-3 sentences",
            "medium": "1-2 paragraphs",
            "long": "3-5 paragraphs with key details"
        }
        prompt = f"""Summarize this lecture transcript in {length_map.get(length, 'medium')}.
Focus on main concepts, key points, and conclusions.

Transcript:
{text[:4000]}"""

        return ask_nova(prompt)

    def extract_action_items(self, text: str) -> List[str]:
        """Extract action items from text."""
        prompt = f"""Extract all action items, todos, and follow-ups from this lecture transcript.
Return as JSON array of strings. Include who should do what and when if mentioned.

Transcript:
{text[:4000]}"""

        try:
            response = ask_nova(prompt)
            import re
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception:
            pass
        return []

    def create_notes_from_segments(self, segments: List[TranscriptSegment],
                                   session_start: float) -> List[LectureNote]:
        """Create structured notes from transcript segments."""
        notes = []

        for seg in segments:
            if not seg.text:
                continue

            note_type = self.classify_segment(seg.text)
            timestamp = session_start + seg.start
            timestamp_str = self._format_timestamp(seg.start)

            # Extract tags from content
            tags = self._extract_tags(seg.text)

            note = LectureNote(
                timestamp=timestamp,
                timestamp_str=timestamp_str,
                topic=self._extract_topic(seg.text),
                content=seg.text,
                type=note_type,
                tags=tags
            )
            notes.append(note)

        return notes

    def _format_timestamp(self, seconds: float) -> str:
        """Format seconds as HH:MM:SS."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def _extract_topic(self, text: str) -> str:
        """Extract a short topic from text."""
        # First sentence or first 50 chars
        sentences = text.split('.')
        if sentences:
            return sentences[0][:80]
        return text[:80]

    def _extract_tags(self, text: str) -> List[str]:
        """Extract relevant tags from text."""
        tags = []
        text_lower = text.lower()

        tag_keywords = {
            "definition": ["define", "definition", "means"],
            "formula": ["formula", "equation", "calculate"],
            "process": ["process", "steps", "procedure", "workflow"],
            "comparison": ["compare", "versus", "vs", "difference"],
            "example": ["example", "instance", "e.g."],
            "warning": ["warning", "caution", "avoid", "don't"],
            "tip": ["tip", "trick", "hint", "pro tip"],
        }

        for tag, keywords in tag_keywords.items():
            if any(kw in text_lower for kw in keywords):
                tags.append(tag)

        return tags


class LectureManager:
    """Main lecture intelligence coordinator."""

    def __init__(self, model_size: str = "base.en"):
        self.audio_capture = AudioCapture()
        self.transcriber = TranscriptionEngine(model_size)
        self.note_generator = NoteGenerator()
        self.current_session: Optional[LectureSession] = None
        self.real_time_notes = []
        self._processing_thread = None
        self._stop_processing = False

    def start_lecture(self, title: str = "", metadata: Dict = None) -> LectureSession:
        """Start a new lecture recording session."""
        session_id = f"lecture_{int(time.time())}"
        self.current_session = LectureSession(
            id=session_id,
            title=title or f"Lecture {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            started_at=time.time(),
            state=LectureState.RECORDING,
            metadata=metadata or {}
        )
        self.real_time_notes = []

        # Start audio capture
        self.audio_capture.start()

        # Start real-time processing thread
        self._stop_processing = False
        self._processing_thread = threading.Thread(target=self._real_time_processing, daemon=True)
        self._processing_thread.start()

        return self.current_session

    def _real_time_processing(self):
        """Background thread for real-time transcription and note generation."""
        accumulated_audio = bytearray()
        last_process_time = time.time()
        process_interval = 10.0  # Process every 10 seconds

        while not self._stop_processing and self.current_session:
            try:
                chunk = self.audio_capture.get_audio_chunk(timeout=0.5)
                if chunk:
                    accumulated_audio.extend(chunk)

                # Process periodically
                if time.time() - last_process_time >= process_interval:
                    if len(accumulated_audio) > 16000:  # At least 1 second
                        self._process_accumulated_audio()
                        last_process_time = time.time()
            except Exception as e:
                print(f"Real-time processing error: {e}")

    def _process_accumulated_audio(self):
        """Process accumulated audio for real-time notes."""
        if not self.current_session:
            return

        # Get audio from queue
        audio_data = bytearray()
        while not self.audio_capture.audio_queue.empty():
            try:
                audio_data.extend(self.audio_capture.audio_queue.get_nowait())
            except queue.Empty:
                break

        if len(audio_data) < 32000:  # Less than 2 seconds
            return

        # Transcribe
        segments = self.transcriber.transcribe_chunk(bytes(audio_data))
        if not segments:
            return

        # Add to session
        for seg in segments:
            self.current_session.segments.append(seg)

        # Generate real-time notes
        new_notes = self.note_generator.create_notes_from_segments(
            segments, self.current_session.started_at
        )
        self.current_session.notes.extend(new_notes)
        self.real_time_notes.extend(new_notes)

        # Clear processed audio (keep last 5 seconds for continuity)
        if len(accumulated_audio) > 80000:
            accumulated_audio[:] = accumulated_audio[-80000:]

    def pause_lecture(self):
        """Pause the lecture recording."""
        if self.current_session:
            self.current_session.state = LectureState.PAUSED
        self.audio_capture.pause()

    def resume_lecture(self):
        """Resume the lecture recording."""
        if self.current_session:
            self.current_session.state = LectureState.RECORDING
        self.audio_capture.resume()

    def end_lecture(self) -> LectureSession:
        """End the lecture and generate final output."""
        if not self.current_session:
            return None

        self._stop_processing = True
        if self._processing_thread:
            self._processing_thread.join(timeout=5)

        # Get remaining audio
        final_audio = self.audio_capture.stop()

        # Final transcription
        if final_audio:
            final_segments = self.transcriber.transcribe_full(final_audio)
            self.current_session.segments.extend(final_segments)

            # Generate final notes
            final_notes = self.note_generator.create_notes_from_segments(
                final_segments, self.current_session.started_at
            )
            self.current_session.notes.extend(final_notes)

        # Generate summary and insights
        self._generate_final_output()

        self.current_session.ended_at = time.time()
        self.current_session.state = LectureState.COMPLETE

        # Save to database
        self._save_session(self.current_session)

        session = self.current_session
        self.current_session = None
        return session

    def _generate_final_output(self):
        """Generate summary, topics, and action items."""
        if not self.current_session:
            return

        # Combine all transcript text
        full_text = " ".join(seg.text for seg in self.current_session.segments if seg.text)

        if not full_text:
            return

        # Generate summary
        self.current_session.summary = self.note_generator.generate_summary(full_text, "medium")

        # Extract key topics
        self.current_session.key_topics = self.note_generator.extract_topics(full_text)

        # Extract action items
        self.current_session.action_items = self.note_generator.extract_action_items(full_text)

    def _save_session(self, session: LectureSession):
        """Save lecture session to database."""
        from core.context_engine import get_connection

        conn = get_connection()
        cursor = conn.cursor()

        # Create table if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS lecture_sessions (
                id TEXT PRIMARY KEY,
                title TEXT,
                started_at REAL,
                ended_at REAL,
                state TEXT,
                segments TEXT,  -- JSON
                notes TEXT,  -- JSON
                summary TEXT,
                key_topics TEXT,  -- JSON
                action_items TEXT,  -- JSON
                metadata TEXT  -- JSON
            )
        """)

        cursor.execute("""
            INSERT OR REPLACE INTO lecture_sessions
            (id, title, started_at, ended_at, state, segments, notes, summary, key_topics, action_items, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session.id,
            session.title,
            session.started_at,
            session.ended_at,
            session.state.value,
            json.dumps([asdict(s) for s in session.segments]),
            json.dumps([asdict(n) for n in session.notes]),
            session.summary,
            json.dumps(session.key_topics),
            json.dumps(session.action_items),
            json.dumps(session.metadata)
        ))
        conn.commit()
        conn.close()

    def get_session(self, session_id: str) -> Optional[LectureSession]:
        from core.context_engine import get_connection

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM lecture_sessions WHERE id = ?", (session_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return LectureSession(
            id=row[0],
            title=row[1],
            started_at=row[2],
            ended_at=row[3],
            state=LectureState(row[4]),
            segments=[TranscriptSegment(**s) for s in json.loads(row[5])],
            notes=[LectureNote(**n) for n in json.loads(row[6])],
            summary=row[7],
            key_topics=json.loads(row[8]),
            action_items=json.loads(row[9]),
            metadata=json.loads(row[10])
        )

    def list_sessions(self, limit: int = 20) -> List[Dict]:
        from core.context_engine import get_connection

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, title, started_at, ended_at, state
            FROM lecture_sessions
            ORDER BY started_at DESC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        conn.close()

        return [
            {"id": r[0], "title": r[1], "started_at": r[2], "ended_at": r[3], "state": r[4]}
            for r in rows
        ]

    def export_session(self, session_id: str, format: str = "markdown",
                       output_path: str = None) -> Optional[str]:
        """Export lecture session to various formats."""
        session = self.get_session(session_id)
        if not session:
            return None

        output_path = output_path or f"lecture_{session_id}.{format}"

        if format == "markdown":
            content = self._export_markdown(session)
        elif format == "json":
            content = json.dumps(asdict(session), indent=2, default=str)
        elif format == "txt":
            content = self._export_text(session)
        else:
            return None

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)

        return output_path

    def _export_markdown(self, session: LectureSession) -> str:
        lines = [
            f"# {session.title}",
            f"",
            f"**Date:** {datetime.fromtimestamp(session.started_at).strftime('%Y-%m-%d %H:%M')}",
            f"**Duration:** {self._format_duration(session.ended_at - session.started_at) if session.ended_at else 'In progress'}",
            f"**ID:** {session.id}",
            f"",
            f"## Summary",
            f"{session.summary or 'No summary generated'}",
            f"",
        ]

        if session.key_topics:
            lines.append("## Key Topics")
            for topic in session.key_topics:
                lines.append(f"- {topic}")
            lines.append("")

        if session.action_items:
            lines.append("## Action Items")
            for item in session.action_items:
                lines.append(f"- [ ] {item}")
            lines.append("")

        if session.notes:
            lines.append("## Notes")
            for note in session.notes:
                tag_str = f" [{', '.join(note.tags)}]" if note.tags else ""
                lines.append(f"### {note.timestamp_str} - {note.topic}{tag_str}")
                lines.append(f"*Type: {note.type}*")
                lines.append(f"{note.content}")
                lines.append("")

        return "\n".join(lines)

    def _export_text(self, session: LectureSession) -> str:
        lines = [
            f"{session.title}",
            f"Date: {datetime.fromtimestamp(session.started_at).strftime('%Y-%m-%d %H:%M')}",
            f"Duration: {self._format_duration(session.ended_at - session.started_at) if session.ended_at else 'In progress'}",
            f"",
            f"SUMMARY:",
            f"{session.summary}",
            f"",
        ]

        if session.key_topics:
            lines.append("KEY TOPICS:")
            for topic in session.key_topics:
                lines.append(f"  - {topic}")
            lines.append("")

        if session.action_items:
            lines.append("ACTION ITEMS:")
            for item in session.action_items:
                lines.append(f"  - {item}")
            lines.append("")

        if session.notes:
            lines.append("NOTES:")
            for note in session.notes:
                lines.append(f"  [{note.timestamp_str}] {note.topic} ({note.type}): {note.content}")

        return "\n".join(lines)

    def _format_duration(self, seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        if hours > 0:
            return f"{hours}h {minutes}m {secs}s"
        return f"{minutes}m {secs}s"


# Global instance
lecture_manager = LectureManager()


# Convenience functions
def start_lecture(title: str = "", metadata: Dict = None) -> LectureSession:
    return lecture_manager.start_lecture(title, metadata)

def pause_lecture():
    lecture_manager.pause_lecture()

def resume_lecture():
    lecture_manager.resume_lecture()

def end_lecture() -> LectureSession:
    return lecture_manager.end_lecture()

def get_lecture(session_id: str) -> Optional[LectureSession]:
    return lecture_manager.get_session(session_id)

def list_lectures(limit: int = 20) -> List[Dict]:
    return lecture_manager.list_sessions(limit)

def export_lecture(session_id: str, format: str = "markdown", path: str = None) -> Optional[str]:
    return lecture_manager.export_session(session_id, format, path)


if __name__ == "__main__":
    # Test
    print("Lecture Intelligence module loaded.")
    print("Available functions:")
    print("  start_lecture(title, metadata)")
    print("  pause_lecture()")
    print("  resume_lecture()")
    print("  end_lecture()")
    print("  get_lecture(session_id)")
    print("  list_lectures(limit)")
    print("  export_lecture(session_id, format, path)")