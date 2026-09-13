"""
Second Brain - Phase 20
Knowledge graph, bidirectional links, concept mapping, spaced repetition.
Fully local, no cloud dependencies.
"""

import os
import json
import time
import uuid
import re
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, asdict, field
from pathlib import Path
from collections import defaultdict, Counter
from datetime import datetime

from core.context_engine import get_connection
from core.semantic_memory import search_memory, add_memory


DB_DIR = "database"
SECOND_BRAIN_DB = os.path.join(DB_DIR, "second_brain.db")

os.makedirs(DB_DIR, exist_ok=True)


def init_second_brain_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Nodes (concepts, notes, ideas)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS nodes (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL,  -- 'concept', 'note', 'idea', 'person', 'project', 'resource'
            title TEXT NOT NULL,
            content TEXT,
            source TEXT,  -- 'manual', 'extracted', 'linked', 'imported'
            tags TEXT,  -- JSON array
            aliases TEXT,  -- JSON array
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            access_count INTEGER DEFAULT 0,
            last_accessed REAL
        )
    """)

    # Edges (relationships between nodes)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS edges (
            id TEXT PRIMARY KEY,
            source_id TEXT NOT NULL,
            target_id TEXT NOT NULL,
            relation_type TEXT NOT NULL,  -- 'links_to', 'references', 'part_of', 'contains', 'related_to', 'depends_on', 'inspired_by', 'contradicts'
            weight REAL DEFAULT 1.0,
            metadata TEXT,  -- JSON
            created_at REAL NOT NULL,
            FOREIGN KEY (source_id) REFERENCES nodes(id),
            FOREIGN KEY (target_id) REFERENCES nodes(id)
        )
    """)

    # Spaced repetition schedule
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS review_schedule (
            id TEXT PRIMARY KEY,
            node_id TEXT NOT NULL,
            interval INTEGER NOT NULL,  -- days
            ease_factor REAL DEFAULT 2.5,
            due_date REAL NOT NULL,
            last_reviewed REAL,
            review_count INTEGER DEFAULT 0,
            lapses INTEGER DEFAULT 0,
            state TEXT DEFAULT 'new',  -- 'new', 'learning', 'review', 'suspended'
            FOREIGN KEY (node_id) REFERENCES nodes(id)
        )
    """)

    # Review history
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS review_history (
            id TEXT PRIMARY KEY,
            node_id TEXT NOT NULL,
            rating INTEGER NOT NULL,  -- 0=again, 1=hard, 2=good, 3=easy
            interval_before INTEGER,
            interval_after INTEGER,
            ease_before REAL,
            ease_after REAL,
            reviewed_at REAL NOT NULL,
            time_taken INTEGER,  -- seconds
            FOREIGN KEY (node_id) REFERENCES nodes(id)
        )
    """)

    # Graph views (saved perspectives)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS graph_views (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            filter_query TEXT,  -- JSON filter
            layout TEXT DEFAULT 'force',  -- 'force', 'hierarchical', 'circular'
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
    """)

    # Daily notes
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_notes (
            id TEXT PRIMARY KEY,
            date TEXT NOT NULL UNIQUE,  -- YYYY-MM-DD
            content TEXT,
            linked_nodes TEXT,  -- JSON array of node_ids
            tags TEXT,  -- JSON array
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
    """)

    # Indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_nodes_title ON nodes(title)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_edges_type ON edges(relation_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_review_due ON review_schedule(due_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_daily_date ON daily_notes(date)")

    conn.commit()
    conn.close()


init_second_brain_db()


@dataclass
class Node:
    id: str
    type: str
    title: str
    content: str = ""
    source: str = "manual"
    tags: List[str] = field(default_factory=list)
    aliases: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    access_count: int = 0
    last_accessed: Optional[float] = None


@dataclass
class Edge:
    id: str
    source_id: str
    target_id: str
    relation_type: str
    weight: float = 1.0
    metadata: Dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


