"""Planning module - goal tracking with file associations.

Uses Memory API to store goals and track which files are relevant to each goal.
No callable functions for time (just context) - integrates with file module to
know what files should be open.

Session ID automatically available via get_session_id().
"""

import json
import os
import requests

from modules import CalledFn, ContextFn, Module, get_session_id
from modules.memory_utils import _search_memories, _get_memory_url


def _search_planning(query: str, limit: int = 50) -> list[dict]:
    """Search memory DB for planning records."""
    session_id = get_session_id()
    return _search_memories(session_id, query, limit=limit, keyword_prefix="k:planning AND ")


def _search_goals(status: str = None, limit: int = 20) -> list[dict]:
    """Search for goals, optionally filtered by status."""
    query = "k:goal"
    if status:
        query += f" AND p:status={status}"
    return _search_planning(query, limit)


def _get_goal_files(goal: dict) -> list[str]:
    """Extract file list from goal properties."""
    props = goal.get("properties", {})
    files_str = props.get("files", "[]")
    try:
        return json.loads(files_str)
    except (json.JSONDecodeError, TypeError):
        return []


# --- Called Functions ---

async def create_goal(
    title: str,
    description: str = None,
    priority: str = "medium",
    files: list[str] = None
) -> str:
    """Create a new goal with optional files and description."""
    session_id = get_session_id()
    
    priority = priority.lower() if priority else "medium"
    if priority not in ("low", "medium", "high", "critical"):
        priority = "medium"
    
    content = f"Goal: {title}"
    if description:
        content += f"\n\n{description}"
    
    keywords = [
        session_id,
        "planning",
        "goal",
        f"priority:{priority}",
    ]
    
    properties = {
        "status": "active",
        "priority": priority,
        "title": title,
        "files": json.dumps(files or []),
    }
    
    try:
        resp = requests.post(
            f"{_get_memory_url()}/memories",
            json={
                "content": content,
                "keywords": keywords,
                "properties": properties,
            },
            timeout=5
        )
        resp.raise_for_status()
        result = resp.json()
        goal_id = result.get("id", "?")
        
        file_count = len(files) if files else 0
        files_info = f" ({file_count} file{'s' if file_count != 1 else ''})" if files else ""
        return f"Created goal #{goal_id}: {title}{files_info}"
    except requests.RequestException as e:
        return f"[ERROR] Failed to create goal: {e}"


async def add_file_to_goal(goal_id: int, file_path: str) -> str:
    """Add a file to an existing goal."""
    session_id = get_session_id()
    
    try:
        resp = requests.get(f"{_get_memory_url()}/memories/{goal_id}", timeout=5)
        resp.raise_for_status()
        goal = resp.json()
    except requests.RequestException:
        return f"[ERROR] Goal #{goal_id} not found"
    
    props = goal.get("properties", {})
    files = _get_goal_files(goal)
    
    # Normalize and deduplicate
    abs_path = os.path.abspath(os.path.expanduser(file_path))
    
    if abs_path in files:
        return f"File already linked to goal #{goal_id}"
    
    files.append(abs_path)
    
    try:
        resp = requests.put(
            f"{_get_memory_url()}/memories/{goal_id}",
            json={
                "properties": {
                    **props,
                    "files": json.dumps(files),
                }
            },
            timeout=5
        )
        resp.raise_for_status()
        return f"Linked {os.path.basename(abs_path)} to goal #{goal_id} ({len(files)} files)"
    except requests.RequestException as e:
        return f"[ERROR] Failed to link file: {e}"


async def remove_file_from_goal(goal_id: int, file_path: str) -> str:
    """Remove a file from a goal."""
    session_id = get_session_id()
    
    try:
        resp = requests.get(f"{_get_memory_url()}/memories/{goal_id}", timeout=5)
        resp.raise_for_status()
        goal = resp.json()
    except requests.RequestException:
        return f"[ERROR] Goal #{goal_id} not found"
    
    props = goal.get("properties", {})
    files = _get_goal_files(goal)
    
    abs_path = os.path.abspath(os.path.expanduser(file_path))
    
    if abs_path not in files:
        return f"File not linked to goal #{goal_id}"
    
    files.remove(abs_path)
    
    try:
        resp = requests.put(
            f"{_get_memory_url()}/memories/{goal_id}",
            json={
                "properties": {
                    **props,
                    "files": json.dumps(files),
                }
            },
            timeout=5
        )
        resp.raise_for_status()
        return f"Removed {os.path.basename(abs_path)} from goal #{goal_id}"
    except requests.RequestException as e:
        return f"[ERROR] Failed to remove file: {e}"


