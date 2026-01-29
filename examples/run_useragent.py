"""
User-agent workflow: simulated user interacts with AI agent.

This is a simple user-agent session without orchestrator control.
The user LLM directly generates actions and communicates with the agent.

Run: python examples/run_useragent.py
"""

import os
import yaml
from pathlib import Path
import shutil
from humanlayer.sessions.useragent import main as run_useragent

# Setup paths
BASE_DIR = Path(__file__).parent.parent
os.chdir(BASE_DIR)

task_dir = Path("examples/tasks")
task_name = "portfolio-optimization"

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

# Load user profile
profiles_path = BASE_DIR / "src/humanlayer/config/user_profiles.yaml"
with open(profiles_path) as f:
    profiles = yaml.safe_load(f)
user_profile = profiles.get("vibe_coder", profiles["default"])

# Run user-agent session
run_useragent(
    task_dir=task_dir,
    task_name=task_name,
    user_profile=user_profile,
    user_behaviors="",
    max_steps=100,
    config_path="./src/humanlayer/config/user_agent.yaml",
    cwd=str(env_dir)
)
