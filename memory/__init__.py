"""Memory API for Riven - vector-based memory storage with SQLite.

Usage:
    # Run the API server
    python -m memory.api
    
    # Or import the database directly
    from memory import MemoryDB
    db = MemoryDB()
    db.add("Hello world", "user")
"""

from memory.embedding import EmbeddingModel
from memory.db import MemoryDB
from memory import api

__all__ = ["EmbeddingModel", "MemoryDB"]