async def update_goal_status(goal_id: int, status: str) -> str:
    """Update goal status (active, paused, complete)."""
    status = status.lower()
    if status not in ("active", "paused", "complete"):
        return f"[ERROR] Invalid status. Use: active, paused, or complete"
    
    try:
        resp = requests.put(
            f"{_get_memory_url()}/memories/{goal_id}",
            json={"properties": {"status": status}},
            timeout=5
        )
        resp.raise_for_status()
        return f"Goal #{goal_id} status → {status}"
    except requests.RequestException:
        return f"[ERROR] Goal #{goal_id} not found"


async def list_goals(status: str = None) -> str:
    """List all goals, optionally filtered by status."""
    goals = _search_goals(status=status, limit=50)
    
    if not goals:
        status_msg = f" ({status})" if status else ""
        return f"No goals found{status_msg}."
    
    lines = [f"Goals:"]
    for goal in goals:
        props = goal.get("properties", {})
        title = props.get("title", "Untitled")
        priority = props.get("priority", "medium")
        goal_status = props.get("status", "active")
        files = _get_goal_files(goal)
        
        priority_emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(priority, "⚪")
        status_marker = "✅" if goal_status == "complete" else "⏸" if goal_status == "paused" else "📌"
        
        file_count = len(files)
        files_str = f" [{file_count} file{'s' if file_count != 1 else ''}]" if files else ""
        
        lines.append(f"  #{goal['id']} {status_marker}{priority_emoji} {title}{files_str}")
    
    return "\n".join(lines)


async def get_goal(goal_id: int) -> str:
    """Get full details of a goal including linked files."""
    try:
        resp = requests.get(f"{_get_memory_url()}/memories/{goal_id}", timeout=5)
        resp.raise_for_status()
        goal = resp.json()
    except requests.RequestException:
        return f"[ERROR] Goal #{goal_id} not found"
    
    props = goal.get("properties", {})
    title = props.get("title", "Untitled")
    priority = props.get("priority", "medium")
    status = props.get("status", "active")
    files = _get_goal_files(goal)
    
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
    
    content = goal.get("content", "")
    if content:
        # Skip the "Goal: title" prefix if present
        if content.startswith("Goal:"):
            content = content.split("\n\n", 1)[-1] if "\n\n" in content else ""
        if content:
            lines.append(f"\n{content}")
    
    return "\n".join(lines)


async def close_goal(goal_id: int) -> str:
    """Mark a goal as complete."""
    return await update_goal_status(goal_id, "complete")


def _planning_help() -> str:
    """Static tool documentation."""
    return """## Planning (Help)

Goals are your **planning system**. Use them to organize software work before, during, and after coding.

### How to Use Goals for Software Work

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
Call close_goal() to mark it complete. This removes it from the active goals list.

### Example Workflow
1. Task: "add user auth to the API"
2. Call create_goal(title="Add user authentication", description="...", files=["api.py", "auth.py"])
3. Call get_goal(goal_id) to see the plan — opens relevant files first
4. Edit api.py and auth.py
5. Call close_goal(goal_id) when done

### Tool Reference
- **create_goal(title, description?, priority?, files?)** - Create goal BEFORE coding (planning step)
- **add_file_to_goal(goal_id, file_path)** - Add a file to an existing goal's plan
- **list_goals(status?)** - List all goals (active, paused, complete)
- **get_goal(goal_id)** - See goal details and its file list (your plan for that goal)
- **update_goal_status(goal_id, status)** - Change status: active, paused, or complete
- **close_goal(goal_id)** - Mark goal complete (after all work is done)
- **remove_file_from_goal(goal_id, file_path)** - Remove a file from a goal's plan

### Priority Levels
critical > high > medium > low

### Notes
- Goals are session-scoped (private to this session)
- Files are stored as absolute paths
- Active goals and their linked files appear in context below ({planning})
- Goals are the source of truth for what files should be open — if a file is not on any active goal's list, consider closing it"""


def _planning_context() -> str:
    """Dynamic context - active goals with files. Changes when goals are created/updated.
    
    This context shows the current work plan. The linked files are what you should
    have open. If open files are NOT on any active goal's list, close them.
    """
    session_id = get_session_id()
    goals = _search_goals(status="active", limit=10)
    
    if not goals:
        return "No active goals. Create one with create_goal() before starting work."
    
    lines = ["=== Active Goals (your work plan) ==="]
    lines.append("\nOpen the linked files for each goal before working on it.")
    lines.append("Close files that are not on any goal's file list.\n")
    
    for goal in goals:
        props = goal.get("properties", {})
        title = props.get("title", "Untitled")
        priority = props.get("priority", "medium")
        files = _get_goal_files(goal)
        
        priority_emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(priority, "⚪")
        
        if files:
            file_names = ", ".join(os.path.basename(f) for f in files)
            lines.append(f"{priority_emoji} Goal #{goal['id']}: {title}")
            lines.append(f"   Files: {file_names}")
        else:
            lines.append(f"{priority_emoji} Goal #{goal['id']}: {title} (no files — use add_file_to_goal to build the plan)")
    
    return "\n".join(lines)


def get_module() -> Module:
    """Get the planning module."""
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
