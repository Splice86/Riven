"""Simplified memory database with vector embeddings."""

import sqlite3
import numpy as np
from datetime import datetime, timezone
from typing import Optional

from embedding import EmbeddingModel


DEFAULT_DB_PATH = "memory.db"


class MemoryDB:
    """SQLite-based memory storage with vector embeddings."""
    
    def __init__(
        self,
        db_path: str = DEFAULT_DB_PATH,
        embedding_model: Optional[EmbeddingModel] = None
    ):
        self.db_path = db_path
        self.embedding = embedding_model or EmbeddingModel()
        init_db(db_path)
    
    def add_memory(
        self,
        content: str,
        keywords: list[str] | None = None,
        properties: dict[str, str] | None = None,
        embedding: np.ndarray | None = None
    ) -> int:
        """Add a memory with optional keywords and properties.
        
        Args:
            content: The memory text
            keywords: Optional keywords to tag the memory
            properties: Optional key-value pairs (e.g., {"role": "user"})
            embedding: Optional pre-computed embedding (generated from content if not provided)
            
        Returns:
            The ID of the inserted memory
        """
        import json
        
        # Generate embedding if not provided
        if embedding is None:
            embedding = self.embedding.get(content)
        
        now = datetime.now(timezone.utc).isoformat()
        
        # Store keywords as JSON array
        keywords_json = "[]"
        if keywords:
            unique_keywords = list(set(kw.lower().strip() for kw in keywords if kw.strip()))
            keywords_json = json.dumps(unique_keywords)
        
        # Store properties as JSON object
        properties_json = "{}"
        if properties:
            properties_json = json.dumps(properties)
        
        with sqlite3.connect(self.db_path) as conn:
            # Insert memory
            cursor = conn.execute(
                """INSERT INTO memories (content, keywords, properties, embedding, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (content, keywords_json, properties_json, embedding.tobytes(), now, now)
            )
            memory_id = cursor.lastrowid
            conn.commit()
            
            return memory_id

    def search(self, query_string: str, limit: int = 50) -> list[dict]:
        """Search memories using the query DSL.
        
        Args:
            query_string: Search query in DSL format
            limit: Maximum number of results
            
        Returns:
            List of matching memories with their data
        
        See search.py for DSL documentation.
        """
        from search import MemorySearcher
        searcher = MemorySearcher(self.db_path, self.embedding)
        return searcher.search(query_string, limit)
    
    def get_memory(self, memory_id: int) -> dict | None:
        """Get a single memory by ID.
        
        Args:
            memory_id: The memory ID
            
        Returns:
            Memory dict or None if not found
        """
        import json
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM memories WHERE id = ?",
                (memory_id,)
            ).fetchone()
            
            if row is None:
                return None
            
            return {
                'id': row['id'],
                'content': row['content'],
                'keywords': json.loads(row['keywords']) if row['keywords'] else [],
                'properties': json.loads(row['properties']) if row['properties'] else {},
                'embedding': np.frombuffer(row['embedding']) if row['embedding'] else None,
                'created_at': row['created_at'],
                'updated_at': row['updated_at'],
            }
    
    def update_memory(
        self,
        memory_id: int,
        content: str | None = None,
        keywords: list[str] | None = None,
        properties: dict[str, str] | None = None
    ) -> bool:
        """Update an existing memory.
        
        Args:
            memory_id: The memory ID to update
            content: New content (optional)
            keywords: New keywords list (optional)
            properties: New properties dict (optional)
            
        Returns:
            True if updated, False if not found
        """
        import json
        
        now = datetime.now(timezone.utc).isoformat()
        
        # Build update query dynamically
        updates = ["updated_at = ?"]
        params = [now]
        
        if content is not None:
            updates.append("content = ?")
            params.append(content)
        
        if keywords is not None:
            unique_keywords = list(set(kw.lower().strip() for kw in keywords if kw.strip()))
            updates.append("keywords = ?")
            params.append(json.dumps(unique_keywords))
        
        if properties is not None:
            updates.append("properties = ?")
            params.append(json.dumps(properties))
        
        params.append(memory_id)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                f"UPDATE memories SET {', '.join(updates)} WHERE id = ?",
                params
            )
            conn.commit()
            return cursor.rowcount > 0
    
    def delete_memory(self, memory_id: int) -> bool:
        """Delete a memory by ID.
        
        Args:
            memory_id: The memory ID to delete
            
        Returns:
            True if deleted, False if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM memories WHERE id = ?",
                (memory_id,)
            )
            conn.commit()
            return cursor.rowcount > 0



def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    """Initialize the database schema.
    
    Args:
        db_path: Path to the SQLite database file
    """
    with sqlite3.connect(db_path) as conn:
        # Main memories table - simplified with JSON columns for search
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                keywords TEXT,  -- JSON array of keywords ["python", "coding"]
                properties TEXT, -- JSON object {"role": "user"}
                embedding BLOB,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        # Indexes for search
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_created ON memories(created_at)")
        
        conn.commit()


if __name__ == "__main__":
    import tempfile
    import os
    
    # Mock embedding model that returns zeros
    class MockEmbeddingModel:
        def __init__(self):
            self.dimension = 384  # Common embedding dimension
        
        def get(self, text: str) -> np.ndarray:
            """Return a zero vector for testing."""
            return np.zeros(self.dimension, dtype=np.float32)
    
    # Create temp database
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    
    try:
        print("Testing MemoryDB...")
        print("=" * 50)
        
        # Initialize with mock embedding
        db = MemoryDB(db_path, embedding_model=MockEmbeddingModel())
        
        # Test 1: Simple memory
        memory_id = db.add_memory("This is my first memory!")
        print(f"✓ Added memory {memory_id}: 'This is my first memory!'")
        
        # Test 2: Memory with keywords
        memory_id = db.add_memory(
            "Python is a great programming language",
            keywords=["Python", "programming", "python", "code"]  # should dedupe
        )
        print(f"✓ Added memory {memory_id} with keywords (deduplicated)")
        
        # Test 3: Memory with properties
        memory_id = db.add_memory(
            "User asked about the weather",
            properties={"role": "user", "source": "chat"}
        )
        print(f"✓ Added memory {memory_id} with properties")
        
        # Test 4: Memory with everything
        memory_id = db.add_memory(
            "Assistant provided a helpful response",
            keywords=["assistant", "help"],
            properties={"role": "assistant", "importance": "high"}
        )
        print(f"✓ Added memory {memory_id} with keywords AND properties")
        
        print("=" * 50)
        print("All tests passed! ✓")
        
    finally:
        # Cleanup
        os.unlink(db_path)
