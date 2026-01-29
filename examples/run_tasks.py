"""
Unified task runner for all modes.

Usage:
    python examples/run_tasks.py \
        portfolio-optimization cobol-modernization build-pmars break-filter-js-from-html build-cython-ext multi-source-data-merger count-dataset-tokens dna-insert git-leak-recovery mailman\
        -m agentonly \
        -n 5 \
        --max-steps 50 \
        --orchestrator-mode simple
"""

import asyncio
import json
import yaml
import shutil
import os
import sys
from pathlib import Path
from datetime import datetime
import typer

from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn, BarColumn, MofNCompleteColumn
from rich.console import Console
from rich.text import Text

app = typer.Typer()


class ConditionalBarColumn(BarColumn):
    def render(self, task):
        if task.total is None:
            return Text("")
        return super().render(task)

class ConditionalMofNCompleteColumn(MofNCompleteColumn):
    def render(self, task):
        if task.total is None:
            return Text("")
        return super().render(task)


def mode_to_dirname(mode: str, orchestrator_mode: str = None) -> str:
    """Convert mode to job directory name"""
    if mode == "orchestrated":
        return f"orchestrated_{orchestrator_mode}"
    return mode


async def run_single_task(
    task_name: str,
    mode: str,
    task_dir: Path,
    config_path: str,
    user_profile: str,
    max_steps: int,
    orchestrator_mode: str,
    progress_callback,
    base_dir: Path,
):
    """Run a single task as subprocess to isolate output"""

    result = {
        "task": task_name,
        "mode": mode,
        "success": 0,
        "error": None,
        "stage": "setup",
        "timestamp": datetime.now().isoformat(),
        "job_dir": None
    }
    output = ""

    try:
        await progress_callback(task_name, "launch_sandbox")

        # Build command based on mode
        module_map = {
            "agentonly": "humanlayer.sessions.agentonly",
            "useragent": "humanlayer.sessions.useragent",
            "orchestrated": "humanlayer.sessions.orchestrated",
            "oracle": "humanlayer.sessions.oracle",
        }

        cmd = [
            sys.executable, "-m", module_map[mode],
            str(task_dir), task_name,
            "--config-path", config_path,
        ]

        # Add mode-specific arguments
        if mode != "oracle":
            cmd.extend(["--max-steps", str(max_steps)])

        if mode in ["useragent", "orchestrated"]:
            cmd.extend(["--user-profile", user_profile])

        if mode == "orchestrated":
            cmd.extend(["--orchestrator-mode", orchestrator_mode])

        # Set environment
        env = os.environ.copy()
        env_dir = task_dir / task_name / "environment"
        if env_dir.exists():
            env["HUMANLAYER_CWD"] = str(env_dir)

        await progress_callback(task_name, "run_task")

        # Run as subprocess with output captured (not displayed)
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=env,
        )
        stdout, _ = await proc.communicate()
        output = stdout.decode("utf-8", errors="replace") if stdout else ""

        # Find latest job directory
        jobs_base = base_dir / "examples/jobs" / task_name / mode_to_dirname(mode, orchestrator_mode)
        if jobs_base.exists() and list(jobs_base.glob("*")):
            latest_job = max(jobs_base.glob("*"), key=lambda p: p.stat().st_mtime)
            result["job_dir"] = str(latest_job.relative_to(base_dir))

            # Extract model name from config
            model_name = "unknown"
            try:
                if config_path and os.path.exists(config_path):
                    with open(config_path) as f:
                        cfg = yaml.safe_load(f)
                        model_name = cfg.get("model", {}).get("model_name", "unknown")
            except Exception:
                pass

            # Save raw output to output.log
            with open(latest_job / "output.log", "w") as f:
                f.write(output)

            # Save metadata to config.json
            run_config = {
                "task": task_name,
                "mode": mode,
                "model_name": model_name,
                "returncode": proc.returncode,
            }
            with open(latest_job / "config.json", "w") as f:
                json.dump(run_config, f, indent=2)

            # Read test result
            result_file = latest_job / "result.json"
            if result_file.exists():
                with open(result_file) as f:
                    test_result = json.load(f)
                    result["success"] = test_result.get("success", 0)

        result["stage"] = "complete"

    except Exception as e:
        result["error"] = str(e)
        result["stage"] = "failed"

        # Find or create job directory for error logs
        jobs_base = base_dir / "examples/jobs" / task_name / mode_to_dirname(mode, orchestrator_mode)

        if jobs_base.exists() and list(jobs_base.glob("*")):
            job_dir = max(jobs_base.glob("*"), key=lambda p: p.stat().st_mtime)
        else:
            timestamp = datetime.now().strftime("%m-%d-%H:%M:%S")
            job_dir = jobs_base / timestamp
            job_dir.mkdir(parents=True, exist_ok=True)

        result["job_dir"] = str(job_dir.relative_to(base_dir))

        # Extract model name from config (for error case too)
        model_name = "unknown"
        try:
            if config_path and os.path.exists(config_path):
                with open(config_path) as f:
                    cfg = yaml.safe_load(f)
                    model_name = cfg.get("model", {}).get("model_name", "unknown")
        except Exception:
            pass

        # Save raw output to output.log
        with open(job_dir / "output.log", "w") as f:
            f.write(output)

        # Save metadata to config.json
        run_config = {
            "task": task_name,
            "mode": mode,
            "model_name": model_name,
            "error": str(e),
        }
        with open(job_dir / "config.json", "w") as f:
            json.dump(run_config, f, indent=2)

    return result


