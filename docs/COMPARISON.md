# Mini-SWE-Agent vs Harbor: Side-by-Side Comparison

## The Main Loop (Core Logic)

### Mini-SWE-Agent (100 lines)
```python
# agents/default.py:run()

def run(self, task: str):
    messages = [system_prompt, user_task]

    while True:
        # 1. Query LLM
        response = self.model.query(messages)
        messages.append(assistant_response)

        # 2. Parse bash command
        action = parse_action(response)

        # 3. Execute
        output = self.env.execute(action)

        # 4. Check if done
        if "FINAL_OUTPUT" in output:
            return "Submitted", output

        # 5. Add to messages
        messages.append(user_observation)
```

### Harbor (1000s of lines)
```python
# trial/trial.py:run()

async def run(self):
    # 1. Setup environment (container)
    await environment.start()

    # 2. Setup agent (install dependencies)
    await agent.setup(environment)

    # 3. Execute agent (black box - agent controls loop)
    await agent.run(instruction, environment, context)

    # 4. Verify (run tests)
    result = await verifier.verify()

    # 5. Cleanup
    await environment.stop()

    return TrialResult
```

## Architecture Comparison

```
┌─────────────────────────────────────────────────────────────────┐
│                      MINI-SWE-AGENT                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  CLI: mini                                                      │
│   ↓                                                             │
│  Agent (controls loop) ──→ Model ──→ LLM API                   │
│   │                         ↑                                   │
│   │                         └── LiteLLM wrapper                 │
│   ↓                                                             │
│  Environment ──→ subprocess.run()                               │
│                                                                 │
│  Linear flow, single task, simple                               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                         HARBOR                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  CLI: harbor run                                                │
│   ↓                                                             │
│  Job ──→ Orchestrator (parallel execution)                      │
│           ↓                                                     │
│           Trial₁   Trial₂   Trial₃ ... (concurrent)             │
│           │                                                     │
│           ├── Environment (Docker/E2B/Modal/etc)                │
│           │    ↓                                                │
│           │    Container with full sandbox                      │
│           │                                                     │
│           ├── Agent (any: claude-code, openhands, etc)          │
│           │    ↓                                                │
│           │    Agent controls its own loop internally           │
│           │                                                     │
│           └── Verifier (runs tests, gets reward)                │
│                ↓                                                │
│                TrialResult                                       │
│                                                                 │
│  Parallel, async, complex orchestration                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Key Differences

| Aspect | Mini-SWE-Agent | Harbor |
|--------|----------------|--------|
| **Philosophy** | Simple, hackable, transparent | Production-grade, scalable, flexible |
| **Control** | Agent controls loop | Trial controls lifecycle |
| **Agent Loop** | Visible (in agents/default.py) | Hidden (inside each agent) |
| **History** | Linear messages list | ATIF trajectory format |
| **Execution** | Synchronous, single-threaded | Async, parallel, concurrent |
| **Scale** | 1 task at a time | 1000s of tasks in parallel |
| **Environments** | Simple subprocess wrapper | Full sandboxing (Docker, E2B, etc) |
| **Verification** | Agent decides when done | Separate verifier runs tests |
| **Code Size** | ~100 lines core | ~10,000+ lines |
| **Dependencies** | Minimal (litellm, jinja2) | Heavy (docker, async libs, etc) |
| **Learning Curve** | Easy (read 3 files) | Steep (many abstractions) |
| **Extensibility** | Modify 100-line loop | Implement protocols |
| **Use Case** | Local dev, experimentation | Benchmarks, evaluation at scale |

## The Agent Loop Location

### Mini-SWE-Agent
**You control the loop:**
```python
# agents/default.py - YOU SEE THIS
while True:
    response = model.query(messages)
    action = parse_action(response)
    output = env.execute(action)
    if done: break
    messages.append(observation)
```

### Harbor
**Agent controls its own loop:**
```python
# You don't see this - it's inside each agent
# agents/installed/claude_code.py
async def run(self, instruction, environment, context):
    # Spawns `claude-code` CLI
    # Claude Code has its own internal loop
    # You don't control it, just get the result

