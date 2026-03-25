"""Context system for agent conversations - memory-backed."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from memory_manager import MemoryManager

# Try to import config
try:
    from config import (
        DEFAULT_DB,
        CONTEXT_MAX_MESSAGES,
        CONTEXT_KEEP_RECENT,
        CONTEXT_CLUSTER_GAP_MINUTES,
        CONTEXT_CLUSTER_EXCLUDE_MINUTES
    )
except ImportError:
    DEFAULT_DB = "riven"
    CONTEXT_MAX_MESSAGES = 50
    CONTEXT_KEEP_RECENT = 10
    CONTEXT_CLUSTER_GAP_MINUTES = 30
    CONTEXT_CLUSTER_EXCLUDE_MINUTES = 30


@dataclass
class Message:
    """A single message in the conversation."""
    id: int  # Memory ID
    role: str  # "user", "assistant", "system", "tool"
    content: str
    tool_name: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class ActivityLog:
    """Conversation history backed by MemoryManager.
    
    Messages are stored in the memory API with node_type=context.
    When count exceeds max_messages, older ones are clustered and summarized.
    """
    
    def __init__(
        self,
        max_messages: int = CONTEXT_MAX_MESSAGES,
        memory_manager: Optional[MemoryManager] = None,
        keep_recent: int = CONTEXT_KEEP_RECENT,
        db_name: str = DEFAULT_DB
    ):
        self._max = max_messages
        self._keep_recent = keep_recent  # Keep this many un-summarized
        self._db_name = db_name
        self._manager = memory_manager or MemoryManager(db_name=db_name)
        self._recent_ids: list[int] = []  # Track recent message IDs
        self._cluster_gap = CONTEXT_CLUSTER_GAP_MINUTES
        self._cluster_exclude = CONTEXT_CLUSTER_EXCLUDE_MINUTES
    
    @property
    def manager(self) -> MemoryManager:
        """Access the memory manager."""
        return self._manager
    
    def add(self, role: str, content: str, tool_name: str | None = None, created_at: str | None = None) -> int:
        """Add a message to memory.
        
        Args:
            role: Message role (user, assistant, tool, system)
            content: Message content
            tool_name: Optional tool name for tool messages
            created_at: Optional ISO timestamp (for simulating historical messages)
            
        Returns:
            Memory ID of the stored message
        """
        props = {
            "role": role,
            "node_type": "context"
        }
        if tool_name:
            props["tool_name"] = tool_name
        
        result = self._manager.add(
            content=content,
            keywords=["context", role],
            properties=props,
            created_at=created_at
        )
        
        self._recent_ids.append(result.id)
        
        # Check if we need to prune/cluster
        self._maybe_cluster()
        
        return result.id
    
    def add_user(self, content: str, created_at: str | None = None) -> int:
        return self.add("user", content, created_at=created_at)
    
    def add_assistant(self, content: str, created_at: str | None = None) -> int:
        return self.add("assistant", content, created_at=created_at)
    
    def add_tool(self, tool_name: str, content: str, created_at: str | None = None) -> int:
        return self.add("tool", content, tool_name=tool_name, created_at=created_at)
    
    def add_tool_result(self, tool_name: str, content: str, created_at: str | None = None) -> int:
        """Alias for add_tool."""
        return self.add_tool(tool_name, content, created_at=created_at)

    def add_system(self, content: str, created_at: str | None = None) -> int:
        return self.add("system", content, created_at=created_at)
    
    def _maybe_cluster(self) -> None:
        """Check if we need to summarize old messages.
        
        Logic:
        1. Get count of recent UNSUMMARIZED memories
        2. If over threshold, try temporal clustering
        3. If cluster found, summarize it
        4. Else, reduce time delta until we get a cluster
        5. Mark summarized, repeat until under threshold
        """
        # Keep summarizing until we're under the threshold
        while True:
            # Get unsummarized context messages
            result = self._manager.search(
                "p:node_type=context AND NOT p:summarized=true",
                limit=10000
            )
            
            # Sort by time
            sorted_memories = sorted(result.memories, key=lambda m: m.created_at)
            total = len(sorted_memories)
            
            # If under threshold, done
            if total <= self._max:
                return
            
            # Calculate how many we could summarize (keep recent ones)
            if total <= self._keep_recent:
                return
            
            # Get messages to potentially summarize (everything except recent)
            to_summarize = sorted_memories[:-self._keep_recent] if self._keep_recent > 0 else sorted_memories
            
            if len(to_summarize) < 3:
                return
            
            print(f"Context at {total} unsummarized, checking for clusters...")
            
            # Try temporal clustering with decreasing time gaps
            memory_ids = None
            
            # Start with the configured gap, shrink until we get a cluster
            gap = self._cluster_gap
            while gap >= 5:
                clusters = self._manager.get_temporal_clusters(
                    gap_minutes=gap,
                    exclude_recent_minutes=self._cluster_exclude,
                    query_filter="p:node_type=context AND NOT p:summarized=true"
                )
                
                # Find cluster that overlaps with our to_summarize messages
                for cluster in clusters:
                    cluster_ids = set(cluster.memory_ids)
                    summarize_ids = set(m.id for m in to_summarize)
                    
                    # If cluster overlaps with what we want to summarize
                    if cluster_ids & summarize_ids:
                        memory_ids = list(cluster_ids & summarize_ids)
                        break
                
                if memory_ids:
                    break
                gap = gap // 2
            
            # If no temporal cluster found, just take oldest ones
            if not memory_ids:
                memory_ids = [m.id for m in to_summarize[:min(10, len(to_summarize))]]
            
            if len(memory_ids) < 3:
                return
            
            # Summarize them
            try:
                summary = self._manager.summarize_memories(
                    memory_ids,
                    keywords=["context_summary"]
                )
                print(f"  Summarized {len(memory_ids)} messages -> summary #{summary.id}")
                
                # Mark original messages as summarized
                for mid in memory_ids:
                    self._manager.update(mid, {"summarized": "true"})
                    
            except Exception as e:
                print(f"  Summarization failed: {e}")
                return  # Don't retry if LLM failed
            
            # Loop will check again and clean up if needed
    
    def get_messages(self, limit: int = 20) -> list[dict]:
        """Get recent UNSUMMARIZED messages for LLM API.
        
        This excludes messages that have been summarized to keep
        the context window focused on recent conversation.
        """
        # Only get unsummarized messages
        result = self._manager.search(
            "p:node_type=context AND NOT p:summarized=true",
            limit=limit
        )
        
        # Sort by created_at ascending for LLM
        memories = sorted(result.memories, key=lambda m: m.created_at)
        
        return [
            {
                "role": m.properties.get("role", "user"),
                "content": m.content
            }
            for m in memories
        ]
    
    def get_summaries(self, limit: int = 10) -> list[dict]:
        """Get conversation summaries.
        
        Returns the summarized versions of older conversation segments.
        """
        result = self._manager.search(
            "k:context_summary",
            limit=limit
        )
        
        # Sort by created_at descending (newest first)
        memories = sorted(result.memories, key=lambda m: m.created_at, reverse=True)
        
        return [
            {
                "content": m.content,
                "created_at": m.created_at
            }
            for m in memories
        ]
    
    def get_history(self, limit: int = 20) -> str:
        """Get recent messages as text for display."""
        messages = self.get_messages(limit)
        return "\n".join([f"{m['role']}: {m['content']}" for m in messages])
    
    def get_context_for_prompt(self) -> str:
        """Get formatted context for system prompt.
        
        Returns recent messages + any relevant long-term memories.
        """
        # Get recent context messages
        recent = self.get_messages(limit=10)
        
        if not recent:
            return "(No conversation history)"
        
        # Format as conversation
        lines = []
        for msg in recent:
            role = msg["role"]
            content = msg["content"][:200]  # Truncate long messages
            lines.append(f"{role}: {content}")
        
        return "\n".join(lines)
    
    def clear(self) -> None:
        """Clear all context messages (use with caution!)."""
        result = self._manager.search("p:node_type=context", limit=10000)
        for memory in result.memories:
            try:
                self._manager.delete(memory.id)
            except Exception:
                pass
        self._recent_ids.clear()


class SystemContext:
    """Dynamic system prompt - the {{tags}} template."""
    
    def __init__(self,prompt: str):
        self._template = prompt

    def apply_tags(self, replacements: list[tuple[str, str]]) -> str:
        """Replace {{tag}} placeholders."""
        prompt = self._template
        for tag, data in replacements:
            prompt = prompt.replace(f"{{{{{tag}}}}}", str(data))
        return prompt

