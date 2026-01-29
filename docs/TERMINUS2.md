# Terminus 2 Agent - Codebase Overview

This document explains the structure and operation of the Terminus 2 agent located at `harbor/src/harbor/terminus_2/`.

## What is Terminus 2?

Terminus 2 is an **autonomous agent** that can interact with a terminal (command line) to complete tasks. Think of it as a program that:

1. Reads what's on a terminal screen
2. Asks an AI (LLM) what commands to run next
3. Types those commands into the terminal
4. Repeats until the task is done

It's designed for tasks like installing software, running scripts, navigating file systems, or any other terminal-based work.

---

## Directory Structure

```
terminus_2/
├── __init__.py                    # Makes the agent importable
├── terminus_2.py                  # Main agent logic (the brain)
├── tmux_session.py                # Terminal session manager
├── asciinema_handler.py           # Records terminal sessions
├── terminus_json_plain_parser.py  # Parses JSON responses from LLM
├── terminus_xml_plain_parser.py   # Parses XML responses from LLM
└── templates/
    ├── terminus-json-plain.txt    # Prompt template for JSON mode
    ├── terminus-xml-plain.txt     # Prompt template for XML mode
    └── timeout.txt                # Message shown when commands timeout
```

---

## Main Files Explained

### 1. `terminus_2.py` - The Brain (1726 lines)

This is the **main file** containing the `Terminus2` class. It orchestrates everything.

**What it does:**
- Receives a task instruction (e.g., "install Python and run hello.py")
- Repeatedly asks the LLM what to do next
- Executes commands in the terminal
- Tracks progress and decides when the task is complete

**Key class:** `Terminus2(BaseAgent)`

### 2. `tmux_session.py` - Terminal Manager (600 lines)

Manages the actual terminal where commands run using **tmux** (a terminal multiplexer).

**What it does:**
- Creates a virtual terminal session
- Sends keystrokes (types commands)
- Captures what's displayed on screen
- Records the session (like a video) using asciinema

**Key class:** `TmuxSession`

### 3. `terminus_json_plain_parser.py` - Response Parser (375 lines)

Parses the LLM's responses from JSON format into structured data the agent can use.

**Expected JSON format from LLM:**
```json
{
  "analysis": "What I see on screen...",
  "plan": "My next steps are...",
  "commands": [
    {"keystrokes": "ls -la", "duration": 1.0}
  ],
  "task_complete": false
}
```

### 4. `terminus_xml_plain_parser.py` - Alternative Parser (558 lines)

Same as above but for XML format (alternative to JSON).

### 5. `asciinema_handler.py` - Recording Helper (104 lines)

Adds markers to terminal recordings so you can review what happened at each step.

---

## How the Agent Runs - Step by Step

### Phase 1: Initialization

```
Terminus2.__init__(model_name="gpt-4", ...)
```

When you create a Terminus2 instance:
1. It validates you provided a model name
2. Creates an LLM client to talk to the AI
3. Picks a parser (JSON or XML)
4. Loads prompt templates

### Phase 2: Setup

```
await agent.setup(environment)
```

Before running tasks:
1. Creates a `TmuxSession` (virtual terminal)
2. Starts tmux with specified window size
3. Begins recording the terminal session

### Phase 3: Main Execution Loop

```
await agent.run(instruction="Your task here", environment, context)
```

This is where the work happens. The agent runs in a loop:

```
┌─────────────────────────────────────────────────────────────┐
│                     AGENT LOOP                              │
│                                                             │
│  1. Check if context is getting too long → Summarize?       │
│                        ↓                                    │
│  2. Ask LLM: "Here's the terminal. What should I do?"       │
│                        ↓                                    │
│  3. Parse LLM response → Get commands                       │
│                        ↓                                    │
│  4. Execute commands in terminal                            │
│                        ↓                                    │
│  5. Capture new terminal output                             │
│                        ↓                                    │
│  6. Record this step in trajectory                          │
│                        ↓                                    │
│  7. Is task complete? ──Yes──→ DONE                         │
│          │                                                  │
│          No                                                 │
│          ↓                                                  │
│     Go back to step 1                                       │
└─────────────────────────────────────────────────────────────┘
```

