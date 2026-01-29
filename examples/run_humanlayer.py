"""
HumanLayer orchestrated workflow.

Run: python examples/run_humanlayer.py
"""

import os
import yaml
from pathlib import Path
import shutil
from humanlayer.sessions.orchestrated import main as run_orchestrated

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

# Run orchestrated session
run_orchestrated(
    task_dir=task_dir,
    task_src_dir=src,
    task_name=task_name,
    user_profile=user_profile,
    max_steps=100,
    config_path="./src/humanlayer/config/orchestrated.yaml",
    cwd=str(env_dir),
    orchestrator_mode="simple"
)
