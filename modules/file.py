"""File module with fuzzy matching for temp_riven.

Provides file editing capabilities with:
- open_file: Add file to context (stored in memory DB)
- replace_text: Fuzzy-match replacement with auto-save
- preview_replace: Show matched text without modifying
- diff_text: Show before/after of a replacement
- close_file: Remove from context
- close_all_files: Clear all open files
- file_info: Get file metadata
- search_files: Grep pattern across files
- list_dir: List directory contents
- get_context: Context function that injects open file content

Session ID is automatically available via get_session_id().
"""

import ast
import difflib
import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

import requests
import jellyfish

from modules import CalledFn, ContextFn, Module, get_session_id
from modules.memory_utils import _search_memories, _delete_memory, _get_memory, _set_memory, _get_memory_url


# =============================================================================
# Data Classes for Structured Responses
# =============================================================================

@dataclass
class EditResult:
    """Structured result for file edit operations.

    Provides machine-readable results for all file editing operations,
    making it easier to build agents and debug issues.
    """
    success: bool
    path: str
    message: str
    changed: bool = False
    diff: str = ""
    line_start: int | None = None
    line_end: int | None = None
    similarity: float | None = None
    syntax_error: str | None = None

    def to_string(self) -> str:
        """Convert to user-friendly string.

        Returns a formatted string suitable for displaying to users
        or logging. Includes all relevant details.
        """
        if self.success:
            parts = [f"✅ {self.message}"]
            if self.line_start and self.line_end:
                parts.append(f"   Lines {self.line_start}-{self.line_end}")
            if self.similarity:
                parts.append(f"   Match: {self.similarity:.0%}")
            if self.diff:
                parts.append(f"\n{self.diff}")
            return "\n".join(parts)
        else:
            parts = [f"❌ {self.message}"]
            if self.similarity:
                parts.append(f"   Best match: {self.similarity:.0%}")
            if self.syntax_error:
                parts.append(f"   Syntax error: {self.syntax_error}")
            if self.diff:
                parts.append(f"\n{self.diff}")
            return "\n".join(parts)

    def __str__(self) -> str:
        """String representation for logging."""
        return self.to_string()


@dataclass
class Replacement:
    """A single text replacement for batch operations.

    Represents one old_text -> new_text transformation to be applied
    to a file. Used by batch_edit() to apply multiple replacements
    in a single pass.
    """
    old_str: str
    new_str: str

    def __post_init__(self):
        """Validate replacement data."""
        if not isinstance(self.old_str, str):
            raise TypeError(f"old_str must be str, got {type(self.old_str)}")
        if not isinstance(self.new_str, str):
            raise TypeError(f"new_str must be str, got {type(self.new_str)}")


@dataclass
class FileEditSession:
    """A session of related file edits, persisted in MemoryDB.

    Tracks a complete edit operation including all files modified,
    the diff, and original content snapshots for undo/redo support.
    """
    session_id: str
    tool_name: str
    files: list[str] = field(default_factory=list)
    operations: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    status: Literal["pending", "completed", "failed", "rolled_back"] = "pending"
    diff: str = ""
    original_snapshots: dict[str, str] = field(default_factory=dict)
    modified_snapshots: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "session_id": self.session_id,
            "tool_name": self.tool_name,
            "files": self.files,
            "operations": self.operations,
            "created_at": self.created_at.isoformat(),
            "status": self.status,
            "diff": self.diff,
            "original_snapshots": self.original_snapshots,
            "modified_snapshots": self.modified_snapshots,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FileEditSession":
        """Create from dictionary (e.g., from MemoryDB)."""
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.now()

        return cls(
            session_id=data["session_id"],
            tool_name=data["tool_name"],
            files=data.get("files", []),
            operations=data.get("operations", 0),
            created_at=created_at,
            status=data.get("status", "pending"),
            diff=data.get("diff", ""),
            original_snapshots=data.get("original_snapshots", {}),
            modified_snapshots=data.get("modified_snapshots", {}),
        )


# =============================================================================
# Robustness Helpers
# =============================================================================

def _atomic_write(path: str, content: str) -> None:
    """Write content atomically using temp file + rename.

    Prevents partial writes if the process is interrupted mid-write.
    On POSIX systems, os.replace() is atomic. On Windows, we do our best
    effort with the same pattern.

    Args:
        path: Target file path
        content: Content to write

    Raises:
        OSError: If the write fails after attempting cleanup

    Note:
        The temp file is always cleaned up, even on failure.
    """
    dir_path = os.path.dirname(path) or '.'

    # Create parent directories if needed
    os.makedirs(dir_path, exist_ok=True)

    fd = None
    temp_path = None
    try:
        fd, temp_path = tempfile.mkstemp(dir=dir_path, suffix='.tmp')
        with os.fdopen(fd, 'w') as f:
            f.write(content)
        os.replace(temp_path, path)  # Atomic on POSIX
    except Exception:
        # Clean up temp file on failure
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError:
                pass  # Best effort cleanup
        raise


def _verify_write(path: str, expected_content: str) -> bool:
    """Verify that the file on disk matches the expected content.

    Args:
        path: File path to verify
        expected_content: Expected content after write

    Returns:
        True if the file matches, False otherwise
    """
    try:
        with open(path, 'r') as f:
            actual_content = f.read()
        return actual_content == expected_content
    except Exception:
        return False


