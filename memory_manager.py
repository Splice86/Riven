"""
Memory Manager - Client for the Memories API.

Provides a clean Python interface to interact with the memory system.
"""

import requests
from datetime import datetime, timezone
from typing import Optional, Any
from dataclasses import dataclass


@dataclass
class Memory:
    """Represents a memory entry."""
    id: int
    content: str
    keywords: list[str]
    properties: dict[str, Any]
    created_at: str
    updated_at: str
    
    @property
    def node_type(self) -> str:
        """Get the node type from properties."""
        return self.properties.get("node_type", "memory")
    
    @property
    def temporal_location(self) -> str:
        """Get the temporal location from properties or created_at."""
        return self.properties.get("temporal_location") or self.created_at
    
    @classmethod
    def from_dict(cls, data: dict) -> "Memory":
        return cls(
            id=data["id"],
            content=data["content"],
            keywords=data.get("keywords", []),
            properties=data.get("properties", {}),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", "")
        )


@dataclass
class MemoryRef:
    """Lightweight reference to a memory (returned on create)."""
    id: int
    content: str


@dataclass
class SearchResult:
    """Search results container."""
    memories: list[Memory]
    count: int


class MemoryManager:
    """
    Client for interacting with the Memories API.
    
    Usage:
        manager = MemoryManager()
        manager.add("My memory", keywords=["tag1", "tag2"])
        results = manager.search("k:tag1")
    """
    
    DEFAULT_URL = "http://192.168.1.11:8030"
    
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or self.DEFAULT_URL
        self.session = requests.Session()
    
    # --- Core Operations ---
    
    def add(
        self,
        content: str,
        keywords: Optional[list[str]] = None,
        properties: Optional[dict[str, Any]] = None,
        created_at: Optional[str] = None,
        node_type: str = "memory"
    ) -> MemoryRef:
        """
        Add a new memory.
        
        All memories automatically get:
        - node_type: "memory" (or custom type like "cluster")
        - temporal_location: defaults to created_at
        
        Args:
            content: The memory text content
            keywords: List of keyword tags
            properties: Dict of custom properties
            created_at: Optional ISO timestamp (defaults to now)
            node_type: Type of node ("memory", "cluster", etc.)
            
        Returns:
            MemoryRef with id and content
        """
        # Default timestamp to now
        if not created_at:
            created_at = datetime.now(timezone.utc).isoformat()
        
        # Build properties with defaults
        props = properties or {}
        props["node_type"] = node_type
        props["temporal_location"] = props.get("temporal_location", created_at)
            
        payload = {
            "content": content,
            "created_at": created_at,
            "properties": props
        }
        if keywords:
            payload["keywords"] = keywords
            
        response = self.session.post(f"{self.base_url}/memories", json=payload)
        response.raise_for_status()
        data = response.json()
        return MemoryRef(id=data["id"], content=data["content"])
    
    def get(self, memory_id: int) -> Memory:
        """Get a memory by ID."""
        response = self.session.get(f"{self.base_url}/memories/{memory_id}")
        response.raise_for_status()
        return Memory.from_dict(response.json())
    
    def delete(self, memory_id: int) -> bool:
        """Delete a memory by ID."""
        response = self.session.delete(f"{self.base_url}/memories/{memory_id}")
        response.raise_for_status()
        return True
    
    def count(self) -> int:
        """Get total memory count."""
        response = self.session.get(f"{self.base_url}/stats")
        response.raise_for_status()
        return response.json().get("count", 0)
    
    # --- Search ---
    
    def search(self, query: str = "", limit: int = 50) -> SearchResult:
        """Search memories using the query syntax."""
        payload = {"query": query, "limit": limit}
        response = self.session.post(f"{self.base_url}/memories/search", json=payload)
        response.raise_for_status()
        data = response.json()
        
        return SearchResult(
            memories=[Memory.from_dict(m) for m in data.get("memories", [])],
            count=data.get("count", 0)
        )
    
    # --- Links ---
    
    def add_link(self, source_id: int, target_id: int, link_type: str = "related_to") -> dict:
        """Add a link between two memories."""
        payload = {"source_id": source_id, "target_id": target_id, "link_type": link_type}
        response = self.session.post(f"{self.base_url}/memories/link", json=payload)
        response.raise_for_status()
        return response.json()
    
    # --- Convenience Methods ---
    
    def get_by_keyword(self, keyword: str) -> list[Memory]:
        """Get all memories with a specific keyword."""
        result = self.search(f"k:{keyword}")
        return result.memories
    
    def get_by_property(self, key: str, value: Any) -> list[Memory]:
        """Get all memories with a specific property value."""
        result = self.search(f"p:{key}={value}")
        return result.memories
    
    def get_clusters(self) -> list[Memory]:
        """Get all cluster nodes."""
        return self.get_by_property("node_type", "cluster")
    
    def list_all(self, limit: int = 100) -> list[Memory]:
        """List all memories."""
        result = self.search("", limit=limit)
        return result.memories


if __name__ == "__main__":
    manager = MemoryManager()
    
    print(f"Total memories: {manager.count()}")
    
    # Add a test memory
    m = manager.add(
        "Testing the memory manager!",
        keywords=["test", "riven"],
        properties={"status": "working"}
    )
    print(f"Added memory #{m.id}: {m.content}")
    
    # Verify it has node_type and temporal_location
    mem = manager.get(m.id)
    print(f"  node_type: {mem.node_type}")
    print(f"  temporal_location: {mem.temporal_location}")
    
    # Search for it
    results = manager.search("k:test")
    print(f"Found {results.count} memories with 'test'")
    
    # Delete it
    manager.delete(m.id)
    print(f"Deleted memory #{m.id}")
    print(f"Total memories: {manager.count()}")
