"""
Test user-agent workflow with COBOL modernization task.

Run: python examples/run_humanlayer.py
"""

import os
from pathlib import Path

# Set working directory to humanlayer root
os.chdir("/home/al2644/research/codebase/agent/humanlayer")

# Read instruction from cobol task
task_dir = Path("examples/tasks/cobol-modernization")
instruction_file = task_dir / "instruction.md"


task = instruction_file.read_text()

# Set environment working directory to task environment
env_dir = task_dir / "environment"
if env_dir.exists():
    os.environ["HUMANLAYER_CWD"] = str(env_dir)

from humanlayer.sessions.useragent import main as run_useragent

run_useragent(
    task=task,
    user_profile="A developer with no COBOL experience and very limited coding background trying to modernize legacy code",
    config_path="./src/humanlayer/config/user_agent.yaml",
    cwd=str(env_dir)
)