def _sanitize_content(content: str) -> str:
    """Sanitize content to handle encoding edge cases.

    Surrogate characters (U+D800-U+DFFF) can cause issues when
    writing UTF-8 encoded files. This function replaces them with
    the Unicode replacement character (U+FFFD).

    Args:
        content: Raw file content as read by Python

    Returns:
        Sanitized content safe for UTF-8 encoding
    """
    try:
        # Try to encode as UTF-8 with surrogatepass, then decode
        return content.encode("utf-8", errors="surrogatepass").decode("utf-8", errors="replace")
    except (UnicodeEncodeError, UnicodeDecodeError):
        # Fallback: replace any remaining surrogates with replacement char
        return content.replace('\ud800', '\ufffd').replace('\udfff', '\ufffd')


def _validate_python(content: str) -> tuple[bool, str | None]:
    """Validate Python syntax using AST parsing.

    Args:
        content: Python source code to validate

    Returns:
        Tuple of (is_valid, error_message). error_message is None if valid.
    """
    try:
        ast.parse(content)
        return True, None
    except SyntaxError as e:
        lineno = e.lineno or "?"
        offset = e.offset or "?"
        return False, f"Syntax error at line {lineno}, column {offset}: {e.msg}"


def _count_tokens(text: str) -> int:
    """Rough token count - ~4 chars per token."""
    return len(text) // 4


def _find_best_window(
    haystack_lines: list[str],
    needle: str,
    threshold: float = 0.95
) -> tuple[tuple[int, int] | None, float]:
    """Find line window with best Jaro-Winkler similarity to needle.
    
    Args:
        haystack_lines: The file content split into lines
        needle: The text to search for
        threshold: Minimum similarity score (0.0-1.0)
        
    Returns:
        ((start_line, end_line), score) or (None, best_score) if not found
    """
    needle = needle.rstrip("\n")
    needle_lines = needle.splitlines()
    win_size = len(needle_lines)
    
    if win_size == 0:
        return None, 0.0
    
    best_score = 0.0
    best_span: tuple[int, int] | None = None
    
    for i in range(len(haystack_lines) - win_size + 1):
        window = "\n".join(haystack_lines[i:i + win_size])
        window_clean = window.rstrip('\n')
        score = jellyfish.jaro_winkler_similarity(window_clean, needle)
        if score > best_score:
            best_score = score
            best_span = (i, i + win_size)
    
    if best_score >= threshold:
        return best_span, best_score
    return None, best_score


def _file_type(path: str) -> str:
    """Return a short file type description based on extension."""
    ext = Path(path).suffix.lower()
    type_map = {
        '.py': 'python',
        '.yaml': 'yaml',
        '.yml': 'yaml',
        '.json': 'json',
        '.md': 'markdown',
        '.txt': 'text',
        '.sh': 'shell',
        '.bash': 'shell',
        '.zsh': 'shell',
        '.c': 'c',
        '.h': 'c',
        '.cpp': 'cpp',
        '.rs': 'rust',
        '.go': 'go',
        '.js': 'javascript',
        '.ts': 'typescript',
        '.html': 'html',
        '.css': 'css',
        '.sql': 'sql',
        '.toml': 'toml',
        '.ini': 'ini',
        '.cfg': 'cfg',
        '.conf': 'conf',
        '.env': 'env',
        '.gitignore': 'gitignore',
        '.dockerfile': 'dockerfile',
    }
    return type_map.get(ext, ext.lstrip('.') or 'file')


def _get_cwd() -> str:
    """Get the current working directory from session memory, or fall back to OS cwd."""
    session_id = get_session_id()
    memory = _get_memory(session_id, "cwd")
    if memory:
        props = memory.get("properties", {})
        return props.get("path", os.getcwd())
    return os.getcwd()


def _file_help() -> str:
    """Static tool documentation - does not change between calls."""
    return """## File Tools (Help)

### Workflow
1. **pwd()** - Show current working directory for this session
2. **chdir(path)** - Change the working directory for this session
3. **open_file(path, line_start?, line_end?)** - Open a file into context
4. **replace_text(path, old_text, new_text, threshold?)** - Fuzzy-match replacement (auto-saves)
5. **preview_replace(path, old_text, threshold?)** - Show matched text without modifying
6. **diff_text(path, old_text, new_text, threshold?)** - Show before/after of proposed change
7. **close_file(filename, line_start?, line_end?)** - Close file/range
8. **close_all_files()** - Close all open files
9. **file_info(path)** - Get file metadata
10. **search_files(pattern, path?)** - Grep pattern across files
11. **list_dir(path?)** - List directory contents
12. **write_text(path, content)** - Write content to a file (creates if needed)

### Guidelines
- Use pwd() to see the current directory and chdir(path) to change it
- The working directory persists across calls in this session (survives module reloads)
- Functions like search_files() and list_dir() use the session cwd as default when path is omitted
- Prefer opening whole files (no line_start/line_end) - small files are fine to read entirely
- Avoid opening the same file multiple times in different ranges - open once with a wider range or not at all
- Use search_files() to find patterns before opening files
- Use preview_replace() to verify a match before committing to replace_text()
- Use diff_text() to preview a full change before applying it
- Close files when done to keep context clean
- Use file_info() for metadata without loading content
- Be sensitive to context growth - open only what you need
- Use write_text() to create new files or overwrite existing ones entirely"""


