# Mini-SWE-Agent Execution Flow

## Command: `mini` or `mini -v` or `python run/hello_world.py`

## Complete Execution Flow

```
CLI Command: mini
    ↓
__main__.py
    ↓
run/mini.py:app() → main()  [Line 47-104]
    ↓
    ├─ Load config from config/mini.yaml or config/default.yaml
    ├─ Prompt user for task (via prompt_toolkit)
    │
    ├─ Create Model
    │   └─ get_model(model_name, config) → LitellmModel
    │       └─ models/litellm_model.py:LitellmModel.__init__()
    │
    ├─ Create Environment
    │   └─ LocalEnvironment(**config.get("env", {}))
    │       └─ environments/local.py:LocalEnvironment.__init__()
    │
    ├─ Create Agent
    │   └─ InteractiveAgent or TextualAgent or DefaultAgent
    │       └─ agents/default.py:DefaultAgent.__init__()
    │           ├─ Initialize config (AgentConfig from YAML)
    │           ├─ self.messages = []
    │           ├─ self.model = model
    │           └─ self.env = env
    │
    └─ agent.run(task)
        ↓
        ↓
agents/default.py:DefaultAgent.run() [Line 66-79]
        ↓
        ├─ Initialize messages:
        │   messages = [
        │       {"role": "system", "content": system_template},
        │       {"role": "user", "content": instance_template_with_task}
        │   ]
        │
        └─ while True:  # THE MAIN LOOP
            │
            ├─ try:
            │   └─ self.step()  [Line 74]
            │       ↓
            │       ↓
            ├─ agents/default.py:step() [Line 81-83]
            │   └─ observation = self.get_observation(self.query())
            │       ↓
            │       ├─ self.query()  [Line 85-91]
            │       │   ↓
            │       │   ├─ Check limits (step_limit, cost_limit)
            │       │   ├─ response = self.model.query(self.messages)  [Line 89]
            │       │   │   ↓
            │       │   │   └─ models/litellm_model.py:query() [Line 68-97]
            │       │   │       └─ litellm.completion(model, messages)
            │       │   │           └─ Calls LLM API (Claude, GPT, etc)
            │       │   │           └─ Returns response with content
            │       │   │
            │       │   └─ self.add_message("assistant", response)
            │       │   └─ return response
            │       │
            │       └─ self.get_observation(response)  [Line 93-98]
            │           ↓
            │           ├─ action = self.parse_action(response)  [Line 100-105]
            │           │   ├─ Use regex to extract ```bash ... ```
            │           │   ├─ If found: return {"action": command}
            │           │   └─ If not: raise FormatError
            │           │
            │           ├─ output = self.execute_action(action)  [Line 107-116]
            │           │   ↓
            │           │   └─ try:
            │           │       └─ output = self.env.execute(action["action"])  [Line 109]
            │           │           ↓
            │           │           └─ environments/local.py:execute() [Line 20-35]
            │           │               └─ subprocess.run(
            │           │                      command,
            │           │                      shell=True,
            │           │                      cwd=cwd,
            │           │                      timeout=timeout
            │           │                  )
            │           │               └─ return {"output": stdout, "returncode": code}
            │           │
            │           │       └─ self.has_finished(output)  [Line 115]
            │           │           └─ Check if output starts with
            │           │              "MINI_SWE_AGENT_FINAL_OUTPUT"
            │           │           └─ If yes: raise Submitted(output)
            │           │
            │           ├─ observation = render_template(
            │           │       action_observation_template,
            │           │       output=output
            │           │   )
            │           │   └─ Formats as: <returncode>...</returncode><output>...</output>
            │           │
            │           └─ self.add_message("user", observation)
            │           └─ return output
            │
            └─ except NonTerminatingException as e:  [Line 75-76]
            │   └─ self.add_message("user", str(e))
            │   └─ continue  # Keep looping
            │
            └─ except TerminatingException as e:  [Line 77-79]
                └─ self.add_message("user", str(e))
                └─ return (type(e).__name__, str(e))  # Exit loop
                    ↓
                (Back to mini.py)
                    ↓
                Save trajectory to file
                Print result
```

## The Core Loop (Simplified)

```python
# agents/default.py:run()

messages = [system_prompt, user_task]

while True:
    # 1. Query LLM
    response = model.query(messages)
    messages.append({"role": "assistant", "content": response})

    # 2. Parse action (extract ```bash command ```)
    action = parse_action(response)

    # 3. Execute in environment
    output = env.execute(action)

    # 4. Check if done
    if "MINI_SWE_AGENT_FINAL_OUTPUT" in output:
        return "Submitted", output

    # 5. Add observation to messages
    messages.append({"role": "user", "content": f"<output>{output}</output>"})
```

## File → Function Reference

