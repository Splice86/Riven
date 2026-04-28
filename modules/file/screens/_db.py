"""
Simplified screen DB layer — screens are ephemeral (in-memory only).

All functions are stubs that return empty/False so the rest of the code
remains compatible if anything still calls them. Real state lives in _registry.
"""

from typing import Optional


def register_screen(uid, session_id, client_name="Screen") -> dict:
    return {
        "memory_id": None,
        "uid": uid,
        "screen_status": "idle",
        "bound_path": None,
        "client_name": client_name,
    }


def get_screen(uid: str) -> Optional[dict]:
    return None


def get_all_screens() -> list:
    return []


def get_screens_for_session(session_id: str) -> list:
    return []


def update_screen_prop(uid: str, key: str, value: str) -> bool:
    return True


def update_screen(uid: str, **props) -> bool:
    return True


def set_screen_bound(uid: str, session_id: str, path: str, version=1) -> bool:
    return True


def release_screen(uid: str) -> bool:
    return True


def delete_screen(uid: str) -> bool:
    return True


def touch_screen(uid: str) -> bool:
    return True
