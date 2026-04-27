from typing import Literal
from modules import Module, CalledFn

from .storage import storage


def post_motd(message: str, author: str = None) -> str:
    """Post a message of the day. Viewers subscribed to /module/motd/ will see it.

    Args:
        message: The message content (1–2000 chars).
        author: Optional author name or identifier.

    Returns:
        A confirmation string with the message ID and preview.
    """
    if not message or not message.strip():
        return "Message cannot be empty."

    msg = storage.add(message.strip(), author=author if author else None)
    author_str = f" by {msg.author}" if msg.author else ""
    preview = msg.message[:80] + ("..." if len(msg.message) > 80 else "")
    return (
        f"📢 MOTD #{msg.id} posted{author_str} at {msg.created_at}\n"
        f"   {preview}"
    )


def get_module():
    """Return the MOTD module definition."""
    return Module(
        name="motd",
        context_fns=[],
        called_fns=[
            CalledFn(
                name="post_motd",
                description=(
                    "Post a message of the day. Use this to broadcast important "
                    "notices or reminders to connected remote screens. "
                    "Keep messages concise and actionable."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "message": {
                            "type": "string",
                            "description": "The message content (1–2000 chars).",
                        },
                        "author": {
                            "type": "string",
                            "description": "Optional author name or identifier.",
                        },
                    },
                    "required": ["message"],
                },
                fn=post_motd,
            ),
        ],
    )