class KnowledgeGraph:
    """Knowledge graph with bidirectional links and concept mapping."""

    def __init__(self):
        self.node_cache = {}
        self.cache_time = 0
        self.cache_ttl = 60

    # ==========================================
    # NODE OPERATIONS
    # ==========================================

    def create_node(self, node: Node) -> Node:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO nodes (id, type, title, content, source, tags, aliases, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            node.id, node.type, node.title, node.content, node.source,
            json.dumps(node.tags), json.dumps(node.aliases),
            node.created_at, node.updated_at
        ))
        conn.commit()
        conn.close()

        # Also add to semantic memory for search
        if node.content:
            add_memory(f"node_{node.id}", f"{node.title}: {node.content}")

        self._invalidate_cache()
        return node

    def get_node(self, node_id: str) -> Optional[Node]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM nodes WHERE id = ?", (node_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return Node(
                id=row[0], type=row[1], title=row[2], content=row[3],
                source=row[4], tags=json.loads(row[5]) if row[5] else [],
                aliases=json.loads(row[6]) if row[6] else [],
                created_at=row[7], updated_at=row[8],
                access_count=row[9], last_accessed=row[10]
            )
        return None

    def update_node(self, node_id: str, **kwargs) -> bool:
        allowed = {"type", "title", "content", "source", "tags", "aliases"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return False

        updates["updated_at"] = time.time()
        if "tags" in updates:
            updates["tags"] = json.dumps(updates["tags"])
        if "aliases" in updates:
            updates["aliases"] = json.dumps(updates["aliases"])

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [node_id]

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(f"UPDATE nodes SET {set_clause} WHERE id = ?", values)
        conn.commit()
        affected = cursor.rowcount
        conn.close()

        if affected:
            self._invalidate_cache()
            # Update semantic memory
            node = self.get_node(node_id)
            if node and node.content:
                add_memory(f"node_{node_id}", f"{node.title}: {node.content}")
        return affected > 0

    def delete_node(self, node_id: str) -> bool:
        conn = get_connection()
        cursor = conn.cursor()
        # Delete edges first
        cursor.execute("DELETE FROM edges WHERE source_id = ? OR target_id = ?", (node_id, node_id))
        cursor.execute("DELETE FROM nodes WHERE id = ?", (node_id,))
        conn.commit()
        affected = cursor.rowcount
        conn.close()

        if affected:
            self._invalidate_cache()
        return affected > 0

    def search_nodes(self, query: str, node_type: str = None, tags: List[str] = None, limit: int = 20) -> List[Node]:
        conn = get_connection()
        cursor = conn.cursor()

        sql = "SELECT * FROM nodes WHERE 1=1"
        params = []

        if query:
            sql += " AND (title LIKE ? OR content LIKE ?)"
            params.extend([f"%{query}%", f"%{query}%"])

        if node_type:
            sql += " AND type = ?"
            params.append(node_type)

        if tags:
            for tag in tags:
                sql += " AND tags LIKE ?"
                params.append(f"%{tag}%")

        sql += " ORDER BY access_count DESC, updated_at DESC LIMIT ?"
        params.append(limit)

        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()

        return [
            Node(id=r[0], type=r[1], title=r[2], content=r[3], source=r[4],
                 tags=json.loads(r[5]) if r[5] else [], aliases=json.loads(r[6]) if r[6] else [],
                 created_at=r[7], updated_at=r[8], access_count=r[9], last_accessed=r[10])
            for r in rows
        ]

    def get_all_nodes(self, node_type: str = None, limit: int = 100) -> List[Node]:
        conn = get_connection()
        cursor = conn.cursor()
        if node_type:
            cursor.execute("SELECT * FROM nodes WHERE type = ? ORDER BY updated_at DESC LIMIT ?", (node_type, limit))
        else:
            cursor.execute("SELECT * FROM nodes ORDER BY updated_at DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [
            Node(id=r[0], type=r[1], title=r[2], content=r[3], source=r[4],
                 tags=json.loads(r[5]) if r[5] else [], aliases=json.loads(r[6]) if r[6] else [],
                 created_at=r[7], updated_at=r[8], access_count=r[9], last_accessed=r[10])
            for r in rows
        ]

    # ==========================================
    # EDGE OPERATIONS
    # ==========================================

    def create_edge(self, edge: Edge) -> Edge:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO edges (id, source_id, target_id, relation_type, weight, metadata, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            edge.id, edge.source_id, edge.target_id, edge.relation_type,
            edge.weight, json.dumps(edge.metadata), edge.created_at
        ))
        conn.commit()
        conn.close()
        return edge

    def get_edges(self, node_id: str, direction: str = "both", relation_type: str = None) -> List[Edge]:
        conn = get_connection()
        cursor = conn.cursor()

        if direction == "outgoing":
            sql = "SELECT * FROM edges WHERE source_id = ?"
        elif direction == "incoming":
            sql = "SELECT * FROM edges WHERE target_id = ?"
        else:
            sql = "SELECT * FROM edges WHERE source_id = ? OR target_id = ?"

        params = [node_id] if direction != "both" else [node_id, node_id]

        if relation_type:
            sql += " AND relation_type = ?"
            params.append(relation_type)

        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()

        return [
            Edge(id=r[0], source_id=r[1], target_id=r[2], relation_type=r[3],
                 weight=r[4], metadata=json.loads(r[5]) if r[5] else {}, created_at=r[6])
            for r in rows
        ]

    def get_neighbors(self, node_id: str, depth: int = 1, relation_type: str = None) -> Set[str]:
        """Get all nodes within depth hops."""
        visited = set()
        current_level = {node_id}

        for _ in range(depth):
            next_level = set()
            for nid in current_level:
                edges = self.get_edges(nid, "both", relation_type)
                for edge in edges:
                    neighbor = edge.target_id if edge.source_id == nid else edge.source_id
                    if neighbor not in visited:
                        next_level.add(neighbor)
            visited.update(current_level)
            current_level = next_level
            if not current_level:
                break

        visited.discard(node_id)
        return visited

    def get_shortest_path(self, source_id: str, target_id: str, max_depth: int = 5) -> List[str]:
        """Find shortest path between two nodes using BFS."""
        if source_id == target_id:
            return [source_id]

        queue = [(source_id, [source_id])]
        visited = {source_id}

        while queue:
            current, path = queue.pop(0)
            if len(path) > max_depth:
                continue

            edges = self.get_edges(current, "outgoing")
            for edge in edges:
                neighbor = edge.target_id
                if neighbor == target_id:
                    return path + [neighbor]
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))

        return []

    # ==========================================
    # GRAPH ANALYSIS
    # ==========================================

    def get_graph_stats(self) -> Dict:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM nodes")
        node_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM edges")
        edge_count = cursor.fetchone()[0]
        cursor.execute("SELECT type, COUNT(*) FROM nodes GROUP BY type")
        type_dist = dict(cursor.fetchall())
        cursor.execute("SELECT relation_type, COUNT(*) FROM edges GROUP BY relation_type")
        rel_dist = dict(cursor.fetchall())
        conn.close()

        return {
            "nodes": node_count,
            "edges": edge_count,
            "node_types": type_dist,
            "relation_types": rel_dist,
            "density": edge_count / max(node_count * (node_count - 1), 1) if node_count > 1 else 0
        }

    def find_clusters(self, min_size: int = 3) -> List[List[str]]:
        """Find connected components (clusters) in the graph."""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT source_id, target_id FROM edges")
        edges = cursor.fetchall()
        conn.close()

        # Build adjacency list
        adj = defaultdict(set)
        for src, tgt in edges:
            adj[src].add(tgt)
            adj[tgt].add(src)

        # Find connected components
        visited = set()
        clusters = []

        for node in adj:
            if node not in visited:
                cluster = []
                stack = [node]
                while stack:
                    n = stack.pop()
                    if n not in visited:
                        visited.add(n)
                        cluster.append(n)
                        stack.extend(adj[n] - visited)
                if len(cluster) >= min_size:
                    clusters.append(cluster)

        return clusters

    def get_centrality(self, node_id: str) -> Dict:
        """Calculate centrality measures for a node."""
        edges_out = self.get_edges(node_id, "outgoing")
        edges_in = self.get_edges(node_id, "incoming")

        # Degree centrality
        out_degree = len(edges_out)
        in_degree = len(edges_in)
        total_degree = out_degree + in_degree

        # Betweenness approximation (simplified)
        # PageRank would be better but requires full graph computation

        return {
            "out_degree": out_degree,
            "in_degree": in_degree,
            "total_degree": total_degree,
            "outgoing_relations": Counter(e.relation_type for e in edges_out),
            "incoming_relations": Counter(e.relation_type for e in edges_in)
        }

    def _invalidate_cache(self):
        self.node_cache = {}
        self.cache_time = 0

    # ==========================================
    # BACKLINKS & BIDIRECTIONAL NAVIGATION
    # ==========================================

    def get_backlinks(self, node_id: str) -> List[Node]:
        """Get all nodes that link to this node."""
        edges = self.get_edges(node_id, "incoming")
        backlinks = []
        for edge in edges:
            node = self.get_node(edge.source_id)
            if node:
                backlinks.append(node)
        return backlinks

    def get_forward_links(self, node_id: str) -> List[Node]:
        """Get all nodes this node links to."""
        edges = self.get_edges(node_id, "outgoing")
        forward = []
        for edge in edges:
            node = self.get_node(edge.target_id)
            if node:
                forward.append(node)
        return forward

    def get_unlinked_mentions(self, node_id: str) -> List[Node]:
        """Find nodes that mention this node's title/aliases but don't link to it."""
        node = self.get_node(node_id)
        if not node:
            return []

        search_terms = [node.title] + node.aliases
        all_nodes = self.get_all_nodes(limit=1000)

        unlinked = []
        for n in all_nodes:
            if n.id == node_id:
                continue
            # Check if any search term appears in content
            content = (n.title + " " + n.content).lower()
            for term in search_terms:
                if term.lower() in content:
                    # Check if not already linked
                    edges = self.get_edges(node_id, "both")
                    linked_ids = {e.target_id for e in edges if e.source_id == node_id}
                    linked_ids.update({e.source_id for e in edges if e.target_id == node_id})
                    if n.id not in linked_ids:
                        unlinked.append(n)
                        break
        return unlinked


