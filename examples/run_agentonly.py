"""
Test agent-only workflow with COBOL modernization task.

This runs an autonomous agent that solves the task directly,
without any simulated user in the loop.

Run: python examples/run_agentonly.py
"""

import os
from pathlib import Path
import shutil
from humanlayer.sessions.agentonly import main as run_agentonly

os.chdir("/share/goyal/mog29/tb_collab/humanlayer")

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

run_agentonly(
    task_dir=task_dir,
    task_name=task_name,
    max_steps=100,
    config_path="./src/humanlayer/config/agent_only.yaml",
    cwd=str(env_dir)
)
