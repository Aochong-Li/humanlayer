# HumanLayer User-Agent Workflow

## Quick Start

### Run the example:
```bash
python example_task.py
```

### Run with CLI:
```bash
python -m humanlayer.sessions.useragent -t "Create a file called test.txt with 'hello world' inside"
```

### With custom config:
```bash
python -m humanlayer.sessions.useragent \
  -t "Your task here" \
  -c path/to/config.yaml
```

## How It Works

1. **User (LLM)** receives a task
2. **User decides** at each step:
   - Execute a bash command directly
   - Request help from the Agent (another LLM)
   - Exit when done

3. **Agent** provides advice when requested

4. **SessionHistory** tracks the conversation with different visibility:
   - User's commands are private (agent can't see them)
   - User's requests to agent are visible to both
   - Agent's responses are visible to both

## Example Flow

```
Step 1:
  User thinks: "I need to create a file, I can do this myself"
  User executes: `echo "Hello" > test.txt`
  Output: (empty, success)

Step 2:
  User thinks: "Let me verify it worked"
  User executes: `cat test.txt`
  Output: "Hello"

Step 3:
  User thinks: "Task is complete"
  User exits: [USER END] Task completed successfully
```

## With Agent Help

```
Step 1:
  User thinks: "I'm not sure how to do this, let me ask the agent"
  User requests: "How do I create a Python virtual environment?"

  Agent thinks: "They need venv"
  Agent responds: "Use `python -m venv .venv` to create a virtual environment"

Step 2:
  User thinks: "Got it, I'll do that"
  User executes: `python -m venv .venv`
  Output: (success)
```

## Config Structure

See `src/humanlayer/config/user_agent.yaml` for the full config with:
- `user.system_template` - Instructions for the user LLM
- `agent.system_template` - Instructions for the agent LLM
- `history.*_template` - How messages are formatted
- `model` - Which LLM to use

## Environment Variables

Set your API key:
```bash
export ANTHROPIC_API_KEY="your-key-here"
```

Or create `.env` file at `~/.config/humanlayer/.env`
