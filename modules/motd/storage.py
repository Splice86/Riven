import datetime
import threading
from typing import Optional

from .models import MotdMessage


class MotdStorage:
    """In-memory storage for MOTD messages. Thread-safe."""

    def __init__(self):
        self._messages: list[MotdMessage] = []
        self._lock = threading.Lock()
        self._next_id = 1

    def add(self, message: str, author: Optional[str] = None) -> MotdMessage:
        with self._lock:
            msg = MotdMessage(
                id=self._next_id,
                message=message,
                author=author,
                created_at=datetime.datetime.utcnow().isoformat() + "Z",
            )
            self._messages.append(msg)
            self._next_id += 1
            return msg

    def list_all(self) -> list[MotdMessage]:
        with self._lock:
            return list(reversed(self._messages))  # newest first

    def get_latest(self) -> Optional[MotdMessage]:
        with self._lock:
            return self._messages[-1] if self._messages else None

    def count(self) -> int:
        with self._lock:
            return len(self._messages)


# Global singleton — lives for the lifetime of the API server process
storage = MotdStorage()
