"""Constants for the screens subsystem.

================================================================================
DESIGN
================================================================================

Screens are stored as memories in the DB with the following schema:

  Keyword:   "screen:{uid}"                   # Unique per screen (overwrite key)
  Keywords:  ["screen", session_id]           # For session-scoped queries
  Properties:
    - type:             "screen"
    - capacity_lines:   "30"                  # Max lines the screen can display
    - status:           "idle" | "bound"
    - bound_path:       "src/main.py"         # Absolute or project-relative path
    - bound_section:    "0-30" | null         # Line range or null for full file
    - bound_version:    "3"                   # Monotonically increasing edit count
    - bound_session:    "session-abc"         # Which Riven session it's bound to
    - last_seen:        "2025-05-29T10:00:00Z"
    - client_name:      "Workshop Screen 1"

This approach:
  - Session ID scopes screens to a Riven instance (survives reconnects)
  - Content = UID (overwrite key) ensures one record per screen
  - Properties carry all mutable state (survives server restarts)
  - Screens are filtered with: k:screen AND p:bound_session={session}

================================================================================
"""

from __future__ import annotations

# Memory keyword prefix for screen registrations
MEMORY_KEYWORD_PREFIX = "screen:"

# Full keyword used as search scope
MEMORY_KEYWORD = MEMORY_KEYWORD_PREFIX

# Default search limit
DEFAULT_SEARCH_LIMIT = 100


# =============================================================================
# Property Keys
# =============================================================================

PROP_TYPE = "type"
PROP_CAPACITY = "capacity_lines"
PROP_STATUS = "status"
PROP_BOUND_PATH = "bound_path"
PROP_BOUND_SECTION = "bound_section"
PROP_BOUND_VERSION = "bound_version"
PROP_BOUND_SESSION = "bound_session"
PROP_LAST_SEEN = "last_seen"
PROP_CLIENT_NAME = "client_name"

# Property values
STATUS_IDLE = "idle"
STATUS_BOUND = "bound"
TYPE_SCREEN = "screen"


# =============================================================================
# SQL Queries (for execute_sql)
# =============================================================================

# ---- Upsert screen (insert or replace) ---------------------------------------

SQL_UPSERT_SCREEN = """
INSERT INTO memories (content, created_at, last_updated)
VALUES (:uid, :now, :now)
ON CONFLICT(id) DO UPDATE SET
    content = :uid,
    last_updated = :now
WHERE content = :uid
"""

SQL_SET_KEYWORDS = """
DELETE FROM memory_keywords WHERE memory_id = :memory_id;
INSERT INTO memory_keywords (memory_id, keyword_id)
SELECT :memory_id, k.id FROM keywords k WHERE k.name IN :keywords;
"""

SQL_SET_PROPERTIES = """
DELETE FROM properties WHERE memory_id = :memory_id;
INSERT INTO properties (memory_id, key, value)
VALUES (:memory_id, :key, :value);
"""

# For memory_types we use the keywords table, not a separate column.
# "screen" is added as a keyword; the session_id is also added.

SQL_FIND_SCREEN_BY_UID = """
SELECT m.id, m.content, m.created_at, m.last_updated,
       p.key, p.value
FROM memories m
LEFT JOIN properties p ON p.memory_id = m.id
WHERE m.content = :uid
  AND m.content LIKE 'screen:%'
ORDER BY p.key
"""

SQL_GET_SCREEN_ID = """
SELECT id FROM memories WHERE content = :uid AND content LIKE 'screen:%'
"""

SQL_FIND_SCREENS_BY_SESSION = """
SELECT m.id, m.content,
       p.key, p.value
FROM memories m
LEFT JOIN properties p ON p.memory_id = m.id
WHERE 'screen' IN (SELECT kw.name FROM memory_keywords mk JOIN keywords kw ON kw.id = mk.keyword_id WHERE mk.memory_id = m.id)
  AND p.key = 'bound_session'
  AND p.value = :session_id
ORDER BY m.id
"""

SQL_GET_SCREEN_PROPS = """
SELECT p.key, p.value
FROM memories m
JOIN properties p ON p.memory_id = m.id
WHERE m.content = :uid
ORDER BY p.key
"""

SQL_UPDATE_PROP = """
DELETE FROM properties WHERE memory_id = :memory_id AND key = :key;
INSERT INTO properties (memory_id, key, value) VALUES (:memory_id, :key, :value);
"""

SQL_SET_SCREEN_STATUS = SQL_UPDATE_PROP  # Same pattern
SQL_SET_SCREEN_BOUND = SQL_UPDATE_PROP   # Same pattern

SQL_DELETE_SCREEN = """
DELETE FROM memories WHERE content = :uid AND content LIKE 'screen:%'
"""


# =============================================================================
# Keyword Builders
# =============================================================================

def make_screen_keyword(uid: str) -> str:
    """Build the memory keyword for a screen UID."""
    return f"{MEMORY_KEYWORD_PREFIX}{uid}"


def extract_uid_from_keyword(keyword: str) -> str | None:
    """Extract the UID portion from a screen keyword, or None if invalid."""
    if not keyword.startswith(MEMORY_KEYWORD_PREFIX):
        return None
    return keyword[len(MEMORY_KEYWORD_PREFIX):]


# =============================================================================
# Search Query Builders
# =============================================================================

def build_screen_search_query(session_id: str = None) -> str:
    """Build a search query for screens.

    Args:
        session_id: If provided, only return screens bound to this session.
                    If None, return all screens.

    Returns:
        Search query string
    """
    if session_id:
        return f"k:screen AND p:bound_session={session_id}"
    return "k:screen"
