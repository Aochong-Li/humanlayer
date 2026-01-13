# HumanLayer Prototype Summary

## What You Built

A **user-driven** workflow where an LLM "user" works on tasks and can optionally ask an LLM "agent" for help.

This is the **inverse** of mini-swe-agent:
- **mini-swe-agent**: Agent drives, executes commands
- **humanlayer**: User drives, can ask agent for help

## Core Components

### 1. DefaultUser (`src/humanlayer/users/default.py`)
- LLM that acts as a "user"
- At each step decides:
  - Execute bash command myself
  - Request help from agent
  - Exit when done

### 2. Agent (`src/humanlayer/agents/default.py`)
- Helper LLM that provides advice
- Only responds when user requests help

### 3. SessionHistory (`src/humanlayer/sessions/history.py`)
- Tracks conversation with visibility controls
- User's commands are private (agent can't see)
- Requests/responses are shared

### 4. Main Loop (`src/humanlayer/sessions/useragent.py`)
- Orchestrates user ↔ agent interaction
- Displays formatted output

## Files Created/Modified

### Created:
- `src/humanlayer/config/user_agent.yaml` - Config with prompts
- `example_task.py` - Simple test
- `USAGE.md` - How to use it
- `PROTOTYPE_SUMMARY.md` - This file

### Modified:
- `src/humanlayer/sessions/useragent.py` - Added CLI, formatting, agent parsing

## How to Test

### Simple test:
```bash
python example_task.py
```

### CLI:
```bash
python -m humanlayer.sessions.useragent -t "Create a test.txt file"
```

### With API key:
```bash
export ANTHROPIC_API_KEY="your-key"
python -m humanlayer.sessions.useragent -t "Your task"
```

## Example Workflow

```
Task: Create a Python script called hello.py

Step 1:
  User thinks: "I'll create the file"
  User executes: echo 'print("Hello!")' > hello.py
  Output: (success)

Step 2:
  User thinks: "Let me test it"
  User executes: python hello.py
  Output: "Hello!"

Step 3:
  User thinks: "Done!"
  User exits: [USER END]
```

## Next Steps

To make this a real HumanLayer framework, you could:

1. **Add Director**: Supervise what user tries to execute
2. **Add Human User**: Replace LLM user with real human
3. **Add More Agents**: Different types of helpers
4. **Add Logging**: Track decisions for analysis
5. **Add Evaluation**: Measure how well users perform

But for now, this prototype lets you **test how an LLM "user" behaves** when given tasks and optional agent help!
