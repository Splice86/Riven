# Plan: Remove `section` and `capacity` from screens

## Why

Both were introduced to support windowed file viewing — sending only a slice of lines to the browser, then scrolling to it. Since we now send the full file on every snapshot and let the browser's native scrollbar handle navigation, neither concept is needed.

Removing them also eliminates:
- The `bound_section` field that lives in 4+ files but is never acted on meaningfully
- `screen_bind_section` tool that nobody calls
- The `_computeScrollTarget` JS logic for handling section offsets
- `PROP_BOUND_SECTION` constant that was never imported anywhere
- `FileSnapshot.slice()` which is now equivalent to just `.lines`

## Changes by file

### 1. `_diff.py`
- `FileSnapshot.slice(section=..., capacity=...)` → keep method but strip both params (callers always pass nothing now)
- Rename `sections` field in `LineDiff`? No — it's the diff sections, not file sections. Keep it.

### 2. `_broadcaster.py`
- `_build_snapshot(path, version, section)` → `_build_snapshot(path, version)` — no section arg
- `snap.slice(section=section)` → `snap.lines` — full file
- Remove `"section"` and `"showing"` keys from snapshot payload (they're meaningless now)
- `broadcast_bind(screen)` — remove `section=` from bound message
- `_build_diff` — keep as-is (sections is diff sections, not file sections)

### 3. `_registry.py`
- `ScreenConnection.__slots__` — remove `"bound_section"`
- `ScreenConnection.__init__` — remove `bound_section` param
- `ScreenConnection.to_dict()` — remove `"bound_section"` key
- `ScreenRegistry.bind(uid, path, section)` → `ScreenRegistry.bind(uid, path)` — no section arg
- `ScreenRegistry.release()` — remove `screen.bound_section = ""` line
- Update log message in `bind()` — remove `section={section}`

### 4. `_ws.py`
- `registered` message — remove `bound_section` key
- `bound` message — remove `section` key (it's the self-bind path, different from file section but same reasoning)
- Self-bind handler: remove `section = msg.get("section", "")` and related code

### 5. `_tools.py`
- Remove `screen_bind_section()` entirely
- `screen_bind(path, screen_uid, section=...)` → `screen_bind(path, screen_uid)` — no section param
- `screen_list()` — remove `section_str` display line
- `screen_status()` — remove `Bound section` line
- `screen_bind` return message — remove section mention
- Update `__init__.py` exports

### 6. `constants.py`
- Remove `PROP_BOUND_SECTION = "bound_section"`
- Remove `"bound_section"` from the schema docstring in the file header

### 7. `_db.py`
- `register_screen()` — remove `section` from return dict
- `set_screen_bound()` — remove `section` param

### 8. `__init__.py`
- Remove `screen_bind_section` from the `from ._tools import` line

### 9. `screen.html`
- `_computeScrollTarget` — simplify further (only care about first 'added' section, already done)
- `scrollToLine` guard — `lineIdx >= linesEl.children.length` still matters since we now have full file in DOM
- Diff handler — `msg.section` is no longer in payload — remove reference
- Snapshot handler — `msg.section` and `msg.showing` no longer in payload — remove references

## Non-changes (intentional)

- `LineDiff.sections` — keeps the same name. It's diff sections, not file sections. Clear from context.
- `diff.sections` in JS — same. Received from server and used correctly.
- `renderLines` in screen.html — still works fine, no changes needed there.
- The `section` concept in `constants.py`'s schema docstring was for the DB design — already non-functional. Just clean the property name.

## Execution order

1. `_diff.py` — foundation
2. `_registry.py` — core type
3. `_broadcaster.py` — uses registry + diff
4. `_ws.py` — uses registry
5. `_tools.py` — uses registry + broadcaster
6. `__init__.py` — uses tools
7. `constants.py` — dead code cleanup
8. `_db.py` — stub consistency
9. `screen.html` — payload cleanup
10. Verify: grep for `bound_section` and `section` (as window param) across all files

## Verification ✅

```bash
$ grep -rn 'bound_section\|PROP_BOUND_SECTION\|screen_bind_section' modules/file/screens/ --include='*.py'
# → only: lines = snap.slice()   ← the one legitimate call

$ grep -n 'msg\.section\|msg\.showing\|msg\.bound_section' modules/file/static/screen.html
# → only: msg.sections (diff sections, correct)
```

## Actual changes made

| File | What changed |
|---|---|
| `_diff.py` | `slice(section=, capacity=)` → `slice()` — no args, returns all lines |
| `_registry.py` | Removed `bound_section` from `__slots__`, `__init__`, `to_dict()`; simplified `bind()` and `release()` |
| `_broadcaster.py` | `_build_snapshot()` dropped `section`; removed `section`/`showing` from payload; removed `section` from `broadcast_bind()` |
| `_ws.py` | Removed `bound_section` from `registered` msg; removed `section` from self-bind handler and `bound` msg |
| `_tools.py` | Removed `screen_bind_section` entirely; `screen_bind()` loses `section` param; cleaned list/status output |
| `__init__.py` | Removed `screen_bind_section` from exports |
| `constants.py` | Removed `PROP_BOUND_SECTION` and `bound_section` from schema doc |
| `_db.py` | Removed `section` from stub function signatures |
| `screen.html` | Already clean — all `section` refs are diff sections |
| `PLAN.md` | This file |

## What's still here (intentionally)

- `LineDiff.sections` — the diff sections list, completely separate concept
- `_computeScrollTarget(sections)` in JS — uses diff sections to find scroll target
- `renderLines(rawLines, 'added')` — applies diff sections to DOM
- `msg.sections` in diff handler — this is the diff, not the file window

---

## Side Fix: `jellyfish` import broke module discovery

**Problem:** `modules.file` imports `jellyfish` at top of `editor.py` and `code_parser.py`.
`api.py`'s `_discover_modules()` imports `modules.file` → fails silently (bare `except`)
→ `file` never found → `register_routes` never called → screens router never registered → 404.

**Fix applied:** Lazy imports — `import jellyfish` moved inside the functions that use it.

| File | Change |
|---|---|
| `editor.py` | Removed top-level `import jellyfish`; added inside `_find_best_window()` |
| `code_parser.py` | Removed top-level `import jellyfish`; added inside `_find_definitions_by_name()` |
| `modules/file/__init__.py` | Removed `screen_bind_section` import and tool spec (was still referencing removed function) |

**Verification:** `python3 -c "..."` — `file` module now discovers with `register_routes`.
