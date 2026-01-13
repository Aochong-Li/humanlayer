# Harbor Execution Flow

## Command: `harbor run -p ./harbor/examples/tasks/hello-world -a oracle -e e2b -n 1`

### Complete Execution Flow

```
CLI Command
    ↓
main.py:app()
    ↓
jobs.py:start()  [Line 103-703]
    ↓
    ├─ Parse CLI arguments
    │   -p: path to task/dataset
    │   -a: agent name (oracle)
    │   -e: environment type (e2b)
    │   -n: n_concurrent_trials (1)
    │
    ├─ Build JobConfig object [Line 531]
    │   ├─ agents: [AgentConfig(name='oracle')]
    │   ├─ environment: EnvironmentConfig(type='e2b')
    │   ├─ tasks: [TaskConfig(path='./harbor/examples/tasks/hello-world')]
    │   └─ orchestrator: OrchestratorConfig(n_concurrent_trials=1)
    │
    ├─ Create Job(config) [Line 673]
    │
    └─ asyncio.run(job.run()) [Line 677]
        ↓
        ↓
job.py:Job.run() [Line 269-320]
        ↓
        ├─ Create JobResult object
        ├─ Save config to job_dir/config.json
        │
        └─ await orchestrator.run() [Line 279]
            ↓
            ↓
orchestrators/local.py:LocalOrchestrator.run() [Line 286-343]
            ↓
            ├─ Create semaphore (concurrency control)
            ├─ Create progress bars
            │
            └─ For each trial_config:
                └─ asyncio.create_task(_run_trial(...))
                    ↓
                    ↓
LocalOrchestrator._run_trial() [Line 161-244]
                    ↓
                    └─ _execute_trial_with_retries() [Line 110-159]
                        ↓
                        ├─ Create Trial(trial_config) [Line 120]
                        │
                        └─ await trial.run() [Line 125]
                            ↓
                            ↓
trial/trial.py:Trial.run() [Line 319-396]
                            ↓
                            ├─ Trigger START hooks
                            ├─ Create trial directory
                            ├─ Save trial config
                            │
                            ├─ await _setup_environment() [Line 339]
                            │   └─ environment.start(force_build=...)
                            │
                            ├─ await _setup_agent() [Line 340]
                            │   └─ agent.setup(environment)
                            │
                            ├─ await _execute_agent() [Line 343]
                            │   └─ [Line 220-243]
                            │       └─ await agent.run(
                            │              instruction=task.instruction,
                            │              environment=environment,
                            │              context=agent_result
                            │          ) [Line 230-234]
                            │
                            ├─ Download agent logs
                            │
                            ├─ await _run_verification() [Line 363]
                            │   └─ [Line 244-253]
                            │       └─ verifier = Verifier(task, trial_paths, environment)
                            │           └─ await verifier.verify()
                            │               └─ Runs tests in environment
                            │               └─ Parses reward from /logs/verifier/reward.txt
                            │
                            ├─ await _cleanup_and_finalize() [Line 394]
                            │   ├─ Stop and delete environment
                            │   ├─ Save trial result to result.json
                            │   └─ Trigger END hooks
                            │
                            └─ return TrialResult
                                ↓
                            (Back to orchestrator)
                                ↓
                            Collect all trial results
                                ↓
                            Return to Job.run()
                                ↓
                            Compute metrics and stats
                            Save job result
                            Print results tables
```

## Key Files & Functions

### 1. CLI Entry Point
- **File**: `src/harbor/cli/main.py`
- **Function**: `app = Typer()` with `start` command
- **Purpose**: Parse command line arguments

### 2. Job Orchestration Setup
- **File**: `src/harbor/cli/jobs.py`
- **Function**: `start()` [Line 103-703]
- **Purpose**:
  - Parse all CLI flags
  - Build `JobConfig` from arguments
  - Create `Job` instance
  - Run the job

### 3. Job Execution
- **File**: `src/harbor/job.py`
- **Class**: `Job`
- **Key Methods**:
  - `__init__(config)` [Line 38-75]:
    - Initialize trial configs
    - Create orchestrator
    - Set up metrics
  - `run()` [Line 269-320]:
    - Delegate to orchestrator
    - Collect results
    - Compute metrics

### 4. Trial Orchestration
- **File**: `src/harbor/orchestrators/local.py`
- **Class**: `LocalOrchestrator`
- **Key Methods**:
  - `run()` [Line 286-343]:
    - Create async tasks for all trials
    - Control concurrency with semaphore
    - Track progress
  - `_run_trial()` [Line 161-244]:
    - Execute single trial with progress updates
  - `_execute_trial_with_retries()` [Line 110-159]:
    - Retry logic with exponential backoff

### 5. Single Trial Execution
- **File**: `src/harbor/trial/trial.py`
- **Class**: `Trial`
- **Key Methods**:
  - `__init__(config)` [Line 77-144]:
    - Load task
    - Create agent (via AgentFactory)
    - Create environment (via EnvironmentFactory)
    - Set timeouts
  - `run()` [Line 319-396]:
    - **Main trial execution loop**
    - Setup → Run → Verify → Cleanup
  - `_setup_environment()`:
    - Start container/sandbox
  - `_setup_agent()`:
    - Install agent dependencies
  - `_execute_agent()` [Line 220-243]:
    - **Call agent.run() with timeout**
  - `_run_verification()` [Line 244-253]:
    - Run tests
    - Parse reward

