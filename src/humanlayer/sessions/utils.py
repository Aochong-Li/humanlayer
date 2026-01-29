"""
Shared utilities for session runners.
"""

import json
import yaml
from datetime import datetime
from pathlib import Path


def load_config(path: str) -> dict:
    """Load YAML configuration file."""
    with open(path) as f:
        return yaml.safe_load(f)


def format_error_observation(error_type: str, details: str, hint: str = "") -> str:
    """Format an error as a structured observation."""
    parts = [f"[{error_type}]", details]
    if hint:
        parts.append(f"Hint: {hint}")
    return "\n".join(parts)


def create_save_dir(jobs_dir: str, task_name: str, mode: str) -> Path:
    """Create timestamped directory for saving session results.

    Args:
        jobs_dir: Base jobs directory
        task_name: Name of the task
        mode: Session mode (e.g., "agentonly", "useragent", "orchestrated_simple")

    Returns:
        Path to the created directory
    """
    timestamp = datetime.now().strftime("%m-%d-%H:%M:%S")
    save_path = Path(jobs_dir) / task_name / mode / timestamp
    save_path.mkdir(parents=True, exist_ok=True)
    return save_path


def save_messages(messages: list, save_path: Path, filename: str = "history.json"):
    """Save session messages to JSON file.

    Args:
        messages: List of Message objects with role, visible_to, reasoning, action, response
        save_path: Directory to save to
        filename: Output filename
    """
    messages_data = [
        {
            "role": msg.role,
            "visible_to": msg.visible_to,
            "reasoning": msg.reasoning,
            "action": msg.action,
            "response": msg.response,
        }
        for msg in messages
    ]

    history_file = save_path / filename
    with open(history_file, "w") as f:
        json.dump(messages_data, f, indent=2)

    print(f"History saved to: {history_file}")
    return history_file


async def run_verification(env, task_dir: Path, task_name: str, save_dir: Path, report_progress=None):
    """Run verification tests for non-local environments.

    Args:
        env: Environment instance with upload_dir/download_dir methods
        task_dir: Base task directory
        task_name: Name of the task
        save_dir: Directory to save results
        report_progress: Optional async callback for progress updates

    Returns:
        dict with verification results, or None if not applicable
    """
    if not (hasattr(env, 'upload_dir') and hasattr(env, 'download_dir')):
        return None

    print(f"\n{'='*60}")
    print("Running verification...")
    print(f"{'='*60}\n")

    if report_progress:
        await report_progress("running verification")

    # Upload tests directory
    tests_dir = task_dir / task_name / "tests"
    work_dir = env.get_work_dir() if hasattr(env, 'get_work_dir') else "/app"

    if tests_dir.exists():
        print(f"Uploading tests from {tests_dir}")
        await env.upload_dir(tests_dir, "/tests")

    # Create logs directory and run tests
    await env.execute("mkdir -p /logs/verifier")
    test_script = tests_dir / "test.sh"
    result_data = None

    if test_script.exists():
        print(f"Running test script in {work_dir}...")
        result = await env.execute("bash /tests/test.sh", cwd=work_dir)
        print(f"Test output:\n{result.get('output', '')}")

        # Read the reward/result
        reward_result = await env.execute("cat /logs/verifier/reward.txt 2>/dev/null || echo 0")
        reward = reward_result.get('output', '0').strip()

        # Save result.json
        result_data = {
            "success": int(reward) if reward.isdigit() else 0,
            "test_output": result.get('output', ''),
            "returncode": result.get('returncode', 1)
        }
        result_json_path = save_dir / "result.json"
        with open(result_json_path, 'w') as f:
            json.dump(result_data, f, indent=2)
        print(f"\n{'='*60}")
        print(f"Verification result: {result_data['success']}")
        print(f"Result saved to: {result_json_path}")
        print(f"{'='*60}\n")

    # Download environment directory
    download_path = save_dir / "environment_snapshot"
    print(f"Downloading environment to: {download_path}")
    if report_progress:
        await report_progress("download")
    await env.download_dir(target_dir=download_path)

    return result_data
