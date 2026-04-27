"""MOTD module — Message of the Day.

Riven can post messages that remote screens can subscribe to via /module/motd/.

Endpoints:
  - GET  /module/motd/        — list all messages
  - POST /module/motd/        — post a new message
  - GET  /module/motd/latest  — get most recent message

Tool:
  - post_motd(message, author=None) — async, broadcast to /module/motd/
"""

from .tools import get_module, post_motd, _motd_help, _motd_latest
from .storage import storage

__all__ = ["get_module", "register_routes", "post_motd", "storage"]


def register_routes(app):
    """Called by Riven at startup to mount this module's API routes."""
    from .routes import router
    app.include_router(router)