### 6. Agent Execution
- **File**: `src/harbor/agents/installed/*.py`
- **Base Class**: `BaseAgent` (in `src/harbor/agents/base.py`)
- **Key Method**:
  - `async run(instruction, environment, context)`:
    - Each agent implements this differently
    - Oracle agent: reads solution
    - Claude Code: spawns claude-code CLI
    - OpenHands: spawns openhands
    - etc.

### 7. Environment Management
- **Files**: `src/harbor/environments/*.py`
- **Base Class**: `BaseEnvironment` (in `src/harbor/environments/base.py`)
- **Key Methods**:
  - `start(force_build)`: Start container
  - `exec(command)`: Execute command in container
  - `stop(delete)`: Stop and optionally delete container
  - `write_file()`, `read_file()`: File operations

### 8. Verification
- **File**: `src/harbor/verifier/verifier.py`
- **Class**: `Verifier`
- **Key Method**:
  - `verify()`:
    - Execute test.sh in environment
    - Read `/logs/verifier/reward.txt`
    - Return VerifierResult with rewards

## Data Flow

### Input (CLI Args) → JobConfig
```python
JobConfig {
    agents: [AgentConfig(name='oracle')],
    environment: EnvironmentConfig(type='e2b'),
    tasks: [TaskConfig(path='./examples/tasks/hello-world')],
    orchestrator: OrchestratorConfig(n_concurrent_trials=1),
    n_attempts: 1,
    timeout_multiplier: 1.0
}
```

### JobConfig → TrialConfig
```python
TrialConfig {
    trial_name: "hello-world__oracle__0",
    job_id: UUID,
    agent: AgentConfig(name='oracle'),
    environment: EnvironmentConfig(type='e2b'),
    task: TaskConfig(path='./examples/tasks/hello-world'),
    timeout_multiplier: 1.0
}
```

### Trial Execution → TrialResult
```python
TrialResult {
    trial_name: "hello-world__oracle__0",
    task_name: "hello-world",
    started_at: datetime,
    finished_at: datetime,
    agent_info: AgentInfo(name='oracle', version='1.0'),
    agent_result: AgentContext(...),  # What agent did
    verifier_result: VerifierResult(
        rewards: {"reward": 1.0},
        stdout: "...",
        stderr: "..."
    ),
    exception_info: None | ExceptionInfo
}
```

### TrialResults → JobResult
```python
JobResult {
    id: UUID,
    started_at: datetime,
    finished_at: datetime,
    stats: JobStats {
        evals: {
            "oracle__hello-world": {
                n_trials: 1,
                n_errors: 0,
                metrics: [{"mean": 1.0}],
                reward_stats: {...}
            }
        }
    }
}
```

## Key Abstractions

### Agent Protocol
```python
class BaseAgent(ABC):
    @abstractmethod
    async def setup(self, environment: BaseEnvironment) -> None:
        """Install dependencies, prepare agent"""

    @abstractmethod
    async def run(self, instruction: str, environment: BaseEnvironment,
                  context: AgentContext) -> None:
        """Execute the task"""
```

### Environment Protocol
```python
class BaseEnvironment(ABC):
    @abstractmethod
    async def start(self, force_build: bool = False) -> None:
        """Start the environment"""

    @abstractmethod
    async def exec(self, command: str, **kwargs) -> dict:
        """Execute command in environment"""

    @abstractmethod
    async def stop(self, delete: bool = True) -> None:
        """Stop environment"""
```

### Task Structure
```
task-directory/
├── task.toml           # Config (timeouts, resources)
├── instruction.md      # What the agent should do
├── environment/        # Dockerfile or env definition
│   └── Dockerfile
├── tests/              # Verification scripts
│   └── test.sh        # Must write reward to /logs/verifier/reward.txt
└── solution/           # Optional reference solution
    └── solve.sh
```

## Typical Execution Timeline

```
T+0s:   CLI parsing
T+0.1s: Job creation, load tasks
T+0.2s: Orchestrator creates trial configs
T+0.3s: Trial 1 starts
T+0.5s: Environment starts (e2b container spins up)
T+5s:   Environment ready
T+5.1s: Agent setup (install dependencies)
T+10s:  Agent setup complete
T+10.1s: Agent execution starts
T+30s:  Agent execution completes
T+30.1s: Verification starts (run tests)
T+35s:  Verification complete, reward=1.0
T+35.1s: Cleanup, save results
T+35.2s: Trial complete
T+35.3s: Job aggregates results, computes metrics
T+35.4s: Print results table, done
```

## For Your HumanLayer Framework

To integrate with Harbor, you'd want to hook into:

1. **Agent Level** - Wrap `BaseAgent`:
   ```python
   class HumanLayerAgent(BaseAgent):
       def __init__(self, underlying_agent, director, user):
           self.agent = HumanLayerAgentAdapter(underlying_agent)
           self.director = director
           self.user = user
           self.runner = HumanLayerRunner(self.agent, self.director, self.user)

       async def run(self, instruction, environment, context):
           # Run with supervision
           success, msg = await self.runner.run_async()
   ```

2. **Trial Level** - Add hooks:
   ```python
   trial.add_hook(TrialEvent.AGENT_START, on_agent_start)
   trial.add_hook(TrialEvent.AGENT_STEP, on_agent_step)  # If you add this
   ```

3. **Environment Level** - Intercept commands:
   ```python
   class SupervisedEnvironment(BaseEnvironment):
       async def exec(self, command, **kwargs):
           # Check with director before executing
           allowed, reason = self.director.should_allow(Action(command, "bash"))
           if not allowed:
               # Ask user
               ...
   ```
