# HumanLayer Codebase Handoff

**Last Updated:** 2026-01-26

## Overview

HumanLayer is a framework for simulating human-agent interactions in coding environments. It supports three execution modes to study how AI agents perform tasks with varying levels of human involvement.

## Architecture

### Three Execution Modes

1. **Agent-Only** (`agentonly`): Autonomous agent solves tasks directly
2. **User-Agent** (`useragent`): Simulated user + AI agent interaction (no orchestrator)
3. **Orchestrated** (`orchestrated`): Orchestrator controls user cognitive state and task progression
   - `default`: Full LLM-based orchestration with perception, memory, and task progression
   - `simple`: Symbolic DFS task traversal with simple perception (no LLM for progression)

### Core Components

```
src/humanlayer/
├── agents/          # AI agent implementations (ChatAgent)
├── users/           # Simulated user implementations (User)
├── orchestrators/   # Orchestration logic (default, simple)
├── environments/    # Execution environments (local, e2b, docker)
├── models/          # LLM interface (litellm wrapper)
├── sessions/        # Session runners (agentonly.py, useragent.py, orchestrated.py)
└── config/          # Configuration files
```

## Key Features

### 1. Task Tree Structure
- Hierarchical task decomposition (root → intermediate → leaf nodes)
- Parsed from flat task instructions using LLM
- Tracked via `TaskNode` with status (pending/completed)

### 2. Orchestration (Simple Mode)
- **Task Progression**: DFS traversal of leaf nodes
- **User Memory**: Session history via `SessionHistory.get("user")`
- **Perception**: Truncates natural language (~64 tokens), preserves code blocks inline
- **Completion**: Marks current node complete after each user action
- **Termination**: User exits AND all nodes traversed

### 3. Session History
- `SessionHistory` tracks all interactions
- Messages have: `role`, `visible_to`, `reasoning`, `action`, `response`
- Filters by viewer (user/agent/orchestrator/system see different subsets)
- Skips empty messages to avoid API errors

### 4. User Simulation
- User profiles loaded from `config/user_profiles.yaml`
- Supports personas: `vibe_coder` (non-technical), `junior_developer`, `default`
- User actions: `execute` (bash), `request` (ask agent), `exit`
- Output format: `<think>reasoning</think>` + `<response>action</response>`

### 5. Environment Support
- **Local**: Direct command execution
- **E2B**: Sandboxed remote environment with Docker support
- **Docker/Singularity**: Containerized execution
- All async with upload/download capabilities

## Verification Flow

After session completion (for non-local environments):

1. Upload `/tests` directory to environment
2. Run `bash /tests/test.sh` in working directory (e.g., `/app`)
3. Read result from `/logs/verifier/reward.txt`
4. Save `result.json`:
   ```json
   {
     "success": 1,           // 0 or 1
     "test_output": "...",   // Full test output
     "returncode": 0,        // Exit code
     "verify": "..."         // Verification stdout/stderr
   }
   ```
5. Download environment snapshot to `environment_snapshot/`

## File Structure

### Configuration
- `config/orchestrated.yaml` - Orchestrator config with Jinja2 templates
- `config/user_agent.yaml` - User-agent mode config
- `config/agent_only.yaml` - Agent-only mode config
- `config/user_profiles.yaml` - User persona definitions

### Sessions
- `sessions/orchestrated.py` - Orchestrator session runner
- `sessions/useragent.py` - User-agent session runner
- `sessions/agentonly.py` - Agent-only session runner
- `sessions/history.py` - SessionHistory and Message classes

### Orchestrators
- `orchestrators/default.py` - Full LLM-based orchestration
- `orchestrators/simple.py` - Symbolic DFS orchestration

### Runners
- `examples/run_humanlayer.py` - Run orchestrated mode
- `examples/run_useragent.py` - Run user-agent mode
- `examples/run_agentonly.py` - Run agent-only mode

## Saved Output Structure

```
examples/jobs/{task_name}/
├── agentonly/{timestamp}/
│   ├── chat_history.json
│   ├── result.json
│   └── environment_snapshot/
├── useragent/{timestamp}/
│   ├── chat_history.json
│   ├── result.json
│   └── environment_snapshot/
└── orchestrated_simple/{timestamp}/
    ├── history.json
    ├── task_tree.json
    ├── result.json
    └── environment_snapshot/
```

## Recent Changes (Jan 2026)

1. **SimpleOrchestrator Implementation**
   - Symbolic DFS task traversal (no LLM for node selection)
   - Simple perception: truncate NL, preserve code blocks
   - Mark complete after each action
   - User memory = session history

2. **Unified Verification Flow**
   - All three modes now run tests and save results consistently
   - Added `verify` field to result.json
   - Download environment snapshot after verification

3. **Session History Improvements**
   - Renamed `ChatHistory` → `SessionHistory`
   - Added system message support (role="system")
   - Skip empty messages to prevent API errors

4. **E2B Environment Fixes**
   - Fixed Dockerfile build path (runs in environment_dir)
   - Handle command failures (catch `CommandExitException`)
   - Added `download_dir()` and `get_work_dir()` methods

5. **User Profile Management**
   - Centralized profiles in `config/user_profiles.yaml`
   - All run scripts load profiles from YAML

6. **Visualization**
   - Updated `viz/trajectory_visualizer.py` for system messages
   - Support both `history.json` and `chat_history.json`

## Usage

### Run a Task

```bash
# Agent-only mode
python examples/run_agentonly.py

# User-agent mode
python examples/run_useragent.py

# Orchestrated mode (simple)
python examples/run_humanlayer.py
```

### Visualize Results

```bash
streamlit run viz/trajectory_visualizer.py --server.port 8095
```

## Key Implementation Notes

1. **All sessions are async** - Use `asyncio.run()` for entry points
2. **Environment execution** - Must use `await env.execute()` (made async for compatibility)
3. **Template rendering** - Uses Jinja2 with `StrictUndefined` to catch missing variables
4. **Task tree traversal** - SimpleOrchestrator uses `_next_task_node()` to get DFS leaf order
5. **Working directory** - E2B defaults to `/app` (extracted from Dockerfile WORKDIR)
6. **Test scripts** - Must run from working directory using `cwd` parameter

## Dependencies

- LiteLLM (model interface)
- E2B (remote sandboxing)
- Jinja2 (template rendering)
- Pydantic (config validation)
- Streamlit (visualization)
- PyYAML (config loading)
- Tiktoken (token counting)

## Next Steps / TODOs

1. Test verification flow on real e2b environment
2. Implement default orchestrator (full LLM-based perception/progression)
3. Add more user profiles
4. Create session comparison/analysis tools
5. Add metrics tracking (turns, tokens, success rate)
6. Implement task tree validation

## Contact

For questions or issues, refer to the original implementation details in the codebase or session transcripts.
