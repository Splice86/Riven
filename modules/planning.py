"""Planning module - goal tracking with file associations.

Goals are stored in .riven/plan.yaml at the project root (versioned with git).
Memory API is used for cross-session context search, but plan.yaml is the
source of truth.

Session ID automatically available via get_session_id().
"""

import json
import os
from datetime import datetime, timezone

import yaml

from modules import CalledFn, ContextFn, Module, get_session_id
from modules.memory_utils import _search_memories, _get_memory_url
from config import RIVEN_DIR, find_project_root

import requests as _requests


# =============================================================================
# Plan file I/O
# =============================================================================

def _plan_path() -> str | None:
    root = find_project_root()
    if root is None:
        return None
    return os.path.join(root, RIVEN_DIR, "plan.yaml")


def _ensure_plan_file() -> str | None:
    """Return error string if plan.yaml can't be accessed, None on success."""
    path = _plan_path()
    if path is None:
        return (
            "⚠️  No riven project found.\n\n"
            "   Run create_project() first, then try again."
        )
    if not os.path.exists(path):
        return (
            f"⚠️  {path} not found.\n\n"
            "   Run create_project() to initialise the project, which creates plan.yaml."
        )
    return None


def _read_plan() -> tuple[dict, str]:
    """Read plan.yaml. Returns (plan_dict, error_string)."""
    err = _ensure_plan_file()
    if err:
        return {}, err
    try:
        with open(_plan_path()) as f:
            return yaml.safe_load(f) or {}, ""
    except yaml.YAMLError as e:
        return {}, f"[ERROR] plan.yaml is malformed: {e}"
    except OSError as e:
        return {}, f"[ERROR] Could not read plan.yaml: {e}"


def _write_plan(plan: dict) -> str | None:
    """Write plan.yaml. Returns error string on failure, None on success."""
    err = _ensure_plan_file()
    if err:
        return err
    try:
        with open(_plan_path(), "w") as f:
            yaml.dump(plan, f, default_flow_style=False, sort_keys=False)
        return None
    except OSError as e:
        return f"[ERROR] Could not write plan.yaml: {e}"


# =============================================================================
# Goal helpers
# =============================================================================

def _normalize_files(files: list[str] | None) -> list[str]:
    """Normalize file list to absolute paths, deduplicated."""
    seen = set()
    result = []
    for f in (files or []):
        abs_path = os.path.abspath(os.path.expanduser(f))
        if abs_path not in seen:
            seen.add(abs_path)
            result.append(abs_path)
    return result


def _sync_to_memory(goal_id: int, goal: dict) -> None:
    """Fire-and-forget sync to memory API for context search indexing."""
    try:
        payload = {
            "content": f"Goal #{goal_id}: {goal.get('title', 'Untitled')}",
            "keywords": [
                get_session_id(),
                "planning",
                "goal",
                f"priority:{goal.get('priority', 'medium')}",
                f"status:{goal.get('status', 'active')}",
            ],
            "properties": {
                "goal_id": goal_id,
                "title": goal.get("title", ""),
                "description": goal.get("description", ""),
                "priority": goal.get("priority", "medium"),
                "status": goal.get("status", "active"),
                "files": json.dumps(goal.get("files", [])),
            },
        }
        _requests.post(f"{_get_memory_url()}/memories", json=payload, timeout=2)
    except Exception:
        pass


# =============================================================================
# Called functions
# =============================================================================

