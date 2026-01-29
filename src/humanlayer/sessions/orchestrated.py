"""
Run script for orchestrated user-agent sessions.

Usage:
    python -m humanlayer.sessions.orchestrated --task-dir <path> --task-name <name>
"""

import asyncio
import json
import os
import typer
from pathlib import Path

from humanlayer import package_dir
from humanlayer.agents.chat import ChatAgentConfig, ChatAgent
from humanlayer.environments import get_environment
from humanlayer.models import get_model
from humanlayer.users.default import User, UserConfig
from humanlayer.orchestrators.default import Orchestrator, OrchestratorConfig
from humanlayer.orchestrators.simple import SimpleOrchestrator, SimpleOrchestratorConfig
from humanlayer.sessions.utils import load_config, create_save_dir, save_messages, run_verification
from humanlayer.environments.utils.task import get_task_config

app = typer.Typer()


def save_task_tree(task_tree: dict, save_dir: Path):
    """Save task tree to the save directory."""
    save_path = save_dir / "task_tree.json"
    with open(save_path, "w") as f:
        json.dump(task_tree, f, indent=2)
    print(f"Task tree saved to: {save_path}")

async def _run_main(
    task_dir: Path,
    task_name: str,
    config_path: str,
    user_profile: str,
    max_steps: int,
    cwd: str,
    orchestrator_mode: str,
    progress_callback=None,
):
    """Async implementation of main logic."""
    config = load_config(config_path)

    async def report_progress(stage):
        if progress_callback:
            await progress_callback(task_name, stage)

    # Get task config
    task_config = get_task_config(task_dir / task_name)
    task, setup_config = task_config['instruction'], task_config['setup_config']

    # Environment
    env_config = config.get("env", {})
    env_config.update(setup_config.get('environment', {}))
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
        model_config = config.get("model", {})
        model_name = model_config.pop("model_name", None)
        if not model_name:
            raise ValueError("model_name required in config")
        model = get_model(model_name, model_config)

        # User
        user_cfg = config.get("user", {})
        user_cfg["user_profile"] = user_profile
        user_config = UserConfig(**user_cfg)
        user = User(model, env, user_config, task=task, max_steps=max_steps)

        # Agent
        agent_cfg = config.get("agent", {})
        agent_config = ChatAgentConfig(**agent_cfg)
        agent = ChatAgent(model, env, agent_config)

        # Orchestrator
        orch_cfg = config.get("orchestrator", {})
        orch_cfg["task_spec"] = task
        orch_cfg["max_turns"] = max_steps
        if os.path.exists(task_dir.parent / "task_tree.json"):
            orch_cfg["task_tree"] = json.load(open(task_dir.parent / task_name / "task_tree.json"))

        if orchestrator_mode == "default":
            orchestrator_config = OrchestratorConfig(**orch_cfg)

            orchestrator = Orchestrator(
                model=model,
                config=orchestrator_config,
                user=user,
                agent=agent,
                env=env,
            )
        elif orchestrator_mode == "simple":
            orchestrator_config = SimpleOrchestratorConfig(**orch_cfg)
            orchestrator = SimpleOrchestrator(
                model=model,
                config=orchestrator_config,
                user=user,
                agent=agent,
                env=env,
            )
        else:
            raise ValueError(f"Invalid orchestrator mode: {orchestrator_mode}")

        # Run
        print(f"\n{'='*60}")
        print(f"Task: {task}")
        print(f"User Profile: {user_profile}")
        print(f"Max Steps: {max_steps}")
        print(f"{'='*60}\n")

        await report_progress("run_task")
        history, task_tree = await orchestrator.run()
        print(f"\n{'='*60}")
        print(f"Completed in {orchestrator._turn_count - 1} turns")
        print(f"Task tree status: {'complete' if orchestrator.is_complete() else 'incomplete'}")
        print(f"{'='*60}\n")

        # Save history
        mode_name = "orchestrated" if orchestrator_mode == "default" else "orchestrated_simple"
        save_dir = create_save_dir(env.config.jobs_dir, task_name, mode_name)
        save_messages(history.messages, save_dir, "history.json")
        save_task_tree(task_tree, save_dir)

        # Run verification for non-local environments
        await run_verification(env, task_dir, task_name, save_dir, report_progress)

    finally:
        # Stop async environment if needed
        if hasattr(env, 'stop'):
            await env.stop()


@app.command()
def main(
    task_dir: Path,
    task_name: str,
    config_path: str = str(package_dir / "config" / "orchestrated.yaml"),
    user_profile: str = "A junior developer learning to code",
    max_steps: int = 100,
    cwd: str = "",
    orchestrator_mode: str = "default",
):
    """Run an orchestrated user-agent session on a task."""
    asyncio.run(_run_main(
        task_dir=task_dir,
        task_name=task_name,
        config_path=config_path,
        user_profile=user_profile,
        max_steps=max_steps,
        cwd=cwd,
        orchestrator_mode=orchestrator_mode,
    ))


if __name__ == "__main__":
    app()
