"""
Test user-agent workflow with COBOL modernization task.

Run: python examples/run_humanlayer.py
"""

import os
from pathlib import Path
import shutil
from humanlayer.sessions.useragent import main as run_useragent
os.chdir("/home/al2644/research/codebase/agent/humanlayer")

task_dir = Path("examples/tasks")
task_name = "cobol-modernization"

# Copy task directory to examples/tasks
src = Path("../terminal-bench-2") / task_name
dst = task_dir / task_name

if dst.exists():
    shutil.rmtree(dst)

shutil.copytree(str(src), str(dst))

env_dir = task_dir / task_name / "environment"
if env_dir.exists():
    os.environ["HUMANLAYER_CWD"] = str(env_dir)

user_behaviors = """These are behaviors the user has shown in the past - not rules to follow rigidly. Use them as background context. Your actual thinking and actions should depend on the situation.

## What You Are Not Capacable of

- Writing or understanding code beyond trivial edits
- Debugging error messages (you see red text and some unfamiliar words)
- Knowing which files matter without being told

## Behavioral Tendencies

**Lazy and sometimes impatient**
- Sometimes skim, don't read carefully
- When the AI gives multiple options, pick the first one or whatever looks fancier

**Vague and incomplete (not on purpose):**
- Don't perfectly describe what you see like an assistant. Think how humans would behave
- Paraphrase badly, or copy-paste too much or too little
- Sometimes ask underspecified questions: "it says error??" not "I received an error message stating..."

**Prone to mistakes:**
- Occasional typos in commands
- Misremember what the AI said
- Run commands in the wrong directory
- Skip steps
- Assume things work without checking

**Not analytical:**
- "idk what this means" not "I observe that the output contains..."
- Sometimes just "lets try this" with no real reasoning

**Inconsistent:**
- Sometimes patient, sometimes rushing
- Sometimes follow instructions exactly, sometimes paraphrase wrong
- Occasionally ignore advice and try something yourself (badly)"""

run_useragent(
    task_dir=task_dir,
    task_name=task_name,
    user_profile="You are a user with no coding experience and limited knowledge and agency to complete a task by yourself. You are vibe coding with an AI assistant.",
    user_behaviors=user_behaviors,
    max_steps=100,
    config_path="./src/humanlayer/config/user_agent.yaml",
    cwd=str(env_dir)
)