# agents/installed/openhands.py
async def run(self, instruction, environment, context):
    # Spawns OpenHands
    # OpenHands has its own loop
    # Black box from Harbor's perspective
```

## When to Use Which?

### Use Mini-SWE-Agent when:
- ✅ Building a prototype
- ✅ Learning how agents work
- ✅ You want full control over the loop
- ✅ Running locally on your machine
- ✅ Working on single tasks
- ✅ Want to modify agent behavior easily
- ✅ Need transparency (see every step)

### Use Harbor when:
- ✅ Running benchmarks (SWE-bench, etc)
- ✅ Evaluating multiple agents
- ✅ Need parallel execution (100+ trials)
- ✅ Want cloud sandboxing (E2B, Modal)
- ✅ Comparing agent performance
- ✅ Need reproducible results
- ✅ Production evaluation pipeline

## For HumanLayer: Which is Easier to Wrap?

### Mini-SWE-Agent: ⭐ EASIER
**Why:**
- The loop is exposed (agents/default.py)
- Only 100 lines to understand
- You can intercept at step level
- Single execution flow

**How:**
```python
class HumanLayerAgent(DefaultAgent):
    def step(self):
        response = self.query()
        action = self.parse_action(response)

        # ⭐ ADD YOUR SUPERVISION HERE
        allowed = self.director.should_allow(action)
        if not allowed:
            # Block or ask user
            ...

        output = self.execute_action(action)
        return output
```

### Harbor: HARDER
**Why:**
- Agent loop is inside each agent (claude-code, openhands)
- You don't control the agent loop
- Must wrap at environment level or trial hooks
- More abstractions to understand

**How:**
```python
# Option 1: Wrap environment.exec()
class SupervisedEnvironment(BaseEnvironment):
    async def exec(self, command, **kwargs):
        # Check every command agent tries to run
        allowed = self.director.should_allow(command)
        ...

# Option 2: Create a HumanLayer agent wrapper
class HumanLayerAgent(BaseAgent):
    def __init__(self, real_agent, director, user):
        self.agent = real_agent
        ...

    async def run(self, instruction, environment, context):
        # Wrap the entire agent.run() call
        ...
```

## Code Complexity

### Mini-SWE-Agent Files You Need to Read:
```
1. agents/default.py     (123 lines) - The core loop
2. environments/local.py  (39 lines) - Execute commands
3. models/litellm_model.py (101 lines) - LLM wrapper
4. run/hello_world.py     (37 lines) - Example usage
────────────────────────────────────
   Total: ~300 lines
```

### Harbor Files You Need to Read:
```
1. cli/jobs.py           (800+ lines) - CLI parsing
2. job.py                (300+ lines) - Job orchestration
3. orchestrators/local.py (350+ lines) - Parallel execution
4. trial/trial.py        (400+ lines) - Trial lifecycle
5. agents/base.py        (100+ lines) - Agent protocol
6. environments/base.py  (200+ lines) - Environment protocol
7. verifier/verifier.py  (200+ lines) - Verification
────────────────────────────────────
   Total: ~2,350+ lines (just the core!)
```

## Recommendation for HumanLayer

**Start with Mini-SWE-Agent** because:

1. **Simpler architecture** - easier to understand
2. **Exposed loop** - you can see and control every step
3. **Less code** - 300 lines vs 2,350+ lines
4. **Better learning** - understand agent patterns first
5. **Easier integration** - just extend DefaultAgent
6. **Faster iteration** - modify and test quickly

**Then expand to Harbor** once you have:
- Working HumanLayer with mini-swe-agent
- Proven supervision patterns
- Clear understanding of what to intercept

## Summary

```
Mini-SWE-Agent = Simple, transparent, easy to hack
Harbor         = Complex, powerful, production-ready

For learning and building HumanLayer:
Start with Mini-SWE-Agent ✓

For benchmarking HumanLayer at scale:
Eventually support Harbor ✓
```

Your humanlayer framework can start by wrapping mini-swe-agent's simple loop, prove the concept works, then expand to support Harbor's more complex architecture later!