def _file_context() -> str:
    """Dynamic context - currently open files. Changes when files are opened/closed."""
    session_id = get_session_id()
    query = "k:file"
    memories = _search_memories(session_id, query, limit=50)
    cwd = _get_cwd()

    if not memories:
        return f"cwd: {cwd}\n\nNo files currently open"
    
    lines = [f"cwd: {cwd}", "", "=== Open Files ==="]
    total_tokens = 0
    
    for mem in memories:
        props = mem.get("properties", {})
        path = props.get("path")
        
        if not path or not os.path.exists(path):
            continue
        
        try:
            with open(path, 'r') as f:
                content = f.read()
            
            line_start = props.get("line_start", "0")
            line_end = props.get("line_end", "*")
            
            start = int(line_start) if line_start != "0" else 0
            if line_end and line_end != "*":
                content_lines = content.splitlines(keepends=True)
                content = ''.join(content_lines[start:int(line_end)])
            
            filename = os.path.basename(path)
            end_display = line_end if line_end != "*" else "end"
            lines.append(f"\n=== {filename} [lines {line_start}-{end_display}] ===")
            lines.append(content)
            total_tokens += _count_tokens(content)
        except Exception:
            continue
    
    lines.append(f"\n\n--- File Context Stats ---")
    lines.append(f"Total open file tokens: {total_tokens:,}")
    
    return "\n".join(lines)


# --- Called Functions ---

async def open_file(path: str, line_start: int = None, line_end: int = None) -> str:
    """Open a file and add it to the file context.
    
    Args:
        path: Path to the file to open.
        line_start: Start line for partial opening (0-indexed, None = from start)
        line_end: End line for partial opening (None = to end)
        
    Returns:
        Confirmation message with file metadata
    """
    path = os.path.expanduser(path)
    abs_path = os.path.abspath(path)
    
    if not os.path.exists(abs_path):
        return f"Error: File {abs_path} not found"
    
    filename = os.path.basename(abs_path)
    session_id = get_session_id()
    
    line_start = line_start if line_start is not None else 0
    line_end_str = line_end if line_end is not None else "*"
    line_range = f"{line_start}-{line_end_str}"
    
    keywords = [
        session_id,
        "file",
        f"file:{filename}",
        f"file:{filename}:{line_range}"
    ]
    payload = {
        "content": f"open: {filename} [{line_range}]",
        "keywords": keywords,
        "properties": {
            "path": abs_path,
            "filename": filename,
            "line_start": str(line_start),
            "line_end": str(line_end) if line_end is not None else "*"
        }
    }
    
    try:
        url = f"{_get_memory_url()}/memories"
        resp = requests.post(url, json=payload, timeout=5)
        if resp.status_code != 200:
            return f"Error saving to memory: {resp.text[:200]}"
    except Exception as e:
        return f"Error saving to memory: {e}"
    
    try:
        with open(abs_path, 'r') as f:
            content = f.read()
        total_lines = len(content.splitlines())
    except Exception:
        total_lines = "?"
    
    file_type_str = _file_type(abs_path)
    line_info = ""
    if line_start > 0 or line_end is not None:
        line_info = f" (lines {line_start}-{line_end or 'end'})"
    
    large_warning = ""
    if total_lines != "?" and total_lines > 1000:
        large_warning = " [!LARGE FILE - consider using line_start/line_end to limit scope]"
    
    return f"Opened {filename} ({file_type_str}, {total_lines} lines){line_info}{large_warning}"


async def replace_text(
    path: str,
    old_text: str,
    new_text: str,
    threshold: float = 0.95,
    validate_syntax: bool = True
) -> str:
    """Replace text in a file using fuzzy matching (auto-saves).
    
    Uses atomic writes, syntax validation for Python files, and write verification.
    
    Args:
        path: Path to the file
        old_text: Text to find and replace
        new_text: Replacement text
        threshold: Minimum Jaro-Winkler similarity (0.0-1.0, default 0.95)
        validate_syntax: Whether to validate Python syntax after replacement (default: True)
        
    Returns:
        Confirmation message or error with best match info
    """
    path = os.path.expanduser(path)
    abs_path = os.path.abspath(path)
    
    try:
        with open(abs_path, 'r') as f:
            content = f.read()
        # Sanitize content for UTF-8 encoding edge cases
        content = _sanitize_content(content)
        lines = content.splitlines(keepends=True)
    except Exception as e:
        return f"Error reading {abs_path}: {e}"
    
    span, score = _find_best_window(lines, old_text, threshold=threshold)
    
    if not span:
        # Find best match even below threshold so we can show it
        best_span, best_score = _find_best_window(lines, old_text, threshold=0.0)
        if best_span:
            start, end = best_span
            matched_lines = lines[start:end]
            matched_text = ''.join(matched_lines).strip()
            return (
                f"Text not found (best match was {best_score:.0%} — below {threshold:.0%} threshold).\n\n"
                f"Best match found:\n{matched_text[:300]}\n\n"
                f"Tips:\n"
                f"- Try lowering threshold (e.g., threshold=0.75) if whitespace differs\n"
                f"- Make sure indentation and newlines match the file format\n"
                f"- The more text you provide, the better the fuzzy match"
            )
        return (
            f"Text not found.\n\n"
            f"Tips:\n"
            f"- Check for whitespace differences (spaces/tabs)\n"
            f"- Make sure newlines match the file format\n"
            f"- The more text you provide, the better the fuzzy match"
        )
    
    start, end = span
    
    new_lines = new_text.splitlines(keepends=True)
    if new_lines and not new_lines[-1].endswith('\n'):
        new_lines[-1] += '\n'
    lines[start:end] = new_lines
    new_content = ''.join(lines)
    
    # Validate Python syntax for .py files
    if validate_syntax and abs_path.endswith('.py'):
        is_valid, syntax_error = _validate_python(new_content)
        if not is_valid:
            return f"Error: Replacement would introduce syntax error: {syntax_error}"
    
    # Use atomic write to prevent partial writes
    try:
        _atomic_write(abs_path, new_content)
    except Exception as e:
        return f"Error saving {abs_path}: {e}"
    
    # Verify the write succeeded
    if not _verify_write(abs_path, new_content):
        return f"Replaced lines {start+1}-{end} but verification failed (content may differ)"
    
    return f"Replaced lines {start+1}-{end} (fuzzy match {score:.0%})"