class SpacedRepetition:
    """SM-2 spaced repetition algorithm implementation."""

    def __init__(self):
        pass

    def create_schedule(self, node_id: str) -> str:
        schedule_id = str(uuid.uuid4())[:8]
        due_date = time.time()  # Due now for new cards

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO review_schedule (id, node_id, interval, ease_factor, due_date, state)
            VALUES (?, ?, 0, 2.5, ?, 'new')
        """, (schedule_id, node_id, time.time()))
        conn.commit()
        conn.close()
        return schedule_id

    def get_due_cards(self, limit: int = 20) -> List[Dict]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT rs.id, rs.node_id, rs.interval, rs.ease_factor, rs.due_date,
                   rs.review_count, rs.lapses, rs.state,
                   n.title, n.content, n.type
            FROM review_schedule rs
            JOIN nodes n ON rs.node_id = n.id
            WHERE rs.due_date <= ? AND rs.state != 'suspended'
            ORDER BY rs.due_date
            LIMIT ?
        """, (time.time(), limit))
        rows = cursor.fetchall()
        conn.close()

        return [
            {"schedule_id": r[0], "node_id": r[1], "interval": r[2], "ease_factor": r[3],
             "due_date": r[4], "review_count": r[5], "lapses": r[6], "state": r[7],
             "title": r[8], "content": r[9], "type": r[10]}
            for r in rows
        ]

    def review_card(self, schedule_id: str, rating: int, time_taken: int = 0) -> Dict:
        """Rate: 0=Again, 1=Hard, 2=Good, 3=Easy"""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM review_schedule WHERE id = ?", (schedule_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return {"error": "Schedule not found"}

        schedule_id, node_id, interval, ease_factor, due_date, review_count, lapses, state = row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7]

        # SM-2 algorithm
        if rating == 0:  # Again
            interval = 1
            lapses += 1
            ease_factor = max(1.3, ease_factor - 0.2)
        elif rating == 1:  # Hard
            interval = max(interval * 1.2, 1)
            ease_factor = max(1.3, ease_factor - 0.15)
        elif rating == 2:  # Good
            if review_count == 0:
                interval = 1
            elif review_count == 1:
                interval = 6
            else:
                interval = interval * ease_factor
        elif rating == 3:  # Easy
            if review_count == 0:
                interval = 4
            elif review_count == 1:
                interval = 10
            else:
                interval = interval * ease_factor * 1.3
            ease_factor = min(2.5, ease_factor + 0.15)
        else:
            return {"error": "Invalid rating"}

        interval = int(interval)
        due_date = time.time() + interval * 86400
        review_count += 1

        if review_count <= 1:
            state = "learning"
        else:
            state = "review"

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE review_schedule
            SET interval = ?, ease_factor = ?, due_date = ?, review_count = ?,
                lapses = ?, state = ?, last_reviewed = ?
            WHERE id = ?
        """, (interval, ease_factor, due_date, review_count, lapses, state, time.time(), schedule_id))

        # Record history
        history_id = str(uuid.uuid4())[:8]
        cursor.execute("""
            INSERT INTO review_history (id, node_id, rating, interval_before, interval_after,
                                       ease_before, ease_after, reviewed_at, time_taken)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (history_id, node_id, rating, row[2], interval, row[3], ease_factor, time.time(), time_taken))

        conn.commit()
        conn.close()

        return {
            "schedule_id": schedule_id,
            "node_id": node_id,
            "new_interval": interval,
            "new_ease_factor": ease_factor,
            "new_due_date": due_date,
            "new_state": state,
            "review_count": review_count
        }

    def get_review_stats(self, node_id: str = None) -> Dict:
        conn = get_connection()
        cursor = conn.cursor()

        if node_id:
            cursor.execute("SELECT * FROM review_history WHERE node_id = ? ORDER BY reviewed_at DESC", (node_id,))
        else:
            cursor.execute("SELECT * FROM review_history ORDER BY reviewed_at DESC LIMIT 100")

        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return {"total_reviews": 0}

        ratings = [r[2] for r in rows]
        total = len(ratings)
        again = ratings.count(0)
        hard = ratings.count(1)
        good = ratings.count(2)
        easy = ratings.count(3)

        return {
            "total_reviews": total,
            "again": again,
            "hard": hard,
            "good": good,
            "easy": easy,
            "success_rate": (good + easy) / total if total > 0 else 0,
            "avg_ease": sum(r[6] for r in rows) / total if total > 0 else 2.5
        }