| What | File | Function | Line |
|------|------|----------|------|
| **Entry point** | `__main__.py` | imports `run/mini.py:app()` | 4 |
| **CLI main** | `run/mini.py` | `main()` | 47-104 |
| **Agent loop** | `agents/default.py` | `DefaultAgent.run()` | 66-79 |
| **Single step** | `agents/default.py` | `step()` | 81-83 |
| **Query LLM** | `agents/default.py` | `query()` | 85-91 |
| **Parse action** | `agents/default.py` | `parse_action()` | 100-105 |
| **Execute action** | `agents/default.py` | `execute_action()` | 107-116 |
| **Check done** | `agents/default.py` | `has_finished()` | 118-122 |
| **Model query** | `models/litellm_model.py` | `query()` | 68-97 |
| **Env execute** | `environments/local.py` | `execute()` | 20-35 |

## Key Data Structures

### Messages (The Trajectory)
```python
[
    {"role": "system", "content": "You are a helpful assistant...", "timestamp": 1234},
    {"role": "user", "content": "Please solve: Fix bug in file.py", "timestamp": 1235},
    {"role": "assistant", "content": "Let me check the file.\n```bash\ncat file.py\n```", "timestamp": 1236},
    {"role": "user", "content": "<returncode>0</returncode><output>...</output>", "timestamp": 1237},
    {"role": "assistant", "content": "I see the bug.\n```bash\nsed -i 's/old/new/g' file.py\n```", "timestamp": 1238},
    {"role": "user", "content": "<returncode>0</returncode><output></output>", "timestamp": 1239},
    ...
]
```

### Config (YAML)
```yaml
agent:
  system_template: "You are a helpful assistant..."
  instance_template: "Please solve: {{task}}"
  action_observation_template: "<returncode>{{output.returncode}}</returncode>..."
  action_regex: "```bash\\s*\\n(.*?)\\n```"
  step_limit: 0  # 0 = unlimited
  cost_limit: 3.0

environment:
  env:
    PAGER: cat
  timeout: 30

model:
  model_kwargs:
    drop_params: true
```

## The 3 Core Components

### 1. Model (LLM Interface)
```python
class LitellmModel:
    def __init__(self, model_name: str, **kwargs):
        self.config = LitellmModelConfig(model_name=model_name, **kwargs)
        self.cost = 0.0
        self.n_calls = 0

    def query(self, messages: list[dict]) -> dict:
        # Call LLM via litellm
        response = litellm.completion(model=self.config.model_name, messages=messages)

        # Track cost
        self.cost += litellm.cost_calculator.completion_cost(response)
        self.n_calls += 1

        return {"content": response.choices[0].message.content}
```

### 2. Environment (Executor)
```python
class LocalEnvironment:
    def __init__(self, cwd: str = "", env: dict = {}, timeout: int = 30):
        self.config = LocalEnvironmentConfig(cwd=cwd, env=env, timeout=timeout)

    def execute(self, command: str, cwd: str = "", timeout: int = None):
        # Every command runs in a fresh subprocess
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd or self.config.cwd,
            env=os.environ | self.config.env,
            timeout=timeout or self.config.timeout,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        return {"output": result.stdout, "returncode": result.returncode}
```

### 3. Agent (Orchestrator)
```python
class DefaultAgent:
    def __init__(self, model: Model, env: Environment, **kwargs):
        self.config = AgentConfig(**kwargs)  # From YAML
        self.messages = []
        self.model = model
        self.env = env

    def run(self, task: str) -> tuple[str, str]:
        # Initialize conversation
        self.messages = [
            {"role": "system", "content": render(self.config.system_template)},
            {"role": "user", "content": render(self.config.instance_template, task=task)}
        ]

        # Main loop
        while True:
            try:
                self.step()
            except NonTerminatingException as e:
                self.add_message("user", str(e))
            except TerminatingException as e:
                return type(e).__name__, str(e)

    def step(self):
        response = self.query()  # Get LLM response
        action = self.parse_action(response)  # Extract bash command
        output = self.execute_action(action)  # Run command
        self.add_observation(output)  # Add to messages
```

## Design Principles

### 1. **Stateless Execution**
Every command runs in a fresh subprocess:
```python
# This means cd doesn't persist
subprocess.run("cd /tmp", ...)  # ❌ Doesn't work
subprocess.run("cd /tmp && ls", ...)  # ✅ Works

# Every action is independent - great for sandboxing!
```

### 2. **Linear History**
```python
# The messages list IS the trajectory
# No special history processing
# Perfect for:
# - Debugging (just print messages)
# - Fine-tuning (messages = training data)
# - Replaying (re-send same messages)
```

