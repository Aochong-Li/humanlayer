import tomllib
from pathlib import Path


def get_task_config(task_dir: Path) -> dict:
    instruction_path = task_dir / "instruction.md"
    setup_config_path = task_dir / "task.toml"
    
    instruction = instruction_path.read_text()
    with open(setup_config_path, "rb") as f:
        setup_config = tomllib.load(f)

    return {
        "instruction": instruction,
        "setup_config": setup_config    
    }