async def run_tasks_with_progress(jobs, num_parallel, **kwargs):
    """Run tasks in parallel with rich progress display"""

    console = Console()

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        ConditionalBarColumn(),
        ConditionalMofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:

        # Add total progress bar
        total_id = progress.add_task("[bold green]Total Progress[/bold green]", total=len(jobs))

        # Run with semaphore
        semaphore = asyncio.Semaphore(num_parallel)

        async def run_with_limit(task_name, mode):
            async with semaphore:
                # Add task to progress when it starts running
                # Set total=None for indeterminate progress (pulsing bar)
                task_id = progress.add_task(
                    f"[cyan]{task_name}[/cyan] ({mode}) - setup",
                    total=None
                )

                async def update_progress(t_name, stage):
                    progress.update(
                        task_id,
                        description=f"[cyan]{task_name}[/cyan] ({mode}) - [yellow]{stage}[/yellow]"
                    )

                try:
                    # Determine config path if not provided
                    config_path = kwargs.get("config_path")
                    if not config_path:
                        base_dir = kwargs.get("base_dir")
                        config_map = {
                            "agentonly": "agent_only.yaml",
                            "useragent": "user_agent.yaml",
                            "orchestrated": "orchestrated.yaml",
                            "oracle": "agent_only.yaml"
                        }
                        config_path = str(base_dir / "src/humanlayer/config" / config_map[mode])

                    return await run_single_task(
                        task_name, mode,
                        progress_callback=update_progress,
                        config_path=config_path,
                        base_dir=kwargs.get("base_dir"),
                        **{k: v for k, v in kwargs.items() if k not in ["config_path", "base_dir"]}
                    )
                finally:
                    # Remove task from progress display when done (success or error)
                    progress.remove_task(task_id)
                    # Advance total progress
                    progress.advance(total_id)

        results = await asyncio.gather(
            *[run_with_limit(task_name, mode) for task_name, mode in jobs],
            return_exceptions=True
        )

        # Handle exceptions returned from gather
        processed_results = []
        for i, res in enumerate(results):
            task_name, mode = jobs[i]
            if isinstance(res, Exception):
                processed_results.append({
                    "task": task_name,
                    "mode": mode,
                    "success": 0,
                    "error": str(res),
                    "stage": "failed",
                    "timestamp": datetime.now().isoformat()
                })
            else:
                processed_results.append(res)

    return processed_results