async def preview_replace(path: str, old_text: str, threshold: float = 0.95) -> str:
    """Show the matched text window without modifying the file.
    
    Args:
        path: Path to the file
        old_text: Text to search for
        threshold: Minimum Jaro-Winkler similarity (0.0-1.0, default 0.95)
        
    Returns:
        Matched text window or not-found message
    """
    path = os.path.expanduser(path)
    abs_path = os.path.abspath(path)
    
    try:
        with open(abs_path, 'r') as f:
            content = f.read()
        lines = content.splitlines(keepends=True)
    except Exception as e:
        return f"Error reading {abs_path}: {e}"
    
    span, score = _find_best_window(lines, old_text, threshold=threshold)
    
    if not span:
        best_span, best_score = _find_best_window(lines, old_text, threshold=0.0)
        if best_span:
            start, end = best_span
            matched_text = ''.join(lines[start:end]).strip()
            return (
                f"No match above {threshold:.0%} threshold. "
                f"Best match ({best_score:.0%}) at lines {start+1}-{end}:\n"
                f"{matched_text[:300]}"
            )
        return f"Text not found in {os.path.basename(abs_path)}."
    
    start, end = span
    matched_text = ''.join(lines[start:end]).strip()
    return f"Match at lines {start+1}-{end} (similarity {score:.0%}):\n{matched_text}"


async def diff_text(
    path: str,
    old_text: str,
    new_text: str,
    threshold: float = 0.95
) -> str:
    """Show the unified diff of a proposed replacement without modifying.
    
    Args:
        path: Path to the file
        old_text: Text to find
        new_text: Replacement text
        threshold: Minimum Jaro-Winkler similarity (0.0-1.0, default 0.95)
        
    Returns:
        Unified diff output showing the proposed change
    """
    path = os.path.expanduser(path)
    abs_path = os.path.abspath(path)
    
    try:
        with open(abs_path, 'r') as f:
            content = f.read()
        content = _sanitize_content(content)
        lines = content.splitlines(keepends=True)
    except Exception as e:
        return f"Error reading {abs_path}: {e}"
    
    span, score = _find_best_window(lines, old_text, threshold=threshold)
    
    if not span:
        best_span, best_score = _find_best_window(lines, old_text, threshold=0.0)
        if best_span:
            start, end = best_span
            matched_text = ''.join(lines[start:end]).rstrip()
            return (
                f"Cannot diff — best match ({best_score:.0%}) is below {threshold:.0%} threshold.\n\n"
                f"Best match at lines {start+1}-{end}:\n{matched_text[:300]}\n\n"
                f"Try lowering threshold for this replacement."
            )
        return f"Cannot diff — text not found in {os.path.basename(abs_path)}."
    
    start, end = span
    before_lines = lines[start:end]
    
    new_lines = new_text.splitlines(keepends=True)
    if new_lines and not new_lines[-1].endswith('\n'):
        new_lines[-1] += '\n'
    after_lines = new_lines
    
    filename = os.path.basename(abs_path)
    
    # Generate unified diff
    diff = ''.join(difflib.unified_diff(
        before_lines,
        after_lines,
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}",
        lineterm='\n'
    ))
    
    return (
        f"=== diff: {filename} lines {start+1}-{end} (match {score:.0%}) ===\n"
        f"\n--- unified diff ---\n{diff}"
    )


def _generate_unified_diff(
    path: str,
    old_lines: list[str],
    new_lines: list[str],
    context: int = 3
) -> str:
    """Generate a unified diff between old and new content.
    
    Args:
        path: File path for the diff header
        old_lines: Original lines
        new_lines: New lines
        context: Number of context lines around changes
        
    Returns:
        Unified diff string
    """
    return ''.join(difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=f"a/{os.path.basename(path)}",
        tofile=f"b/{os.path.basename(path)}",
        n=context,
        lineterm='\n'
    ))