### 3. **Template-Based Prompts**
```python
# All prompts are Jinja2 templates in YAML
system_template: |
  You are a helpful assistant on {{system}}.
  Current directory: {{cwd}}

instance_template: |
  Solve: {{task}}

action_observation_template: |
  <returncode>{{output.returncode}}</returncode>
  <output>{{output.output}}</output>
```

### 4. **Exception-Based Control Flow**
```python
# Different exception types control the loop
class NonTerminatingException(Exception):  # Agent can recover
    pass

class FormatError(NonTerminatingException):  # Bad format, ask again
    pass

class TerminatingException(Exception):  # End the run
    pass

class Submitted(TerminatingException):  # Agent finished successfully
    pass

class LimitsExceeded(TerminatingException):  # Hit step/cost limit
    pass
```

## Typical Execution Timeline

```
T+0s:   mini command starts
T+0.1s: Load config (mini.yaml)
T+0.2s: Prompt user for task
T+5s:   User enters "Fix bug in file.py"
T+5.1s: Create model (LitellmModel), env (LocalEnvironment), agent (InteractiveAgent)
T+5.2s: agent.run(task) starts
T+5.3s: Initialize messages with system + user prompts
T+5.4s: Step 1 - Query LLM
T+7s:   LLM responds with ```bash cat file.py```
T+7.1s: Parse action: "cat file.py"
T+7.2s: Execute: subprocess.run("cat file.py")
T+7.3s: Add observation to messages
T+7.4s: Step 2 - Query LLM
T+9s:   LLM responds with fix command
T+9.1s: Execute fix
T+9.2s: Step 3 - Query LLM
T+11s:  LLM submits: echo MINI_SWE_AGENT_FINAL_OUTPUT
T+11.1s: has_finished() detects submission
T+11.2s: Raise Submitted exception
T+11.3s: Exit loop, save trajectory
T+11.4s: Done
```

## Comparison: Mini-SWE-Agent vs Harbor

| Aspect | Mini-SWE-Agent | Harbor |
|--------|----------------|--------|
| **Entry** | `mini` → simple CLI | `harbor run` → complex CLI with many options |
| **Config** | YAML templates in config/ | Pydantic models + CLI args |
| **Execution** | Single agent, single task, synchronous | Multiple agents × tasks, parallel, async |
| **Agent Loop** | Simple while loop in DefaultAgent | Trial → Agent via factory |
| **Environment** | Direct subprocess.run() | Abstract BaseEnvironment (Docker, E2B, etc) |
| **History** | Linear messages list | ATIF trajectory format |
| **Verification** | Agent decides when done | Separate Verifier runs tests |
| **Sandboxing** | Optional (can use Docker env) | Built-in (always sandboxed) |
| **Scale** | 1 task at a time | 1000s of tasks in parallel |
| **Code Size** | ~100 lines core agent | ~10,000s lines |
| **Use Case** | Quick local tasks | Benchmark evaluation |

## For Your HumanLayer Framework

### Option 1: Wrap DefaultAgent.step()
```python
class HumanLayerAgent(DefaultAgent):
    def __init__(self, model, env, director, user, **kwargs):
        super().__init__(model, env, **kwargs)
        self.director = director
        self.user = user

    def step(self):
        # Get LLM response
        response = self.query()

        # Parse action
        action = self.parse_action(response)

        # ⭐ ADD SUPERVISION HERE
        hl_action = Action(content=action["action"], type="bash")
        allowed, reason = self.director.should_allow(hl_action)

        if not allowed:
            response = self.user.query(
                f"Blocked: {reason}\nAction: {action['action']}\nAllow?",
                options=["No", "Yes"]
            )
            if response == "No":
                # Tell agent it was blocked
                self.add_message("user", f"Action blocked: {reason}")
                return

        # Execute as normal
        output = self.execute_action(action)
        self.add_observation(output)
```

### Option 2: Wrap Environment.execute()
```python
class SupervisedLocalEnvironment(LocalEnvironment):
    def __init__(self, director, user, **kwargs):
        super().__init__(**kwargs)
        self.director = director
        self.user = user

    def execute(self, command: str, **kwargs):
        # Check before executing
        action = Action(content=command, type="bash")
        allowed, reason = self.director.should_allow(action)

        if not allowed:
            # Ask user or block
            ...

        return super().execute(command, **kwargs)
```

## Key Insight

Mini-SWE-Agent is **much simpler** than Harbor:
- **100 lines** for core agent loop vs **1000s** in Harbor
- **Synchronous** loop vs **async** parallel execution
- **Direct** subprocess calls vs **abstracted** environments
- **Single** run vs **batch** evaluation

This makes it **perfect** for learning and extending! The entire flow is in 3 files:
1. `run/mini.py` - CLI and setup
2. `agents/default.py` - The 100-line loop
3. `environments/local.py` - Simple subprocess wrapper

For HumanLayer, mini-swe-agent is **easier to wrap** than Harbor!