---

## Key Methods Explained

### `_run_agent_loop()` - The Main Loop
Location: `terminus_2.py`

This method runs the loop described above. For each iteration ("episode"):
- Checks if it needs to compress the conversation history
- Gets the LLM's response
- Runs the commands
- Checks if done

### `_query_llm()` - Talk to the AI
Location: `terminus_2.py`

Sends the current conversation to the LLM and gets a response. Handles errors like:
- Context too long → Triggers summarization
- Output truncated → Retries with error message

### `_execute_commands()` - Run Commands
Location: `terminus_2.py`

Takes the list of commands from the LLM and executes them one by one:
```python
for command in commands:
    session.send_keys(command.keystrokes, command.duration)
```

### `_summarize()` - Compress History
Location: `terminus_2.py`

When the conversation gets too long for the LLM, this creates a summary. It uses a 3-step process:
1. **Summarize**: What have we done so far?
2. **Question**: What important details might be missing?
3. **Answer**: Fill in those missing details

### `send_keys()` - Type in Terminal
Location: `tmux_session.py`

Actually sends keystrokes to the terminal session. Like a robot typing.

### `get_incremental_output()` - Read Screen
Location: `tmux_session.py`

Captures what's currently displayed in the terminal (only new content since last check).

---

## Data Flow Diagram

```
┌──────────────────┐
│   User's Task    │ "Install nginx and configure it"
└────────┬─────────┘
         │
         ↓
┌──────────────────┐
│   Terminus2.run  │ Creates chat, formats initial prompt
└────────┬─────────┘
         │
         ↓
┌──────────────────┐     ┌──────────────┐
│  _query_llm()    │────→│   LLM (AI)   │
│                  │←────│              │
└────────┬─────────┘     └──────────────┘
         │                JSON/XML response
         ↓
┌──────────────────┐
│  Parser          │ Extracts commands: ["apt install nginx", ...]
└────────┬─────────┘
         │
         ↓
┌──────────────────┐     ┌──────────────┐
│ _execute_commands│────→│ TmuxSession  │
│                  │←────│  (Terminal)  │
└────────┬─────────┘     └──────────────┘
         │                Terminal output
         ↓
┌──────────────────┐
│ Record Trajectory│ Save step for analysis/training
└────────┬─────────┘
         │
         ↓
    Loop continues...
```

---

## Important Concepts

### Trajectory
A complete record of everything the agent did - every LLM call, every command, every output. Saved as JSON files for later analysis or training.

### Episode
One iteration of the agent loop. Each episode = one LLM call + its resulting commands.

### Context / Tokens
LLMs have limited "memory" measured in tokens. When the conversation gets too long, the agent must summarize to continue.

### Task Completion
The agent requires **two consecutive** "task complete" signals to actually stop. This prevents premature termination.

---

## Configuration Options

When creating a Terminus2 agent, you can configure:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `model_name` | Required | Which LLM to use (e.g., "gpt-4") |
| `parser_name` | "json" | Response format: "json" or "xml" |
| `max_turns` | 1,000,000 | Maximum iterations before stopping |
| `temperature` | 0.7 | LLM creativity (0=deterministic, 1=random) |
| `enable_summarize` | True | Allow context compression |
| `tmux_pane_width` | - | Terminal width in characters |
| `tmux_pane_height` | - | Terminal height in characters |

---

## Quick Reference

| To understand... | Look at... |
|------------------|------------|
| How the agent thinks | `terminus_2.py` → `_run_agent_loop()` |
| How commands are sent | `tmux_session.py` → `send_keys()` |
| How LLM responses are parsed | `terminus_json_plain_parser.py` |
| What prompts the LLM sees | `templates/terminus-json-plain.txt` |
| How context is compressed | `terminus_2.py` → `_summarize()` |