async def batch_edit(
    path: str,
    replacements: list[Replacement],
    threshold: float = 0.95
) -> EditResult:
    """Apply multiple replacements in a single atomic operation.
    
    More efficient than calling replace_text() multiple times as it only
    reads and writes the file once. All replacements must succeed for the
    file to be modified.
    
    Args:
        path: Path to the file
        replacements: List of Replacement dataclasses (old_str, new_str)
        threshold: Minimum Jaro-Winkler similarity (0.0-1.0, default 0.95)
        
    Returns:
        EditResult with success status, diff, and match info
    """
    path = os.path.expanduser(path)
    abs_path = os.path.abspath(path)
    
    try:
        with open(abs_path, 'r') as f:
            content = f.read()
        content = _sanitize_content(content)
    except Exception as e:
        return EditResult(
            success=False,
            path=abs_path,
            message=f"Error reading {abs_path}: {e}"
        )
    
    original_lines = content.splitlines(keepends=True)
    working_content = content
    
    # Apply each replacement
    changes: list[tuple[int, int, float]] = []
    
    for rep in replacements:
        lines = working_content.splitlines(keepends=True)
        span, score = _find_best_window(lines, rep.old_str, threshold=threshold)
        
        if not span:
            # Find best match even below threshold
            best_span, best_score = _find_best_window(lines, rep.old_str, threshold=0.0)
            if best_span:
                start, end = best_span
                matched_text = ''.join(lines[start:end]).strip()[:100]
                return EditResult(
                    success=False,
                    path=abs_path,
                    message=f"No match for: {rep.old_str[:50]}... (best: {best_score:.0%})",
                    similarity=best_score
                )
            return EditResult(
                success=False,
                path=abs_path,
                message=f"Text not found: {rep.old_str[:50]}..."
            )
        
        start, end = span
        changes.append((start, end, score))
        
        new_lines = rep.new_str.splitlines(keepends=True)
        if new_lines and not new_lines[-1].endswith('\n'):
            new_lines[-1] += '\n'
        
        lines[start:end] = new_lines
        working_content = ''.join(lines)
    
    # Validate Python syntax for .py files
    syntax_error = None
    if abs_path.endswith('.py'):
        is_valid, syntax_error = _validate_python(working_content)
        if not is_valid:
            return EditResult(
                success=False,
                path=abs_path,
                message=f"Syntax validation failed",
                similarity=changes[-1][2] if changes else None,
                syntax_error=syntax_error
            )
    
    # Generate diff
    new_lines = working_content.splitlines(keepends=True)
    diff = _generate_unified_diff(abs_path, original_lines, new_lines)
    
    # Atomic write
    try:
        _atomic_write(abs_path, working_content)
    except Exception as e:
        return EditResult(
            success=False,
            path=abs_path,
            message=f"Failed to write: {e}",
            similarity=changes[-1][2] if changes else None
        )
    
    # Verify write
    if not _verify_write(abs_path, working_content):
        return EditResult(
            success=True,
            path=abs_path,
            message=f"Wrote file but verification failed",
            changed=True,
            diff=diff,
            similarity=changes[-1][2] if changes else None
        )
    
    return EditResult(
        success=True,
        path=abs_path,
        message=f"Applied {len(replacements)} replacement(s)",
        changed=True,
        diff=diff,
        line_start=changes[0][0] + 1 if changes else None,
        line_end=changes[-1][1] + 1 if changes else None,
        similarity=changes[-1][2] if changes else None
    )


async def delete_snippet(path: str, snippet: str, threshold: float = 0.95) -> EditResult:
    """Delete the first occurrence of a snippet from a file.
    
    Uses atomic write and returns a structured EditResult.
    
    Args:
        path: Path to the file
        snippet: Text to find and delete
        threshold: Minimum Jaro-Winkler similarity (0.0-1.0, default 0.95)
        
    Returns:
        EditResult with success status and diff
    """
    path = os.path.expanduser(path)
    abs_path = os.path.abspath(path)
    
    try:
        with open(abs_path, 'r') as f:
            content = f.read()
        content = _sanitize_content(content)
    except Exception as e:
        return EditResult(
            success=False,
            path=abs_path,
            message=f"Error reading {abs_path}: {e}"
        )
    
    lines = content.splitlines(keepends=True)
    span, score = _find_best_window(lines, snippet, threshold=threshold)
    
    if not span:
        best_span, best_score = _find_best_window(lines, snippet, threshold=0.0)
        if best_span:
            start, end = best_span
            matched_text = ''.join(lines[start:end]).strip()[:100]
            return EditResult(
                success=False,
                path=abs_path,
                message=f"Snippet not found (best: {best_score:.0%})",
                similarity=best_score
            )
        return EditResult(
            success=False,
            path=abs_path,
            message="Snippet not found in file"
        )
    
    start, end = span
    original_lines = lines[:]
    del lines[start:end]
    new_content = ''.join(lines)
    
    # Generate diff
    diff = _generate_unified_diff(abs_path, original_lines, lines)
    
    # Atomic write
    try:
        _atomic_write(abs_path, new_content)
    except Exception as e:
        return EditResult(
            success=False,
            path=abs_path,
            message=f"Failed to write: {e}"
        )
    
    # Verify write
    if not _verify_write(abs_path, new_content):
        return EditResult(
            success=True,
            path=abs_path,
            message="Deleted but verification failed",
            changed=True,
            diff=diff,
            similarity=score
        )
    
    return EditResult(
        success=True,
        path=abs_path,
        message="Snippet deleted",
        changed=True,
        diff=diff,
        line_start=start + 1,
        line_end=end,
        similarity=score
    )


