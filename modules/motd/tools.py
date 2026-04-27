from modules import Module, CalledFn, ContextFn

from .storage import storage


async def post_motd(message: str, author: str = None) -> str:
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


def _motd_help() -> str:
    """Static tool documentation injected into the system prompt."""
    return """## MOTD (Message of the Day)

Use the **post_motd** tool to broadcast a message to all connected remote screens.

- **post_motd(message, author?)** — Post a message. Keep it short and actionable.

Example: `post_motd("Deploy at noon today!", "riven")`
"""


def _motd_latest() -> str:
    """Dynamic context — inject the most recent MOTD."""
    msg = storage.get_latest()
    if msg is None:
        return "## MOTD\n\nNo messages posted yet."
    author_str = f" by {msg.author}" if msg.author else ""
    return f"## MOTD\n\nCurrent: {msg.message}{author_str} ({msg.created_at})"


def get_module() -> Module:
    """Return the MOTD module definition."""
    return Module(
        name="motd",
        context_fns=[
            ContextFn(tag="motd_help", fn=_motd_help),
            ContextFn(tag="motd", fn=_motd_latest),
        ],
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
