# Riven File Tool Evolution Plan

## Overview

This document outlines the evolution of Riven's file editing tools from good to great.
We analyze both Riven's existing implementation and Code Puppy's approach, stealing the best ideas
from each while keeping Riven's superior fuzzy matching.

**Goal:** Build the most robust, developer-friendly file editing tool possible.

---

## Phase 1: Core Improvements

| # | Change | Source | Priority | Impact | Effort | Status |
|---|--------|--------|----------|--------|--------|--------|
| 1.1 | Add `threshold` parameter to `_find_best_window()` | Internal | 🔴 High | Fail fast, configurable strictness | ⭐ Low | ✅ DONE |
| 1.2 | Add `.rstrip('\n')` before Jaro-Winkler comparison | Internal | 🔴 High | Fix subtle matching bugs | ⭐ Low | ✅ DONE |
| 1.3 | Create `EditResult` dataclass for structured responses | Code Puppy | 🔴 High | Machine-readable, better for agents | ⭐ Low | ✅ DONE |
| 1.4 | Create `Replacement` dataclass for batch operations | Code Puppy | 🟡 Med | Foundation for batch edits | ⭐ Low | ✅ DONE |

### Details

#### 1.1: Threshold Parameter

**Status:** ✅ Already implemented in `modules/file.py`

```python
def _find_best_window(
    haystack_lines: list[str],
    needle: str,
    threshold: float = 0.95,
) -> tuple[tuple[int, int] | None, float]:
    # Check threshold inside for early exit
    if best_score >= threshold:
        return best_span, best_score
    return None, best_score
```

#### 1.2: Trailing Newline Cleanup

**Status:** ✅ Already implemented in `modules/file.py`

```python
window_clean = window.rstrip('\n')
score = jellyfish.jaro_winkler_similarity(window_clean, needle)
```

#### 1.3: EditResult Dataclass

**Status:** 🔄 In Progress

```python
@dataclass
class EditResult:
    """Structured result for file edit operations."""
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
        """Convert to user-friendly string."""
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
            if self.syntax_error:
                parts.append(f"   Syntax error: {self.syntax_error}")
            if self.diff:
                parts.append(f"\n{self.diff}")
            return "\n".join(parts)
```

#### 1.4: Replacement Dataclass

**Status:** ⏳ TODO

```python
@dataclass
class Replacement:
    """A single text replacement for batch operations."""
    old_str: str
    new_str: str
```

---

## Phase 2: Robustness Features

| # | Change | Source | Priority | Impact | Effort | Files |
|---|--------|--------|----------|--------|--------|-------|
| 2.1 | Atomic writes (temp file + rename) | Code Puppy | 🔴 High | Prevent partial writes | ⭐ Low | `modules/file_editor.py` (new) |
| 2.2 | Verify-after-write | Code Puppy | 🟡 Med | Catch disk/memory mismatches | ⭐ Low | `modules/file_editor.py` (new) |
| 2.3 | Surrogate character sanitization | Code Puppy | 🟡 Med | Handle encoding edge cases | ⭐ Low | `modules/file_editor.py` (new) |
| 2.4 | Syntax validation for `.py` files | New | 🟡 Med | Catch broken Python before saving | ⭐⭐ Med | `modules/file_editor.py` (new) |

### Details

#### 2.1: Atomic Write

```python
def _atomic_write(path: str, content: str) -> None:
    """Write content atomically using temp file + rename.
    
    Prevents partial writes if process is interrupted mid-write.
    """
    dir_path = os.path.dirname(path) or '.'
    fd, temp_path = tempfile.mkstemp(dir=dir_path, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(content)
        os.replace(temp_path, path)  # Atomic on POSIX
    except Exception:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise
```

#### 2.4: Syntax Validation

```python
def _validate_python(content: str) -> tuple[bool, str | None]:
    """Validate Python syntax. Returns (is_valid, error_message)."""
    try:
        ast.parse(content)
        return True, None
    except SyntaxError as e:
        return False, f"Syntax error at line {e.lineno}: {e.msg}"
```

---

## Phase 3: Batch Operations