async def delete_file(path: str) -> EditResult:
    """Delete a file permanently.
    
    Shows what was deleted via unified diff. Uses atomic delete.
    
    Args:
        path: Path to the file to delete
        
    Returns:
        EditResult with success status and diff showing deleted content
    """
    path = os.path.expanduser(path)
    abs_path = os.path.abspath(path)
    
    if not os.path.exists(abs_path):
        return EditResult(
            success=False,
            path=abs_path,
            message=f"File not found: {abs_path}"
        )
    
    if not os.path.isfile(abs_path):
        return EditResult(
            success=False,
            path=abs_path,
            message=f"Not a file: {abs_path}"
        )
    
    # Read content for diff before deleting
    try:
        with open(abs_path, 'r') as f:
            content = f.read()
        original_lines = content.splitlines(keepends=True)
    except Exception as e:
        return EditResult(
            success=False,
            path=abs_path,
            message=f"Error reading {abs_path}: {e}"
        )
    
    # Generate diff showing what was deleted
    diff = _generate_unified_diff(abs_path, original_lines, [])
    
    # Delete the file
    try:
        os.remove(abs_path)
    except Exception as e:
        return EditResult(
            success=False,
            path=abs_path,
            message=f"Failed to delete {abs_path}: {e}"
        )
    
    # Verify deletion
    if os.path.exists(abs_path):
        return EditResult(
            success=False,
            path=abs_path,
            message="File still exists after deletion"
        )
    
    return EditResult(
        success=True,
        path=abs_path,
        message=f"Deleted {os.path.basename(abs_path)}",
        changed=True,
        diff=diff
    )


async def close_file(filename: str, line_start: int = None, line_end: int = None) -> str:
    """Close a file by removing its record from memory DB.
    
    Args:
        filename: Filename to close (can be full path or just name)
        line_start: Optional. Close only this specific range.
        line_end: Optional. Close only this specific range.
        
    Returns:
        Confirmation message
    """
    name = os.path.basename(filename)
    session_id = get_session_id()
    
    if line_start is not None or line_end is not None:
        ls = line_start if line_start is not None else 0
        le = line_end if line_end is not None else "*"
        range_key = f"file:{name}:{ls}-{le}"
        query = f"k:{range_key}"
        memories = _search_memories(session_id, query, limit=10)
    else:
        query = f"k:file:{name}"
        memories = _search_memories(session_id, query, limit=10)
    
    if memories:
        count = 0
        for mem in memories:
            _delete_memory(mem['id'])
            count += 1
        range_desc = f" [{line_start or 0}-{line_end or '*'}]" if line_start is not None or line_end is not None else ""
        return f"Closed {name}{range_desc} ({count} range{'s' if count > 1 else ''})"
    
    return f"File {name} not open"


async def close_all_files() -> str:
    """Close all open files for this session.
    
    Returns:
        Confirmation message with count
    """
    session_id = get_session_id()
    memories = _search_memories(session_id, "k:file", limit=100)
    
    count = 0
    for mem in memories:
        _delete_memory(mem['id'])
        count += 1
    
    return f"Closed {count} open files"


async def pwd() -> str:
    """Print working directory — shows the current directory for this session.

    Returns:
        Current working directory path
    """
    return _get_cwd()


async def chdir(path: str) -> str:
    """Change the working directory for this session.

    Args:
        path: New directory path (absolute or relative)

    Returns:
        Confirmation message with the new directory

    Raises:
        FileNotFoundError: If the path does not exist
        NotADirectoryError: If the path exists but is not a directory
    """
    path = os.path.expanduser(path)
    abs_path = os.path.abspath(path)

    if not os.path.exists(abs_path):
        raise FileNotFoundError(f"Directory does not exist: {abs_path}")
    if not os.path.isdir(abs_path):
        raise NotADirectoryError(f"Not a directory: {abs_path}")

    session_id = get_session_id()
    _set_memory(
        session_id,
        "cwd",
        f"cwd: {abs_path}",
        {"path": abs_path}
    )

    return abs_path


async def file_info(path: str) -> str:
    """Get file metadata without loading content.
    
    Args:
        path: Path to the file
        
    Returns:
        Formatted file metadata
    """
    path = os.path.expanduser(path)
    abs_path = os.path.abspath(path)
    
    if not os.path.exists(abs_path):
        return f"Error: File {abs_path} not found"
    
    stat = os.stat(abs_path)
    
    try:
        with open(abs_path, 'r') as f:
            content = f.read()
        line_count = len(content.splitlines())
        token_count = _count_tokens(content)
    except Exception:
        line_count = 0
        token_count = 0
    
    file_type_str = _file_type(abs_path)
    
    return (
        f"File: {os.path.basename(abs_path)}\n"
        f"Type: {file_type_str}\n"
        f"Lines: {line_count}\n"
        f"Tokens: ~{token_count:,}\n"
        f"Size: {stat.st_size:,} bytes\n"
        f"Modified: {datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')}"
    )