async def create_goal(
    title: str,
    description: str = None,
    priority: str = "medium",
    files: list[str] = None,
) -> str:
    """Create a new goal with optional files and description."""
    plan, err = _read_plan()
    if err:
        return err

    priority = priority.lower() if priority else "medium"
    if priority not in ("low", "medium", "high", "critical"):
        priority = "medium"

    next_id = plan.get("next_id", 1)
    goal_id = next_id
    plan["next_id"] = next_id + 1

    norm_files = _normalize_files(files)
    goal = {
        "title": title,
        "description": description or "",
        "priority": priority,
        "status": "active",
        "files": norm_files,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    plan["goals"][str(goal_id)] = goal

    err = _write_plan(plan)
    if err:
        return err

    _sync_to_memory(goal_id, goal)

    file_count = len(norm_files)
    files_info = f" ({file_count} file{'s' if file_count != 1 else ''})" if norm_files else ""
    return f"Created goal #{goal_id}: {title}{files_info}"


async def add_file_to_goal(goal_id: int, file_path: str) -> str:
    """Add a file to an existing goal."""
    plan, err = _read_plan()
    if err:
        return err

    goal = plan["goals"].get(str(goal_id))
    if not goal:
        return f"[ERROR] Goal #{goal_id} not found"

    abs_path = os.path.abspath(os.path.expanduser(file_path))
    files = goal.setdefault("files", [])

    if abs_path in files:
        return f"File already linked to goal #{goal_id}"

    files.append(abs_path)

    err = _write_plan(plan)
    if err:
        return err

    _sync_to_memory(goal_id, goal)
    return f"Linked {os.path.basename(abs_path)} to goal #{goal_id} ({len(files)} files)"


async def remove_file_from_goal(goal_id: int, file_path: str) -> str:
    """Remove a file from a goal."""
    plan, err = _read_plan()
    if err:
        return err

    goal = plan["goals"].get(str(goal_id))
    if not goal:
        return f"[ERROR] Goal #{goal_id} not found"

    abs_path = os.path.abspath(os.path.expanduser(file_path))
    files = goal.get("files", [])

    if abs_path not in files:
        return f"File not linked to goal #{goal_id}"

    files.remove(abs_path)

    err = _write_plan(plan)
    if err:
        return err

    _sync_to_memory(goal_id, goal)
    return f"Removed {os.path.basename(abs_path)} from goal #{goal_id}"


async def update_goal_status(goal_id: int, status: str) -> str:
    """Update goal status (active, paused, complete)."""
    plan, err = _read_plan()
    if err:
        return err

    goal = plan["goals"].get(str(goal_id))
    if not goal:
        return f"[ERROR] Goal #{goal_id} not found"

    status = status.lower()
    if status not in ("active", "paused", "complete"):
        return f"[ERROR] Invalid status. Use: active, paused, or complete"

    goal["status"] = status
    goal["updated_at"] = datetime.now(timezone.utc).isoformat()

    err = _write_plan(plan)
    if err:
        return err

    _sync_to_memory(goal_id, goal)
    return f"Goal #{goal_id} status → {status}"


async def list_goals(status: str = None) -> str:
    """List all goals, optionally filtered by status."""
    plan, err = _read_plan()
    if err:
        return err

    goals = plan.get("goals", {})
    if not goals:
        return "No goals yet. Create one with create_goal()."

    lines = ["Goals:"]
    for goal_id_str, goal in sorted(goals.items(), key=lambda x: int(x[0])):
        if status and goal.get("status") != status:
            continue
        title = goal.get("title", "Untitled")
        priority = goal.get("priority", "medium")
        goal_status = goal.get("status", "active")
        files = goal.get("files", [])

        priority_emoji = {
            "critical": "🔴", "high": "🟠",
            "medium": "🟡", "low": "🟢",
        }.get(priority, "⚪")
        status_marker = {
            "complete": "✅", "paused": "⏸", "active": "📌",
        }.get(goal_status, "")

        file_count = len(files)
        files_str = f" [{file_count} file{'s' if file_count != 1 else ''}]" if files else ""
        lines.append(f"  #{goal_id_str} {status_marker}{priority_emoji} {title}{files_str}")

    return "\n".join(lines)


async def get_goal(goal_id: int) -> str:
    """Get full details of a goal including linked files."""
    plan, err = _read_plan()
    if err:
        return err

    goal = plan["goals"].get(str(goal_id))
    if not goal:
        return f"[ERROR] Goal #{goal_id} not found"

    title = goal.get("title", "Untitled")
    priority = goal.get("priority", "medium")
    status = goal.get("status", "active")
    files = goal.get("files", [])
    description = goal.get("description", "")

    lines = [
        f"## Goal #{goal_id}: {title}",
        f"Status: {status} | Priority: {priority}",
    ]

    if files:
        lines.append(f"\nFiles ({len(files)}):")
        for f in files:
            lines.append(f"  - {f}")
    else:
        lines.append("\nNo files linked")

    if description:
        lines.append(f"\n{description}")

    return "\n".join(lines)


async def close_goal(goal_id: int) -> str:
    """Mark a goal as complete."""
    return await update_goal_status(goal_id, "complete")


# =============================================================================
# Context
# =============================================================================

def _planning_help() -> str:
    return """## Planning (Help)

Goals are your **planning system**. Use them to organize software work before, during, and after coding.
Goals are stored in `.riven/plan.yaml` and are versioned with git.

### How to Use Goals

**BEFORE writing any code — create a goal:**
When given a task, immediately create a goal describing what needs to be done.
This forces you to break the work into a concrete plan.

**Link files to goals — this IS the plan:**
The `files` parameter in create_goal() and add_file_to_goal() is your todo list.
These are the exact files you need to open and edit to complete the goal.
Before starting work on a goal, open its linked files. After finishing, close them.

**During work:**
- Reference the goal's linked files as your roadmap.
- As you discover additional files needed, add them with add_file_to_goal().
- When you finish a chunk of work, close the files you no longer need.

**After completing work:**
Call close_goal() to mark it complete.

### Tool Reference
- **create_goal(title, description?, priority?, files?)** - Create goal BEFORE coding
- **add_file_to_goal(goal_id, file_path)** - Add a file to an existing goal's plan
- **list_goals(status?)** - List all goals (active, paused, complete)
- **get_goal(goal_id)** - See goal details and its file list
- **update_goal_status(goal_id, status)** - Change status: active, paused, or complete
- **close_goal(goal_id)** - Mark goal complete
- **remove_file_from_goal(goal_id, file_path)** - Remove a file from a goal's plan

### Priority Levels
critical > high > medium > low

### Notes
- Goals are stored in `.riven/plan.yaml` (versioned with git)
- Files are stored as absolute paths
- Active goals and their linked files appear in context below ({planning})
- Goals are the source of truth for what files should be open"""


def _planning_context() -> str:
    """Dynamic context — active goals with files."""
    plan, err = _read_plan()
    if err:
        return f"No goals (project not initialised: run create_project() first)"

    goals = plan.get("goals", {})
    active = {gid: g for gid, g in goals.items() if g.get("status") == "active"}

    if not active:
        return "No active goals. Create one with create_goal() before starting work."

    lines = ["=== Active Goals (your work plan) ==="]
    lines.append("\nOpen the linked files for each goal before working on it.")
    lines.append("Close files that are not on any goal's file list.\n")

    for goal_id_str, goal in sorted(active.items(), key=lambda x: int(x[0])):
        title = goal.get("title", "Untitled")
        priority = goal.get("priority", "medium")
        files = goal.get("files", [])

        priority_emoji = {
            "critical": "🔴", "high": "🟠",
            "medium": "🟡", "low": "🟢",
        }.get(priority, "⚪")

        if files:
            file_names = ", ".join(os.path.basename(f) for f in files)
            lines.append(f"{priority_emoji} Goal #{goal_id_str}: {title}")
            lines.append(f"   Files: {file_names}")
        else:
            lines.append(
                f"{priority_emoji} Goal #{goal_id_str}: {title} "
                f"(no files — use add_file_to_goal to build the plan)"
            )

    return "\n".join(lines)


def get_module() -> Module:
    return Module(
        name="planning",
        called_fns=[
            CalledFn(
                name="create_goal",
                description="Create a new goal with optional description, priority, and file list.",
                parameters={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Goal title"},
                        "description": {"type": "string", "description": "Optional goal description"},
                        "priority": {"type": "string", "description": "Priority: critical, high, medium, low (default: medium)"},
                        "files": {"type": "array", "items": {"type": "string"}, "description": "Optional list of file paths to link"},
                    },
                    "required": ["title"],
                },
                fn=create_goal,
            ),
            CalledFn(
                name="add_file_to_goal",
                description="Link a file to an existing goal.",
                parameters={
                    "type": "object",
                    "properties": {
                        "goal_id": {"type": "integer", "description": "Goal ID to link file to"},
                        "file_path": {"type": "string", "description": "Path to the file (absolute or relative)"},
                    },
                    "required": ["goal_id", "file_path"],
                },
                fn=add_file_to_goal,
            ),
            CalledFn(
                name="remove_file_from_goal",
                description="Remove a file link from a goal.",
                parameters={
                    "type": "object",
                    "properties": {
                        "goal_id": {"type": "integer", "description": "Goal ID"},
                        "file_path": {"type": "string", "description": "Path to the file to unlink"},
                    },
                    "required": ["goal_id", "file_path"],
                },
                fn=remove_file_from_goal,
            ),
            CalledFn(
                name="update_goal_status",
                description="Update goal status.",
                parameters={
                    "type": "object",
                    "properties": {
                        "goal_id": {"type": "integer", "description": "Goal ID"},
                        "status": {"type": "string", "description": "New status: active, paused, or complete"},
                    },
                    "required": ["goal_id", "status"],
                },
                fn=update_goal_status,
            ),
            CalledFn(
                name="list_goals",
                description="List all goals, optionally filtered by status.",
                parameters={
                    "type": "object",
                    "properties": {
                        "status": {"type": "string", "description": "Optional filter: active, paused, or complete"},
                    },
                    "required": [],
                },
                fn=list_goals,
            ),
            CalledFn(
                name="get_goal",
                description="Get full details of a goal including linked files.",
                parameters={
                    "type": "object",
                    "properties": {
                        "goal_id": {"type": "integer", "description": "Goal ID to view"},
                    },
                    "required": ["goal_id"],
                },
                fn=get_goal,
            ),
            CalledFn(
                name="close_goal",
                description="Mark a goal as complete.",
                parameters={
                    "type": "object",
                    "properties": {
                        "goal_id": {"type": "integer", "description": "Goal ID to close"},
                    },
                    "required": ["goal_id"],
                },
                fn=close_goal,
            ),
        ],
        context_fns=[
            ContextFn(tag="planning_help", fn=_planning_help),
            ContextFn(tag="planning", fn=_planning_context),
        ],
    )