| # | Change | Source | Priority | Impact | Effort | Files |
|---|--------|--------|----------|--------|--------|-------|
| 3.1 | `batch_edit()` function | Code Puppy | 🔴 High | One disk trip vs N | ⭐⭐ Med | `modules/file_editor.py` (new) |
| 3.2 | `single_edit()` wrapper | New | 🟡 Med | Backward compatible | ⭐ Low | `modules/file_editor.py` (new) |
| 3.3 | Rollback on batch failure | New | 🟡 Med | All-or-nothing edits | ⭐⭐ Med | `modules/file_editor.py` (new) |
| 3.4 | Conflict detection for overlapping replacements | New | 🟡 Med | Prevent self-overwrites | ⭐⭐ Med | `modules/file_editor.py` (new) |
| 3.5 | `delete_snippet()` function | Code Puppy | 🟡 Med | Remove content | ⭐ Low | `modules/file_editor.py` (new) |

### Details

#### 3.1: Batch Edit Flow

```python
def batch_edit(
    file_path: str,
    replacements: list[Replacement],
    threshold: float = 0.95,
) -> EditResult:
    """Apply multiple replacements in single pass (atomic)."""
    # 1. Read file once
    # 2. Apply all replacements in memory
    # 3. Validate syntax if .py
    # 4. Write once (atomic)
    # 5. Verify write
    # 6. Store session in MemoryDB
    # 7. Return structured EditResult
```

---

## Phase 4: Developer Experience

| # | Change | Source | Priority | Impact | Effort | Files |
|---|--------|--------|----------|--------|--------|-------|
| 4.1 | Unified diff output on every operation | Code Puppy | 🔴 High | Better debugging | ⭐ Low | `modules/file_editor.py` (new) |
| 4.2 | `preview_edit()` with configurable threshold | Internal | 🟡 Med | Consistent API | ⭐ Low | `modules/file_editor.py` (new) |
| 4.3 | `diff_edit()` with unified diff output | Internal | 🟡 Med | Better before/after | ⭐ Low | `modules/file_editor.py` (new) |
| 4.4 | Best-match shown in error messages | Internal | 🟡 Med | Helpful errors | ⭐ Low | `modules/file_editor.py` (new) |
| 4.5 | Tips in error messages | Internal | 🟡 Med | User guidance | ⭐ Low | `modules/file_editor.py` (new) |

### Details

#### 4.4: Helpful Error Messages

```python
# BEFORE (unhelpful):
return {"error": "No suitable match in file (JW < 0.95)"}

# AFTER (helpful):
best_span, best_score = _find_best_window(orig_lines, old_snippet, threshold=0.0)
if best_span:
    matched_text = ''.join(orig_lines[best_span[0]:best_span[1]]).strip()
    return EditResult(
        success=False,
        message=f"Text not found (best match was {best_score:.0%}).\n"
                f"\nBest match:\n{matched_text[:300]}\n\n"
                f"Tips:\n"
                f"- Try lowering threshold if whitespace differs\n"
                f"- Make sure indentation matches the file format",
        similarity=best_score,
    )
```

---

## Phase 5: MemoryDB Integration

| # | Change | Source | Priority | Impact | Effort | Files |
|---|--------|--------|----------|--------|--------|-------|
| 5.1 | `FileEditSession` dataclass | New | 🔴 High | Track edit sessions | ⭐ Low | `modules/file_editor.py` (new) |
| 5.2 | `FileSnapshot` dataclass | New | 🔴 High | Enable undo/redo | ⭐ Low | `modules/file_editor.py` (new) |
| 5.3 | MemoryDB API extensions for file sessions | New | 🔴 High | Persistence layer | ⭐⭐ Med | `context.py` |
| 5.4 | Store sessions on each edit | New | 🔴 High | Build audit trail | ⭐ Low | `modules/file_editor.py` (new) |
| 5.5 | `undo_session()` function | New | 🟡 Med | Undo changes | ⭐⭐ Med | `modules/file_editor.py` (new) |
| 5.6 | Operation history query | New | 🟡 Med | "What changed?" | ⭐⭐ Med | `modules/file_editor.py` (new) |

### Details

#### 5.1: FileEditSession

```python
@dataclass
class FileEditSession:
    """A session of related file edits, persisted in MemoryDB."""
    session_id: str              # UUID, e.g., "edit_abc123"
    tool_name: str               # "batch_edit", "single_edit", etc.
    files: list[str]             # Files modified in this session
    operations: int              # Number of operations
    created_at: datetime
    status: str                  # "pending", "completed", "failed", "rolled_back"
    diff: str                    # Unified diff of all changes
    original_snapshots: dict     # path -> original content (for undo)
    modified_snapshots: dict     # path -> new content
```

#### 5.2: FileSnapshot

```python
@dataclass  
class FileSnapshot:
    """A point-in-time snapshot of a file for undo/redo."""
    snapshot_id: str
    file_path: str
    content: str
    session_id: str              # Link to the edit session
    operation_index: int         # Order within session
    created_at: datetime
    checksum: str                # SHA256 of content for verification
```