async def search_files(pattern: str, path: str = None) -> str:
    """Grep pattern across files under a directory.
    
    Args:
        pattern: Regex pattern to search for
        path: Directory to search under (default: cwd)
        
    Returns:
        Formatted list of matches (file:line:content)
    """
    search_path = os.path.expanduser(path) if path else _get_cwd()
    
    if not os.path.exists(search_path):
        return f"Path not found: {search_path}"
    
    try:
        result = subprocess.run(
            ['rg', '--line-number', '--color=never', pattern, search_path],
            capture_output=True,
            text=True,
            timeout=10
        )
        output = result.stdout.strip()
    except FileNotFoundError:
        return "[ERROR] ripgrep (rg) not installed. Install ripgrep to use search_files."
    except subprocess.TimeoutExpired:
        return "[ERROR] Search timed out after 10 seconds."
    except Exception as e:
        return f"[ERROR] Search failed: {e}"
    
    if not output:
        return f"No matches for '{pattern}' under {search_path}"
    
    lines = output.splitlines()
    # ripgrep outputs: file:line:content — format nicely
    formatted = [f"=== Search: '{pattern}' ==="]
    for line in lines[:50]:  # cap at 50 matches
        formatted.append(line)
    
    if len(lines) > 50:
        formatted.append(f"... and {len(lines) - 50} more matches")
    
    return "\n".join(formatted)


async def write_text(path: str, content: str) -> str:
    """Write content to a file, creating it if needed.
    
    Args:
        path: Path to the file to write
        content: Content to write to the file
        
    Returns:
        Confirmation message with file info
    """
    path = os.path.expanduser(path)
    abs_path = os.path.abspath(path)
    
    try:
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, 'w') as f:
            f.write(content)
    except Exception as e:
        return f"Error writing {abs_path}: {e}"
    
    try:
        stat = os.stat(abs_path)
        line_count = len(content.splitlines())
        token_count = _count_tokens(content)
        return f"Wrote {os.path.basename(abs_path)} ({line_count} lines, ~{token_count:,} tokens)"
    except Exception:
        return f"Wrote {abs_path}"


async def list_dir(path: str = None) -> str:
    """List directory contents (files and subdirectories).
    
    Args:
        path: Directory to list (default: cwd)
        
    Returns:
        Formatted directory listing
    """
    dir_path = os.path.expanduser(path) if path else _get_cwd()
    
    if not os.path.exists(dir_path):
        return f"Directory not found: {dir_path}"
    
    if not os.path.isdir(dir_path):
        return f"Not a directory: {dir_path}"
    
    try:
        entries = os.listdir(dir_path)
    except PermissionError:
        return f"Permission denied: {dir_path}"
    
    dirs = []
    files = []
    for entry in entries:
        full_path = os.path.join(dir_path, entry)
        if os.path.isdir(full_path):
            dirs.append(entry + '/')
        else:
            files.append(entry)
    
    dirs.sort()
    files.sort()
    
    lines = [f"=== {dir_path} ==="]
    if dirs:
        lines.append("dirs:")
        lines.extend(f"  {d}" for d in dirs)
    if files:
        lines.append("files:")
        lines.extend(f"  {f}" for f in files)
    
    if not dirs and not files:
        lines.append("  (empty)")
    
    return "\n".join(lines)