@app.command()
def main(
    tasks: list[str] = typer.Argument(..., help="List of task names to run"),
    modes: list[str] = typer.Option(["orchestrated"], "--mode", "-m", help="Modes: agentonly, useragent, orchestrated, or oracle"),
    num_parallel: int = typer.Option(1, "--num-parallel", "-n", help="Number of tasks to run in parallel"),
    max_steps: int = typer.Option(100, "--max-steps", help="Maximum steps per task"),
    orchestrator_mode: str = typer.Option("simple", "--orchestrator-mode", help="Orchestrator mode: simple or default"),
    config_path: str = typer.Option(None, "--config", help="Path to config YAML file"),
):
    """Run multiple tasks in parallel with the specified modes."""

    console = Console()
    BASE_DIR = Path(__file__).parent.parent

    # Validate modes
    valid_modes = ["agentonly", "useragent", "orchestrated", "oracle"]
    for mode in modes:
        if mode not in valid_modes:
            console.print(f"[red]Error: Invalid mode '{mode}'. Must be one of: {', '.join(valid_modes)}[/red]")
            raise typer.Exit(1)

    # Prepare jobs and copy tasks
    tasks = list(set(tasks))
    jobs = []
    console.print(f"\n[bold]Preparing workspaces for {len(tasks)} tasks...[/bold]")
    
    task_dir = BASE_DIR / "examples/tasks"
    src_dir = BASE_DIR.parent / "terminal-bench-2"

    for task in tasks:
        # Verify source exists
        src = src_dir / task
        if not src.exists():
            console.print(f"  [red]✗ {task} - not found in {src_dir}[/red]")
            raise typer.Exit(1)

        # Copy task to workspace ONCE per task
        dst = task_dir / task
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        console.print(f"  [green]✓[/green] {task}")

        for mode in modes:
            jobs.append((task, mode))

    # Load user profile (for user-based modes)
    user_profile = ""
    profiles_path = BASE_DIR / "src/humanlayer/config/user_profiles.yaml"
    with open(profiles_path) as f:
        profiles = yaml.safe_load(f)
    user_profile = profiles.get("vibe_coder", profiles["default"])

    # Run tasks
    console.print(f"\n[bold]Running {len(jobs)} jobs in {len(modes)} modes (max {num_parallel} parallel jobs)[/bold]\n")

    results = asyncio.run(run_tasks_with_progress(
        jobs=jobs,
        num_parallel=num_parallel,
        task_dir=task_dir,
        config_path=config_path,
        user_profile=user_profile,
        max_steps=max_steps,
        orchestrator_mode=orchestrator_mode,
        base_dir=BASE_DIR,
    ))

    # Save summary
    timestamp = datetime.now().strftime("%m-%d-%H:%M:%S")
    summary_dir = BASE_DIR / "examples/jobs/summary" / timestamp
    summary_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "timestamp": timestamp,
        "modes": modes,
        "orchestrator_mode": orchestrator_mode,
        "total_jobs": len(jobs),
        "successful": sum(1 for r in results if r.get("success") == 1),
        "failed": sum(1 for r in results if r.get("success") == 0 or r.get("error")),
        "results": results
    }

    summary_file = summary_dir / "summary.json"
    with open(summary_file, "w") as f:
        json.dump(summary, f, indent=2)

    # Print summary
    console.print(f"\n[bold green]Summary:[/bold green]")
    console.print(f"  Total: {summary['total_jobs']}")
    console.print(f"  [green]Successful: {summary['successful']}[/green]")
    console.print(f"  [red]Failed: {summary['failed']}[/red]")
    console.print(f"\n  Summary saved to: [cyan]{summary_file}[/cyan]\n")

    # Print per-task results
    console.print("[bold]Job Results:[/bold]")
    for r in results:
        status = "[green]✓[/green]" if r.get("success") == 1 else "[red]✗[/red]"
        job_dir = r.get("job_dir", "N/A")
        error = f" - {r.get('error')}" if r.get("error") else ""
        console.print(f"  {status} {r['task']} ({r['mode']}): {job_dir}{error}")

    console.print()


if __name__ == "__main__":
    app()
