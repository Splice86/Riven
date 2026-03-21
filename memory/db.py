"""Memory database with vector embeddings."""

import sqlite3
import numpy as np
from datetime import datetime, timezone
from typing import Optional

from memory.embedding import EmbeddingModel

DEFAULT_DB_PATH = "memory.db"


class MemoryDB:
    """SQLite-based memory storage with vector embeddings."""
    
    def __init__(
        self,
        db_path: str = DEFAULT_DB_PATH,
        embedding_model: EmbeddingModel | None = None
    ):
        self.db_path = db_path
        self.embedding = embedding_model or EmbeddingModel()
        self._init_db()
    
    def _init_db(self):
        """Initialize the database schema."""
        with sqlite3.connect(self.db_path) as conn:
            # Main memories table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user',
                    embedding BLOB,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            
            # Keywords table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS keywords (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            
            # Memory keywords junction
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memory_keywords (
                    memory_id INTEGER NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
                    keyword_id INTEGER NOT NULL REFERENCES keywords(id) ON DELETE CASCADE,
                    PRIMARY KEY (memory_id, keyword_id)
                )
            """)
            
            # Indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_mk_memory ON memory_keywords(memory_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_mk_keyword ON memory_keywords(keyword_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_keyword_name ON keywords(name)")
            conn.commit()
    
    def add(
        self,
        content: str,
        role: str = "user",
        keywords: list[str] | None = None
    ) -> int:
        """Add a memory.
        
        Args:
            content: The content to store
            role: Role (user, assistant, system, tool)
            keywords: Optional keywords for the memory
            
        Returns:
            The ID of the inserted memory
        """
        embedding = self.embedding.get(content)
        now = datetime.now(timezone.utc).isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """INSERT INTO memories (content, role, embedding, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (content, role, embedding.tobytes(), now, now)
            )
            memory_id = cursor.lastrowid
            
            # Add keywords
            if keywords:
                for kw in keywords:
                    normalized = kw.lower().strip()
                    if not normalized:
                        continue
                    
                    conn.execute(
                        "INSERT OR IGNORE INTO keywords (name, created_at) VALUES (?, ?)",
                        (normalized, now)
                    )
                    
                    kw_row = conn.execute(
                        "SELECT id FROM keywords WHERE name = ?", (normalized,)
                    ).fetchone()
                    
                    if kw_row:
                        conn.execute(
                            "INSERT OR IGNORE INTO memory_keywords (memory_id, keyword_id) VALUES (?, ?)",
                            (memory_id, kw_row[0])
                        )
            
            conn.commit()
            return memory_id
    
    def get(self, memory_id: int) -> dict | None:
        """Get a memory by ID.
        
        Args:
            memory_id: The ID of the memory
            
        Returns:
            Dictionary with memory data, or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
            if not row:
                return None
            
            keywords = conn.execute(
                """SELECT k.name FROM keywords k
                   JOIN memory_keywords mk ON mk.keyword_id = k.id
                   WHERE mk.memory_id = ?""",
                (memory_id,)
            ).fetchall()
            
            return {
                "id": row["id"],
                "content": row["content"],
                "role": row["role"],
                "keywords": [k["name"] for k in keywords],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"]
            }
    
    def search_by_keyword(self, keyword: str, limit: int = 10) -> list[dict]:
        """Search memories by keyword.
        
        Args:
            keyword: Keyword to search for
            limit: Maximum number of results
            
        Returns:
            List of matching memories
        """
        normalized = keyword.lower().strip()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT DISTINCT m.* FROM memories m
                   JOIN memory_keywords mk ON mk.memory_id = m.id
                   JOIN keywords k ON k.id = mk.keyword_id
                   WHERE k.name = ?
                   ORDER BY m.created_at DESC
                   LIMIT ?""",
                (normalized, limit)
            ).fetchall()
            
            results = []
            for row in rows:
                keywords = conn.execute(
                    """SELECT k.name FROM keywords k
                       JOIN memory_keywords mk ON mk.keyword_id = k.id
                       WHERE mk.memory_id = ?""",
                    (row["id"],)
                ).fetchall()
                
                results.append({
                    "id": row["id"],
                    "content": row["content"],
                    "role": row["role"],
                    "keywords": [k["name"] for k in keywords],
                    "created_at": row["created_at"]
                })
            
            return results
    
    def search_similar(self, query: str, limit: int = 5) -> list[dict]:
        """Search memories by semantic similarity.
        
        Args:
            query: Text query to search for
            limit: Maximum number of results
            
        Returns:
            List of similar memories with similarity scores
        """
        query_embedding = self.embedding.get(query)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM memories WHERE embedding IS NOT NULL"
            ).fetchall()
            
            results = []
            for row in rows:
                stored = np.frombuffer(row["embedding"], dtype=np.float32)
                similarity = self._cosine_similarity(query_embedding, stored)
                
                keywords = conn.execute(
                    """SELECT k.name FROM keywords k
                       JOIN memory_keywords mk ON mk.keyword_id = k.id
                       WHERE mk.memory_id = ?""",
                    (row["id"],)
                ).fetchall()
                
                
                results.append({
                    "id": row["id"],
                    "content": row["content"],
                    "role": row["role"],
                    "keywords": [k["name"] for k in keywords],
                    "created_at": row["created_at"],
                    "similarity": float(similarity)
                })
            
            results.sort(key=lambda x: x["similarity"], reverse=True)
            return results[:limit]
    
    def get_recent(self, limit: int = 50) -> list[dict]:
        """Get recent memories.
        
        Args:
            limit: Maximum number of memories
            
        Returns:
            List of recent memories
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM memories ORDER BY created_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
            
            results = []
            for row in rows:
                keywords = conn.execute(
                    """SELECT k.name FROM keywords k
                       JOIN memory_keywords mk ON mk.keyword_id = k.id
                       WHERE mk.memory_id = ?""",
                    (row["id"],)
                ).fetchall()
                results.append({
                    "id": row["id"],
                    "content": row["content"],
                    "role": row["role"],
                    "keywords": [k["name"] for k in keywords],
                    "created_at": row["created_at"]
                })
            
            return results
    
    def delete(self, memory_id: int) -> bool:
        """Delete a memory.
        
        Args:
            memory_id: ID of the memory to delete
            
        Returns:
            True if deleted, False if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            conn.commit()
            return cursor.rowcount > 0
    
    def count(self) -> int:
        """Get total number of memories.
        
        Returns:
            Count of memories
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM memories")
            return cursor.fetchone()[0]
    
    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        norm_a, norm_b = np.linalg.norm(a), np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))
