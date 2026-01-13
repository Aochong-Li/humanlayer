# HumanLayer - Ready to Test

## ✅ Everything is set up

### Simplified Code
- ✅ `src/humanlayer/sessions/useragent.py` - Simplified (no rich/console, just prints)
- ✅ Added `user_profile` parameter for customizing user persona
- ✅ All imports cleaned up (minisweagent → humanlayer)

### Config
- ✅ `src/humanlayer/config/user_agent.yaml` - Updated with realistic "vibe coder" persona
- ✅ Uses `{{exit_code}}` template variable (defined as `[USER END]`)
- ✅ Uses `{{user_profile}}` in instance template

### Example Task
- ✅ `examples/run_humanlayer.py` - Set up to use COBOL modernization task
- ✅ Reads instruction from `examples/tasks/cobol-modernization/instruction.md`
- ✅ Sets user profile as "developer with minimal COBOL experience"

## Run It

```bash
# Make sure API key is set
export ANTHROPIC_API_KEY="your-key"

# Run the example
cd /home/al2644/research/codebase/agent/humanlayer
python examples/run_humanlayer.py
```

## What Will Happen

1. User (LLM) receives COBOL modernization task
2. User can:
   - Execute bash commands (ls, cat, etc.)
   - Request help from agent
   - Exit with `[USER END]` when done
3. Agent provides advice when asked
4. Session history tracks it all

## Output Format

```
============================================================
Task: [COBOL modernization instruction]
============================================================

--- Step 1 ---
[User thinks]: I need to first explore...
[User executes]: ls -la
[Return]: 0
[Output]: [command output]

--- Step 2 ---
[User thinks]: I'm not sure how to...
[User requests]: How do I read COBOL files?
[Agent]: You can use cat to read...

--- Step 3 ---
[User executes]: cat program.cbl
[Output]: [COBOL code]

...

[Done]: [USER END] Task completed
============================================================
Completed in N steps
============================================================
```

## Key Files

| File | Purpose |
|------|---------|
| `src/humanlayer/users/default.py` | User (LLM that does work) |
| `src/humanlayer/agents/default.py` | Agent (helper) |
| `src/humanlayer/sessions/history.py` | Track conversation |
| `src/humanlayer/sessions/useragent.py` | Main loop |
| `src/humanlayer/config/user_agent.yaml` | Prompts & settings |
| `examples/run_humanlayer.py` | Test runner |

## Notes

- User has limited coding skills (realistic novice behavior)
- Agent provides guidance when asked
- User's commands are private (agent can't see)
- User's requests and agent's responses are shared
- Simple print-based output (no fancy formatting)
