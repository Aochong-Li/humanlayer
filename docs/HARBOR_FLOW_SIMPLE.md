# Harbor Flow - Simple Summary

## The 5 Key Steps

```
1. CLI → JobConfig
   harbor run -p task -a agent -e env -n 1
   └─> Parse args into JobConfig object

2. Job → Orchestrator → TrialConfigs
   Job creates Orchestrator with list of trials to run

3. Orchestrator → Trial.run() (parallel)
   Orchestrator runs N trials concurrently

4. Trial → Agent.run()
   Each trial: setup env → setup agent → run agent → verify

5. Aggregate Results
   Collect all TrialResults → compute metrics → save
```

## Core Loop (What Happens Per Trial)

```python
# trial/trial.py:Trial.run()

1. await environment.start()           # Start container (Docker/E2B/etc)
2. await agent.setup(environment)      # Install dependencies
3. await agent.run(                    # Run the agent! 🚀
       instruction=task.instruction,
       environment=environment,
       context=agent_context
   )
4. await verifier.verify()             # Run tests, get reward
5. await environment.stop(delete=True) # Cleanup
```

## Where the Magic Happens

**The agent actually executes here:**

```python
# File: src/harbor/trial/trial.py, Line 230-234

await self._agent.run(
    instruction=self._task.instruction,  # What to do
    environment=self._environment,        # Where to do it
    context=self._result.agent_result    # Store results here
)
```

This calls into the specific agent implementation:
- `agents/installed/oracle.py` - Cheats, reads solution
- `agents/installed/claude_code.py` - Spawns `claude-code` CLI
- `agents/installed/openhands.py` - Spawns OpenHands
- etc.

## File → Function Reference (Quick Lookup)

| What | File | Function | Line |
|------|------|----------|------|
| **Entry point** | cli/main.py | `app()` | 14 |
| **Parse CLI args** | cli/jobs.py | `start()` | 103 |
| **Run all trials** | job.py | `Job.run()` | 269 |
| **Parallel execution** | orchestrators/local.py | `LocalOrchestrator.run()` | 286 |
| **Single trial** | trial/trial.py | `Trial.run()` | 319 |
| **Agent execution** | trial/trial.py | `Trial._execute_agent()` | 220 |
| **Verification** | trial/trial.py | `Trial._run_verification()` | 244 |

## Key Classes

```python
# The main objects and their purpose

JobConfig          # What to run (agents, tasks, settings)
↓
Job                # Orchestrates multiple trials
↓
Orchestrator       # Runs trials in parallel
↓
Trial              # Single agent × task run
↓
Agent              # Does the work (claude, openhands, etc)
Environment        # Where it runs (docker, e2b, etc)
Verifier           # Checks if it worked (runs tests)
↓
TrialResult        # What happened (reward, timing, errors)
JobResult          # Aggregate stats across all trials
```

## For HumanLayer: Where to Hook In

### Option 1: Wrap the Agent
```python
# Create a supervised agent
class HumanLayerAgent(BaseAgent):
    def __init__(self, real_agent, director, user):
        self.agent = real_agent
        self.director = director
        self.user = user

    async def run(self, instruction, environment, context):
        # Intercept agent.run() and add supervision
        ...
```

### Option 2: Wrap the Environment
```python
# Intercept environment.exec() calls
class SupervisedEnvironment(BaseEnvironment):
    async def exec(self, command, **kwargs):
        # Ask director/user before executing
        action = Action(command, "bash")
        allowed, reason = self.director.should_allow(action)
        if not allowed:
            # Ask user or block
            ...
        return await self.real_env.exec(command, **kwargs)
```

### Option 3: Hook into Trial Events
```python
# Add hooks to trial lifecycle
trial.add_hook(TrialEvent.AGENT_START, on_start)
trial.add_hook(TrialEvent.VERIFICATION_START, on_verify)
```

## Summary

Harbor is basically:
1. **Job** = Run multiple (agent × task) combinations
2. **Orchestrator** = Run them in parallel with concurrency control
3. **Trial** = Run one agent on one task (setup → run → verify → cleanup)
4. **Agent** = The AI that actually does the task
5. **Environment** = The sandbox where it runs
6. **Verifier** = Check if it worked

The flow is linear per trial but parallel across trials.
