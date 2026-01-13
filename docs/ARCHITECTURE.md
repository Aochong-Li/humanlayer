# HumanLayer Architecture

## 4 Core Components

### 1. Agent (`core.Agent`)
**What it does:** Takes actions to solve a task

**Interface:**
```python
def step() -> Action          # Returns next action
def observe(obs) -> None      # Receives feedback
def is_done() -> bool         # Are we finished?
```

### 2. Director (`core.Director`)
**What it does:** Supervises agent, can block dangerous actions

**Interface:**
```python
def should_allow(action) -> (bool, str)  # Allow this action?
def on_step(action, obs) -> None         # Log/monitor each step
```

### 3. User (`core.User`)
**What it does:** Human in the loop - makes decisions when needed

**Interface:**
```python
def query(question, options) -> str  # Ask human a question
def notify(message) -> None          # Tell human something
```

### 4. Orchestrator (`runner.HumanLayerRunner`)
**What it does:** Ties them together, runs the main loop

```python
runner = HumanLayerRunner(agent, director, user)
success, msg = runner.run()
```

**The loop:**
1. Agent proposes action
2. Director checks if allowed
3. If blocked, ask User to override
4. Execute action
5. Give observation back to Agent
6. Repeat until done

## Adapter Pattern

To wrap existing frameworks (mini-swe-agent, openhands, etc):

```python
class MiniSWEAgentAdapter:
    def __init__(self, mini_agent):
        self.mini_agent = mini_agent

    def step(self) -> Action:
        # Translate mini-swe-agent's step to our Action
        pass

    def observe(self, obs: Observation):
        # Translate our Observation to mini-swe-agent format
        pass
```

## File Structure

```
src/humanlayer/
├── core/           # Protocols (Agent, Director, User)
├── agents/         # Default agent implementations
├── directors/      # Default director implementations
├── users/          # Default user implementations
├── adapters/       # Wrappers for existing frameworks
└── runner.py       # The orchestrator
```
