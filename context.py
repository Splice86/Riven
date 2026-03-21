"""Context system for agent conversations - simplified."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Message:
    """A single message in the conversation."""
    role: str  # "user", "assistant", "system", "tool"
    content: str
    tool_name: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class ActivityLog:
    """Conversation history - what was said."""
    
    def __init__(self, max_messages: int = 100):
        self._messages: list[Message] = []
        self._max = max_messages
    
    def add(self, role: str, content: str, tool_name: str | None = None) -> None:
        """Add a message."""
        self._messages.append(Message(role=role, content=content, tool_name=tool_name))
        self._trim()
    
    def add_user(self, content: str) -> None:
        self.add("user", content)
    
    def add_assistant(self, content: str) -> None:
        self.add("assistant", content)
    
    def add_tool(self, tool_name: str, content: str) -> None:
        """Add a tool result."""
        self.add("tool", content, tool_name)
    
    def add_tool_result(self, tool_name: str, content: str) -> None:
        """Alias for add_tool."""
        self.add_tool(tool_name, content)

    def add_system(self, content: str) -> None:
        self.add("system", content)

    def _trim(self) -> None:
        if len(self._messages) > self._max:
            self._messages = self._messages[len(self._messages) - self._max:]
    
    def get_messages(self) -> list[dict]:
        """For LLM API."""
        return [{"role": m.role, "content": m.content} for m in self._messages]
    
    def get_history(self) -> str:
        """For text display."""
        return "\n".join([f"{m.role}: {m.content}" for m in self._messages])

    def clear(self) -> None:
        self._messages.clear()


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