class DailyNotes:
    """Daily notes with automatic linking."""

    def __init__(self):
        pass

    def create_note(self, date: str = None, content: str = "", tags: List[str] = None) -> str:
        date = date or datetime.now().strftime("%Y-%m-%d")
        note_id = str(uuid.uuid4())[:8]

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO daily_notes (id, date, content, tags, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (note_id, date, content, json.dumps(tags or []), time.time(), time.time()))
        conn.commit()
        conn.close()
        return note_id

    def get_note(self, date: str) -> Optional[Dict]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM daily_notes WHERE date = ?", (date,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {"id": row[0], "date": row[1], "content": row[2],
                    "tags": json.loads(row[3]) if row[3] else [],
                    "created_at": row[4], "updated_at": row[5]}
        return None

    def update_note(self, date: str, content: str = None, tags: List[str] = None) -> bool:
        conn = get_connection()
        cursor = conn.cursor()
        updates = {}
        if content is not None:
            updates["content"] = content
        if tags is not None:
            updates["tags"] = json.dumps(tags)
        updates["updated_at"] = time.time()

        if not updates:
            return False

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [date]

        cursor.execute(f"UPDATE daily_notes SET {set_clause} WHERE date = ?", values)
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        return affected > 0

    def get_recent_notes(self, limit: int = 10) -> List[Dict]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM daily_notes ORDER BY date DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "date": r[1], "content": r[2],
             "tags": json.loads(r[3]) if r[3] else [],
             "created_at": r[4], "updated_at": r[5]}
            for r in rows
        ]

    def link_nodes(self, date: str, node_ids: List[str]):
        note = self.get_note(date)
        if note:
            existing = set(note.get("linked_nodes", []))
            existing.update(node_ids)
            self.update_note(date, tags=json.dumps(list(existing)))


