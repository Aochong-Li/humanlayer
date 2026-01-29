"""
Agent-only workflow: autonomous agent solves task directly.

Run: python examples/run_agentonly.py
"""

import os
from pathlib import Path
import shutil
from humanlayer.sessions.agentonly import main as run_agentonly

# Setup paths
BASE_DIR = Path(__file__).parent.parent
os.chdir(BASE_DIR)

task_dir = Path("examples/tasks")
task_name = "dna-insert"

# Copy task from terminal-bench-2
src = BASE_DIR.parent / "terminal-bench-2" / task_name
dst = task_dir / task_name

if dst.exists():
    shutil.rmtree(dst)

shutil.copytree(str(src), str(dst))

# Set environment directory
env_dir = task_dir / task_name / "environment"
if env_dir.exists():
    os.environ["HUMANLAYER_CWD"] = str(env_dir)

# Run agent-only session
run_agentonly(
    task_dir=task_dir,
    task_name=task_name,
    max_steps=50,
    config_path="./src/humanlayer/config/agent_only.yaml",
    cwd=str(env_dir)
)