#### 5.3: MemoryDB API Extensions

```python
# In context.py - extend MemoryClient:

class MemoryClient:
    # ... existing methods ...
    
    def add_file_session(self, session: FileEditSession) -> dict:
        """Store a file edit session."""
        resp = requests.post(f"{self.base_url}/file-sessions", json={
            "session_id": session.session_id,
            "tool_name": session.tool_name,
            "files": session.files,
            "operations": session.operations,
            "created_at": session.created_at.isoformat(),
            "status": session.status,
            "diff": session.diff,
            "original_snapshots": session.original_snapshots,
            "modified_snapshots": session.modified_snapshots,
        })
        resp.raise_for_status()
        return resp.json()
    
    def get_file_session(self, session_id: str) -> FileEditSession:
        """Get a specific file edit session."""
        resp = requests.get(f"{self.base_url}/file-sessions/{session_id}")
        resp.raise_for_status()
        return FileEditSession(**resp.json())
    
    def get_file_sessions(self, path: str = None, limit: int = 10) -> list[FileEditSession]:
        """Get recent sessions, optionally filtered by file."""
        params = {"limit": limit}
        if path:
            params["path"] = path
        resp = requests.get(f"{self.base_url}/file-sessions", params=params)
        resp.raise_for_status()
        return [FileEditSession(**s) for s in resp.json().get("sessions", [])]
    
    def get_file_history(self, path: str, limit: int = 20) -> list[dict]:
        """Get change history for a specific file."""
        resp = requests.get(f"{self.base_url}/file-history", 
                           params={"path": path, "limit": limit})
        resp.raise_for_status()
        return resp.json().get("history", [])
    
    def undo_session(self, session_id: str) -> dict:
        """Undo all changes from a session."""
        resp = requests.post(f"{self.base_url}/file-sessions/{session_id}/undo")
        resp.raise_for_status()
        return resp.json()
```

---

## Visual Roadmap

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              RIVEN FILE TOOL ROADMAP                                │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  PHASE 1: Core          PHASE 2: Robustness     PHASE 3: Batch                      │
│  ┌───────────────┐      ┌───────────────┐       ┌───────────────┐                   │
│  │ ✓ threshold   │      │ ✓ Atomic Write│       │ ✓ batch_edit()│                   │
│  │   param       │      │ ✓ Verify      │       │ ✓ single_edit │                   │
│  │ ✓ .rstrip()   │      │ ✓ Surrogate   │       │ ✓ Rollback    │                   │
│  │ ✓ EditResult  │      │   sanitize    │       │ ✓ Conflict    │                   │
│  │ ✓ Replacement │      │ ✓ Syntax      │       │   detection   │                   │
│  └───────────────┘      │   validation  │       │ ✓ delete_     │                   │
│                         └───────────────┘       │   snippet     │                   │
│                                                 └───────────────┘                   │
│  PHASE 4: DX                                                             PHASE 5: MemoryDB
│  ┌───────────────┐                                                      ┌────────────────┐
│  │ ✓ Unified diff│                                                      │ ✓ FileEditSession│
│  │ ✓ preview_    │                                                      │ ✓ FileSnapshot  │
│  │   edit        │                                                      │ ✓ MemoryDB API  │
│  │ ✓ diff_edit() │                                                      │ ✓ Store sessions│
│  │ ✓ Best-match  │                                                      │ ✓ undo_session()│
│  │   errors      │                                                      │ ✓ History query │
│  │ ✓ Tips in     │                                                      └────────────────┘
│  │   errors      │                                                             │
│  └───────────────┘                                                             │
│                                                                                     │
│  Effort: ⭐ = Low    ⭐⭐ = Medium    ⭐⭐⭐ = High                               │
│  Priority: 🔴 High   🟡 Medium   🟠 Low                                          │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Implementation Order