class GraphViews:
    """Saved graph perspectives."""

    def __init__(self):
        pass

    def create_view(self, name: str, description: str = "", filter_query: Dict = None, layout: str = "force") -> str:
        view_id = str(uuid.uuid4())[:8]
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO graph_views (id, name, description, filter_query, layout, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (view_id, name, description, json.dumps(filter_query or {}), layout, time.time(), time.time()))
        conn.commit()
        conn.close()
        return view_id

    def get_view(self, view_id: str) -> Optional[Dict]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM graph_views WHERE id = ?", (view_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {"id": row[0], "name": row[1], "description": row[2],
                    "filter_query": json.loads(row[3]) if row[3] else {},
                    "layout": row[4], "created_at": row[5], "updated_at": row[6]}
        return None

    def list_views(self) -> List[Dict]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM graph_views ORDER BY updated_at DESC")
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "name": r[1], "description": r[2],
             "filter_query": json.loads(r[3]) if r[3] else {},
             "layout": r[4], "created_at": r[5], "updated_at": r[6]}
            for r in rows
        ]


# Global instances
knowledge_graph = KnowledgeGraph()
spaced_repetition = SpacedRepetition()
daily_notes = DailyNotes()
graph_views = GraphViews()


# Convenience functions
def create_node(type: str, title: str, content: str = "", tags: List[str] = None, aliases: List[str] = None) -> Node:
    node = Node(
        id=str(uuid.uuid4())[:8],
        type=type,
        title=title,
        content=content,
        tags=tags or [],
        aliases=aliases or []
    )
    return knowledge_graph.create_node(node)

def get_node(node_id: str) -> Optional[Node]:
    return knowledge_graph.get_node(node_id)

def search_nodes(query: str, node_type: str = None, tags: List[str] = None, limit: int = 20) -> List[Node]:
    return knowledge_graph.search_nodes(query, node_type, tags, limit)

