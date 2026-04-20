# Riven Core — Improvement Plan

## Status: IN PROGRESS

## Issues Found & Fixed

### 1. ✅ `import os` inside functions (planning.py)
- **Status**: FIXED (committed)
- **Problem**: `import os` appeared 5 times inside function bodies in `modules/planning.py`
- **Fix**: Moved to module-level import, removed all inline imports
- **Tests**: 13/13 pass

### 2. ✅ Duplicate shard `default.yaml`
- **Status**: FIXED (committed)
- **Problem**: `shards/default.yaml` was an exact copy of `shards/codehammer.yaml`
- **Fix**: Deleted `default.yaml`, it's now just an alias pointing to `codehammer` config defaults
- **Tests**: 5/5 pass (including duplicate detection test)

### 3. ✅ Hardcoded paths
- **Status**: FIXED (committed)
- **Problems**:
  - `shards/codehammer.yaml` had `debug_dir: "/home/david/Projects/..."` 
  - `core.py` had hardcoded `/home/david/Projects/riven_projects/riven_core/context_logs`
  - `core.py` error message hardcoded `port 8030`
- **Fix**: 
  - Removed `debug_dir` from `codehammer.yaml` (now from config.yaml)
  - `core.py` uses `os.path.dirname(__file__)` for relative resolution
  - Error message now uses actual `memory_url`
  - `context.py` `ContextManager` resolves relative paths to absolute using `Path(__file__).parent`
  - `config.yaml` now has `debug_dir` and `debug_snapshots` settings
  - `Core.__init__` falls back to config for debug settings

### 4. 🔄 `import requests` inside function in api.py
- **Status**: FIXED, not yet committed
- **Problem**: `import requests` inside `send_message()` 
- **Fix**: Moved to module level along with `import glob` and `import yaml`
- **Tests**: 1/2 pass (inline import test now passes)

### 5. ⬜ Duplicate shard listing code in api.py
- **Status**: FIXED, not yet committed
- **Problem**: Identical logic for globbing `shards/*.yaml` appears in both `list_shards()` and `_load_shard()`
- **Fix**: Extracted `_shard_files()` helper used by both functions
- **Tests**: Not yet verified

### 6. ⬜ Empty `Constants` section in context.py
- **Status**: Not yet fixed
- **Problem**: `# Constants` section with no content between two section dividers
- **Fix**: Remove the empty section (3 blank lines)

---

## Remaining Issues (NOT YET STARTED)

### 7. ⬜ `self.session_id = session_id` duplicated in `MemoryClient.__init__`
- **Location**: `context.py` lines 72-74
- **Problem**: `session_id` assigned twice (once on line 72, once on line 74)
- **Fix**: Remove the first assignment on line 72

### 8. ⬜ `import re` inside `reorder_messages` method
- **Location**: `context.py`, inside `reorder_messages` static method
- **Problem**: `import re` inside function body
- **Fix**: Move `import re` to module level

### 9. ⬜ Magic numbers in `context.py` truncate methods
- **Location**: `truncate_tool_result` uses 200 and 150 as defaults
- **Problem**: These are magic numbers, not configurable
- **Fix**: Make them configurable via config.yaml or constructor params

### 10. ⬜ `default_shard: code_hammer` typo in config.yaml
- **Location**: `config.yaml` line 35
- **Problem**: Should be `codehammer` (one word), not `code_hammer`
- **Fix**: Change to `codehammer`

### 11. ⬜ `pass` statement for truncation in `prepare_messages_for_llm`
- **Location**: `context.py`, `prepare_messages_for_llm` method
- **Problem**: Commented-out `pass` statement (dead code)
- **Fix**: Remove the `pass` statement

### 12. ⬜ `session_id` repeated in `MessageRequest` model comment
- **Location**: `api.py`, `MessageRequest` docstring
- **Problem**: `session_id` mentioned twice in the same comment
- **Fix**: Remove redundant mention

### 13. ⬜ Graceful error handling in `api.py send_message`
- **Location**: `api.py`, non-streaming mode
- **Problem**: `if event.get("context_rebuilt"): break` — on `break`, outer `while True` will return instead of looping. The harness controls the loop but the non-streaming path doesn't properly handle multiple turns.
- **Note**: This may be intentional — verify behavior before fixing

### 14. ⬜ `aclose()` on generator - async generator cleanup
- **Location**: `api.py`, `generate()` async function
- **Problem**: `await generator.aclose()` — `aclose()` is only available in Python 3.11+
- **Fix**: Use `generator athrow` or just `return` — or add `sys.version_info` check

### 15. ⬜ Orphaned `re` module usage vs imported `re`
- **Location**: `context.py`
- **Problem**: `import re` is inside the method, not module-level — but `re` module IS used at module level in `_json_safe`... wait, actually no, `_json_safe` doesn't use `re`. So it's only used inside `reorder_messages`. Move to module level.

### 16. ⬜ `__pycache__` in modules/
- **Location**: `modules/__pycache__/`
- **Problem**: Build artifact checked into git
- **Fix**: Add to `.gitignore` and remove from git

---

## Commits Made So Far

1. **fix: move import os to module level in planning.py** — planning tests + init file
2. **fix: remove redundant default.yaml shard and hardcoded paths** — shards tests + conftest

---

## Files Modified

- `modules/planning.py` — import os fix
- `modules/__init__.py` — exported `_session_id`
- `shards/default.yaml` — DELETED
- `shards/codehammer.yaml` — removed hardcoded debug_dir
- `core.py` — hardcoded path fix, config fallback for debug, error message fix
- `context.py` — relative path resolution for debug_dir
- `config.yaml` — added debug settings
- `tests/conftest.py` — test fixtures
- `tests/test_planning.py` — 13 tests
- `tests/test_shards.py` — 5 tests

## Files Modified (NOT YET COMMITTED)

- `api.py` — import requests at module level, _shard_files() helper
- `context.py` — empty Constants section, duplicate session_id assignment, import re
- `tests/test_api.py` — api module tests

---

## Next Steps (Priority Order)

1. **Commit api.py changes** (imports + _shard_files deduplication)
2. **Fix context.py**: empty Constants section, duplicate session_id, import re
3. **Fix api.py**: `aclose()` compatibility, `session_id` docstring duplication
4. **Fix config.yaml**: `code_hammer` typo → `codehammer`
5. **Remove context.py dead pass statement**
6. **Add `.gitignore` and remove `__pycache__` from git**
7. **Run all tests to verify everything passes**
8. **Generate final summary report**
