# Riven 🐶

A modular AI agent with tool use, memory, and extensible modules.

## Overview

Riven is an AI coding assistant built with pydantic_ai that can:
- Read, edit, and write files
- Execute shell commands
- Search and store memories
- Extend functionality via modules

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the agent
python main.py
```

## Configuration

Edit `config.yaml` to customize:
- LLM endpoint and model
- Tool timeouts
- Memory storage settings

### Available Cores

| Core | Purpose |
|------|---------|
| `default` | General purpose assistant |
| `coding` | Software development focused |
| `research` | Research & information gathering |

```bash
# Run with specific core
python main.py --core coding
```

## Modules

Riven uses a modular architecture. Each module provides tools:

| Module | Tools |
|--------|-------|
| **file** | open_file, get_lines, replace_lines, insert_lines, remove_lines, replace_text_at_line, save_file, save_all_files, close_file, list_open_files |
| **shell** | run_shell_command |
| **memory** | search_memories, add_memory, get_memory, list_memories, get_memory_stats, get_recent_context |
| **system** | exit_session, check_reload_modules, get_system_info |
| **time** | get_current_time |
| **bio_riven** | About the agent |

### Writing Custom Modules

A module is a `Module` with:
- `name` - module identifier
- `functions` - dict of async functions
- `enrollment` - setup function (optional)
- `get_context` / `tag` - for system prompt context

```python
from modules import Module

def get_module():
    async def my_tool(arg: str) -> str:
        """Tool description."""
        return f"Result: {arg}"
    
    return Module(
        name="my_module",
        enrollment=lambda: None,
        functions={"my_tool": my_tool}
    )
```

## Memory API

> **Note:** The `memory/` folder is a separate **FastAPI server** that provides vector-backed memory storage and search.

### Running the Memory API

```bash
cd memory
pip install -r requirements.txt
python api.py
# Server runs on http://localhost:8030
```

See `memory/README.md` for full Memory API documentation.

## Commands

| Command | Description |
|---------|-------------|
| `/exit` | Exit the agent |
| `Ctrl+C` | Interrupt current operation |

## File Editing

When using file tools, provide correct indentation in your content - the tools don't auto-adjust indentation.

## License

MIT