def link_nodes(source_id: str, target_id: str, relation_type: str, weight: float = 1.0) -> Edge:
    edge = Edge(
        id=str(uuid.uuid4())[:8],
        source_id=source_id,
        target_id=target_id,
        relation_type=relation_type,
        weight=weight
    )
    return knowledge_graph.create_edge(edge)

def get_backlinks(node_id: str) -> List[Node]:
    return knowledge_graph.get_backlinks(node_id)

def get_forward_links(node_id: str) -> List[Node]:
    return knowledge_graph.get_forward_links(node_id)

def get_graph_stats() -> Dict:
    return knowledge_graph.get_graph_stats()

def find_clusters(min_size: int = 3) -> List[List[str]]:
    return knowledge_graph.find_clusters(min_size)

def get_due_cards(limit: int = 20) -> List[Dict]:
    return spaced_repetition.get_due_cards(limit)

def review_card(schedule_id: str, rating: int, time_taken: int = 0) -> Dict:
    return spaced_repetition.review_card(schedule_id, rating, time_taken)

def get_review_stats(node_id: str = None) -> Dict:
    return spaced_repetition.get_review_stats(node_id)

def create_daily_note(date: str = None, content: str = "", tags: List[str] = None) -> str:
    return daily_notes.create_note(date, content, tags)

def get_daily_note(date: str) -> Optional[Dict]:
    return daily_notes.get_note(date)

def get_recent_daily_notes(limit: int = 10) -> List[Dict]:
    return daily_notes.get_recent_notes(limit)

def create_graph_view(name: str, description: str = "", filter_query: Dict = None, layout: str = "force") -> str:
    return graph_views.create_view(name, description, filter_query, layout)

def list_graph_views() -> List[Dict]:
    return graph_views.list_views()

def get_node_neighbors(node_id: str, depth: int = 1) -> Set[str]:
    return knowledge_graph.get_neighbors(node_id, depth)

def get_shortest_path(source_id: str, target_id: str, max_depth: int = 5) -> List[str]:
    return knowledge_graph.get_shortest_path(source_id, target_id, max_depth)

def get_unlinked_mentions(node_id: str) -> List[Node]:
    return knowledge_graph.get_unlinked_mentions(node_id)

def get_centrality(node_id: str) -> Dict:
    return knowledge_graph.get_centrality(node_id)


# Auto-linking from text
def auto_link_content(content: str, source_node_id: str) -> List[str]:
    """Extract potential links from content and create edges."""
    # Simple pattern: [[title]] or #tag
    linked = []
    for match in re.finditer(r'\[\[([^\]]+)\]\]', content):
        title = match.group(1).strip()
        nodes = search_nodes(title, limit=1)
        if nodes:
            target_id = nodes[0].id
            if target_id != source_node_id:
                link_nodes(source_node_id, target_id, "references")
                linked.append(target_id)
    return linked


# Voice command integration
def second_brain_debug() -> str:
    stats = knowledge_graph.get_graph_stats()
    due = spaced_repetition.get_due_cards(5)
    recent_notes = daily_notes.get_recent_notes(3)

    output = f"Second Brain Stats:\n"
    output += f"  Nodes: {stats['nodes']}, Edges: {stats['edges']}, Density: {stats['density']:.3f}\n"
    output += f"  Due cards: {len(due)}\n"
    output += f"  Recent daily notes: {len(recent_notes)}\n"

    if due:
        output += "\nDue for review:\n"
        for d in due[:3]:
            output += f"  • {d['title']} ({d['state']})\n"

    return output


if __name__ == "__main__":
    # Test
    print("Second Brain module loaded.")
    print("Available functions:")
    print("  create_node(type, title, content, tags, aliases)")
    print("  search_nodes(query, node_type, tags, limit)")
    print("  link_nodes(source_id, target_id, relation_type, weight)")
    print("  get_backlinks(node_id)")
    print("  get_forward_links(node_id)")
    print("  get_graph_stats()")
    print("  find_clusters(min_size)")
    print("  get_due_cards(limit)")
    print("  review_card(schedule_id, rating, time_taken)")
    print("  create_daily_note(date, content, tags)")
    print("  get_daily_note(date)")
    print("  create_graph_view(name, description, filter_query, layout)")
    print("  get_node_neighbors(node_id, depth)")
    print("  get_shortest_path(source_id, target_id, max_depth)")
    print("  get_unlinked_mentions(node_id)")
    print("  get_centrality(node_id)")