def get_module():
    """Get the file module."""
    return Module(
        name="file",
        called_fns=[
            CalledFn(
                name="open_file",
                description="Open a file and add it to the file context. Returns file type and line count. Large files (>1000 lines) include a warning.\n\nArgs:\n- path: Path to the file to open\n- line_start: Start line for partial opening (0-indexed)\n- line_end: End line for partial opening",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to the file to open"
                        },
                        "line_start": {
                            "type": "integer",
                            "description": "Start line for partial opening (0-indexed, default: 0)"
                        },
                        "line_end": {
                            "type": "integer",
                            "description": "End line for partial opening (default: None = to end)"
                        }
                    },
                    "required": ["path"]
                },
                fn=open_file,
            ),
            CalledFn(
                name="replace_text",
                description="Replace text in an open file using fuzzy matching. Auto-saves the file. Validates Python syntax by default.\n\nArgs:\n- path: Path to the file\n- old_text: Text to find and replace (fuzzy matched)\n- new_text: Replacement text\n- threshold: Minimum Jaro-Winkler similarity (0.0-1.0, default: 0.95)\n- validate_syntax: Whether to validate Python syntax after replacement (default: True)",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to the file"
                        },
                        "old_text": {
                            "type": "string",
                            "description": "Text to find and replace (fuzzy matched)"
                        },
                        "new_text": {
                            "type": "string",
                            "description": "Replacement text"
                        },
                        "threshold": {
                            "type": "number",
                            "description": "Minimum Jaro-Winkler similarity (0.0-1.0, default: 0.95). Lower to allow matches with whitespace differences."
                        },
                        "validate_syntax": {
                            "type": "boolean",
                            "description": "Whether to validate Python syntax after replacement (default: True)"
                        }
                    },
                    "required": ["path", "old_text", "new_text"]
                },
                fn=replace_text,
            ),
            CalledFn(
                name="preview_replace",
                description="Show the matched text window without modifying the file. Use to verify the right location before committing to replace_text.\n\nArgs:\n- path: Path to the file\n- old_text: Text to search for\n- threshold: Minimum Jaro-Winkler similarity (0.0-1.0, default: 0.95)",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to the file"
                        },
                        "old_text": {
                            "type": "string",
                            "description": "Text to search for"
                        },
                        "threshold": {
                            "type": "number",
                            "description": "Minimum Jaro-Winkler similarity (0.0-1.0, default: 0.95)"
                        }
                    },
                    "required": ["path", "old_text"]
                },
                fn=preview_replace,
            ),
            CalledFn(
                name="diff_text",
                description="Show the before/after of a proposed replacement without modifying the file. Use to preview a full change before applying it.\n\nArgs:\n- path: Path to the file\n- old_text: Text to find\n- new_text: Replacement text\n- threshold: Minimum Jaro-Winkler similarity (0.0-1.0, default: 0.95)",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to the file"
                        },
                        "old_text": {
                            "type": "string",
                            "description": "Text to find"
                        },
                        "new_text": {
                            "type": "string",
                            "description": "Replacement text"
                        },
                        "threshold": {
                            "type": "number",
                            "description": "Minimum Jaro-Winkler similarity (0.0-1.0, default: 0.95)"
                        }
                    },
                    "required": ["path", "old_text", "new_text"]
                },
                fn=diff_text,
            ),
            CalledFn(
                name="close_file",
                description="Close a file by removing it from the file context.",
                parameters={
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "Filename to close (can be full path or just name)"
                        },
                        "line_start": {
                            "type": "integer",
                            "description": "Optional. Close only this specific range."
                        },
                        "line_end": {
                            "type": "integer",
                            "description": "Optional. Close only this specific range."
                        }
                    },
                    "required": ["filename"]
                },
                fn=close_file,
            ),
            CalledFn(
                name="close_all_files",
                description="Close all open files for this session. Use to clean up context.",
                parameters={
                    "type": "object",
                    "properties": {},
                    "required": []
                },
                fn=close_all_files,
            ),
            CalledFn(
                name="pwd",
                description="Print working directory — shows the current directory for this session.\n\nThe cwd is session-specific and persists across calls.",
                parameters={
                    "type": "object",
                    "properties": {},
                    "required": []
                },
                fn=pwd,
            ),
            CalledFn(
                name="chdir",
                description="Change the working directory for this session.\n\nArgs:\n- path: New directory path (absolute or relative). Supports ~ expansion.",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "New directory path (absolute or relative). Supports ~ expansion."
                        }
                    },
                    "required": ["path"]
                },
                fn=chdir,
            ),
            CalledFn(
                name="file_info",
                description="Get file metadata (type, line count, size, modified date) without loading content.",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to the file"
                        }
                    },
                    "required": ["path"]
                },
                fn=file_info,
            ),
            CalledFn(
                name="search_files",
                description="Grep pattern across files under a directory using ripgrep (rg). Returns file:line:content for each match, capped at 50 results.\n\nArgs:\n- pattern: Regex pattern to search for\n- path: Directory to search under (default: cwd)",
                parameters={
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "description": "Regex pattern to search for"
                        },
                        "path": {
                            "type": "string",
                            "description": "Directory to search under (default: cwd)"
                        }
                    },
                    "required": ["pattern"]
                },
                fn=search_files,
            ),
            CalledFn(
                name="list_dir",
                description="List directory contents (files and subdirectories).\n\nArgs:\n- path: Directory to list (default: cwd)",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Directory to list (default: cwd)"
                        }
                    },
                    "required": []
                },
                fn=list_dir,
            ),
            CalledFn(
                name="write_text",
                description="Write content to a file, creating it if needed.\n\nArgs:\n- path: Path to the file to write\n- content: Content to write",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to the file to write"
                        },
                        "content": {
                            "type": "string",
                            "description": "Content to write to the file"
                        }
                    },
                    "required": ["path", "content"]
                },
                fn=write_text,
            ),
            CalledFn(
                name="batch_edit",
                description="Apply multiple text replacements in a single atomic operation. More efficient than calling replace_text() multiple times.\n\nArgs:\n- path: Path to the file\n- replacements: List of {old_str, new_str} pairs\n- threshold: Minimum Jaro-Winkler similarity (default: 0.95)",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to the file"
                        },
                        "replacements": {
                            "type": "array",
                            "description": "List of {old_str, new_str} replacement pairs"
                        },
                        "threshold": {
                            "type": "number",
                            "description": "Minimum Jaro-Winkler similarity (0.0-1.0, default: 0.95)"
                        }
                    },
                    "required": ["path", "replacements"]
                },
                fn=batch_edit,
            ),
            CalledFn(
                name="delete_snippet",
                description="Delete the first occurrence of a snippet from a file using fuzzy matching.\n\nArgs:\n- path: Path to the file\n- snippet: Text to find and delete\n- threshold: Minimum Jaro-Winkler similarity (default: 0.95)",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to the file"
                        },
                        "snippet": {
                            "type": "string",
                            "description": "Text to find and delete"
                        },
                        "threshold": {
                            "type": "number",
                            "description": "Minimum Jaro-Winkler similarity (0.0-1.0, default: 0.95)"
                        }
                    },
                    "required": ["path", "snippet"]
                },
                fn=delete_snippet,
            ),
            CalledFn(
                name="delete_file",
                description="Delete a file permanently. Shows unified diff of deleted content.\n\nArgs:\n- path: Path to the file to delete",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to the file to delete"
                        }
                    },
                    "required": ["path"]
                },
                fn=delete_file,
            ),
        ],
        context_fns=[
            ContextFn(tag="file_help", fn=_file_help, static=True),
            ContextFn(tag="file", fn=_file_context),
        ],
    )