| Order | Item | Phase | Rationale |
|-------|------|-------|-----------|
| 1 | `_find_best_window` threshold param | 1 | Foundation for everything else |
| 2 | `.rstrip('\n')` before comparison | 1 | Bug fix, immediate improvement |
| 3 | `EditResult` and `Replacement` dataclasses | 1 | Foundation for structured responses |
| 4 | `_atomic_write()` helper | 2 | Safety, prevents data loss |
| 5 | Unified diff output | 4 | Better UX, audit trails |
| 6 | `batch_edit()` function | 3 | Efficiency for LLM-generated edits |
| 7 | `preview_edit()` / `diff_edit()` | 4 | DX improvements |
| 8 | Syntax validation for `.py` | 2 | Quality gate |
| 9 | Verify-after-write | 2 | Catch edge cases |
| 10 | Surrogate sanitization | 2 | Encoding edge cases |
| 11 | `FileEditSession` / `FileSnapshot` | 5 | MemoryDB persistence |
| 12 | MemoryDB API extensions | 5 | Persistence layer |
| 13 | Store sessions on edit | 5 | Build audit trail |
| 14 | Best-match / Tips in errors | 4 | User guidance |
| 15 | Rollback on failure | 3 | All-or-nothing |
| 16 | Conflict detection | 3 | Prevent self-overwrites |
| 17 | `undo_session()` function | 5 | Undo support |
| 18 | Operation history query | 5 | "What changed?" queries |

---

## File Structure

```
riven/
├── modules/
│   ├── file.py           # Keep as-is (fuzzy matching is superior)
│   ├── file_editor.py    # NEW: Robust editor with all improvements
│   └── __init__.py       # Export new functions
├── context.py            # Add MemoryDB API extensions
├── tests/
│   └── test_file_editor.py  # NEW: Tests for new functionality
└── docs/
    └── file_tool_workplan.md  # This file
```

---

## Checklist

### Phase 1: Core
- [x] Add `threshold` parameter to `_find_best_window()` in `modules/file.py`
- [x] Add `.rstrip('\n')` before comparison in `_find_best_window()`
- [x] Create `EditResult` dataclass in `modules/file.py`
- [x] Create `Replacement` dataclass in `modules/file.py`
- [x] Create `FileEditSession` dataclass in `modules/file.py`

### Phase 2: Robustness
- [ ] Create `_atomic_write()` helper in `modules/file_editor.py`
- [ ] Create `_validate_python()` helper in `modules/file_editor.py`
- [ ] Create `_verify_write()` helper in `modules/file_editor.py`
- [ ] Add surrogate sanitization in read/write operations

### Phase 3: Batch Operations
- [ ] Create `batch_edit()` function in `modules/file_editor.py`
- [ ] Create `single_edit()` wrapper in `modules/file_editor.py`
- [ ] Create `delete_snippet()` function in `modules/file_editor.py`
- [ ] Implement rollback logic for batch failures
- [ ] Implement conflict detection for overlapping replacements

### Phase 4: Developer Experience
- [ ] Create `_generate_diff()` helper in `modules/file_editor.py`
- [ ] Update all functions to output unified diff
- [ ] Update `preview_edit()` with configurable threshold
- [ ] Update `diff_edit()` with unified diff output
- [ ] Add best-match to error messages
- [ ] Add tips to error messages

### Phase 5: MemoryDB Integration
- [ ] Create `FileEditSession` dataclass in `modules/file_editor.py`
- [ ] Create `FileSnapshot` dataclass in `modules/file_editor.py`
- [ ] Add file session methods to `MemoryClient` in `context.py`
- [ ] Store sessions on each successful edit
- [ ] Create `undo_session()` function in `modules/file_editor.py`
- [ ] Create `get_file_history()` function in `modules/file_editor.py`
- [ ] Add MemoryDB API routes (backend)

### Module Exports
- [ ] Update `modules/__init__.py` to export new functions

### Testing
- [ ] Add tests for `_find_best_window` threshold parameter
- [ ] Add tests for atomic write
- [ ] Add tests for batch edit
- [ ] Add tests for syntax validation
- [ ] Add tests for MemoryDB integration (mocked)

---

## References

- **Riven file.py:** `/home/david/Projects/riven/modules/file.py`
- **Code Puppy file_modifications.py:** `/home/david/Projects/code_puppy/code_puppy/tools/file_modifications.py`
- **Code Puppy common.py:** `/home/david/Projects/code_puppy/code_puppy/tools/common.py`
- **Comparison doc:** `/home/david/Projects/riven/docs/file_tool_modifications.md`

---

## Status

- [ ] Phase 1 Complete
  - [x] 1.1 Add threshold parameter to _find_best_window
  - [x] 1.2 Add .rstrip('\n') before comparison
  - [x] 1.3 Create EditResult dataclass
  - [x] 1.4 Create Replacement dataclass
- [ ] Phase 2 Complete
- [ ] Phase 3 Complete
- [ ] Phase 4 Complete
- [ ] Phase 5 Complete

---

*Last updated: Generated from file_tool_modifications.md comparison*
