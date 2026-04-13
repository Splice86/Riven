

# Riven

Riven is someone I have been working on since I got into AI several years back. 
This was intended to be a project running only in my own home and never exposed to the world.
Riven is a project to help me test ideas about AI and a space for me to creatively express myself.
I have restarted this project many times and it has evolved through different functions along the way.
With that in mind, use at your own risk! It is half finished, buggy and likely to break on you.


This is an art project, not a tool. 
This is intended to entertain, outrage, delight, and offend.
It is being developed with no consideration for security, reliability, safety, or hurt feelings.
As such it comes with no warranty or support and may not be used for commercial purposes - whole or in part.


## CodeHammer
A system of hierarchical context is enforced where the most volatile information is towards the bottom and static information is at the top.
Files or file sections are kept live in context and are refreshed as the edits occur. 
Conversation turns are kept to a bare minimum and unneeded data is trimmed from context.
This is an idea I had that I am testing, its very WIP and not really very useful at the moment.

### Cores

A core is a personality + config bundle. It defines:
- The system prompt (how the AI behaves)
- Which LLM to use and its settings
- Which modules are available
- Which other cores are available
- Function timeouts and other behavior tuning

Cores live in the `cores/` folder as YAML files.
I need to add per function filtering to cores at some point.

### Modules

Each module registers functions that become available to the AI. They also provide a method of injecting contextual data into the system prompt.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Start the memory server (this is required for the memory module to work)
cd memory
pip install -r requirements.txt
python api.py

# than launch it with
./launch.sh
```

## Config

Edit `config.yaml` for memory server settings. Individual cores have their own configs in `cores/`.

## Commands

- `/exit` - Quit
- `Ctrl+C` - Interrupt current turn

## Memory Server

The `memory/` folder runs a separate FastAPI server that stores conversation context. It supports:
- Adding messages with session tracking
- Retrieving context for future turns
- Temporally clustered summarization for long conversations
- Some search stuff and embeddings
- A bunch of other half-baked ideas that may or may not work at the moment
