"""
Oracle session: Run gold standard solution without agent.

This mode launches the sandbox, runs the solution script directly,
and performs verification. Used for testing infrastructure and
establishing baseline success rates.

Run: python -m humanlayer.sessions.oracle --task-dir <path> --task-name <name>
"""

import asyncio
import json
import typer
from pathlib import Path

from humanlayer import package_dir
from humanlayer.environments import get_environment
from humanlayer.environments.utils.task import get_task_config
from humanlayer.sessions.utils import load_config, create_save_dir

app = typer.Typer()


async def _run_main(
    task_dir: Path,
    task_name: str,
    config_path: str,
    cwd: str,
    progress_callback=None,
):
    """Async implementation of oracle logic."""
    config = load_config(config_path)

    async def report_progress(stage):
        if progress_callback:
            await progress_callback(task_name, stage)

    # Environment
    task_config = get_task_config(task_dir / task_name)
    task, setup_config = task_config['instruction'], task_config['setup_config']

    env_config = config.get("env", {})
    env_config.update(setup_config.get('environment', {}))

    # Config for E2B/Docker
    env_config["environment_dir"] = (task_dir / task_name / "environment")
    env_config["environment_name"] = task_name

    if cwd:
        env_config["cwd"] = cwd
    env = get_environment(env_config, default_type="local")

    # Start async environment if needed
    if hasattr(env, 'start'):
        await report_progress("launch_sandbox")
        await env.start()

    try:
        print(f"\n{'='*60}")
        print(f"Oracle Run: {task_name}")
        print(f"Task: {task}")
        print(f"{'='*60}\n")

        # Create save directory
        save_dir = create_save_dir(env_config.get("jobs_dir", "examples/jobs"), task_name, "oracle")

        # Upload and run solution (for non-local environments)
        if hasattr(env, 'upload_dir') and hasattr(env, 'download_dir'):
            solution_dir = task_dir / task_name / "solution"
            tests_dir = task_dir / task_name / "tests"

            # Get working directory
            work_dir = env.get_work_dir() if hasattr(env, 'get_work_dir') else "/app"

            # Upload solution
            if solution_dir.exists():
                print(f"Uploading solution from {solution_dir}")
                await env.upload_dir(solution_dir, "/solution")

                # Run solution script
                solve_script = solution_dir / "solve.sh"
                if solve_script.exists():
                    await report_progress("run_task")
                    print(f"Running solution script in {work_dir}...")
                    result = await env.execute("bash /solution/solve.sh", cwd=work_dir)
                    print(f"Solution output:\n{result.get('output', '')}")
                    print(f"Solution return code: {result.get('returncode', 1)}")

            # Run verification
            print(f"\n{'='*60}")
            print("Running verification...")
            print(f"{'='*60}\n")

            if tests_dir.exists():
                print(f"Uploading tests from {tests_dir}")
                await env.upload_dir(tests_dir, "/tests")

            # Create logs directory and run tests
            await report_progress("verification")
            await env.execute("mkdir -p /logs/verifier")
            test_script = tests_dir / "test.sh"

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
                    "returncode": result.get('returncode', 1),
                    "verify": result.get('output', '')
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
            await report_progress("download")
            print(f"Downloading environment to: {download_path}")
            await env.download_dir(target_dir=download_path)

        else:
            # For local environments, just note that oracle would run solution
            print("Local environment detected. Oracle mode requires remote environment (e2b/docker).")
            result_data = {
                "success": 0,
                "error": "Oracle mode requires remote environment",
                "test_output": "",
                "returncode": 1,
                "verify": ""
            }
            result_json_path = save_dir / "result.json"
            with open(result_json_path, 'w') as f:
                json.dump(result_data, f, indent=2)

        print(f"\n{'='*60}")
        print("Oracle run completed")
        print(f"{'='*60}\n")

    finally:
        if hasattr(env, 'stop'):
            await env.stop()


@app.command()
def main(
    task_dir: Path,
    task_name: str,
    config_path: str = str(package_dir / "config" / "agent_only.yaml"),
    cwd: str = ""
):
    """Run oracle session on a task.

    Oracle mode runs the gold standard solution without any agent interaction.
    """
    asyncio.run(_run_main(
        task_dir=task_dir,
        task_name=task_name,
        config_path=config_path,
        cwd=cwd,
    ))


if __name__ == "__main__":
    app()
