"""MOTD module — Message of the Day.

Riven can post messages that remote screens can subscribe to via /module/motd/.

Tools:
  - post_motd(message, author=None) — post a new message

Endpoints:
  - GET  /module/motd/        — list all messages
  - POST /module/motd/        — post a new message
  - GET  /module/motd/latest  — get most recent message
"""

import datetime

from .storage import storage
from .tools import get_module as _get_module_tools


def get_module():
    """Return the MOTD module definition for Riven's module registry."""
    return _get_module_tools()


def register_routes(app):
    """Called by Riven at startup to mount this module's API routes."""
    from .routes import router
    app.include_router(router)
