"""
Agent-only session: The agent solves tasks autonomously without user interaction.

Run: python -m humanlayer.sessions.agentonly --task-dir <path> --task-name <name>
"""

import asyncio
import re
import typer
from pathlib import Path
from dataclasses import dataclass

from jinja2 import StrictUndefined, Template
from pydantic import BaseModel

from humanlayer import package_dir
from humanlayer.environments import get_environment
from humanlayer.models import get_model
from humanlayer.sessions.history import SessionHistory, Message
from humanlayer.sessions.utils import load_config, format_error_observation, create_save_dir, save_messages, run_verification
from humanlayer.environments.utils.task import get_task_config

app = typer.Typer()


# ──────────────────────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────────────────────

class AgentOnlyConfig(BaseModel):
    system_template: str
    instance_template: str = ""
    think_tags: list[str] = ["<think>", "</think>"]
    action_tags: list[str] = ["<action>", "</action>"]
    exit_code: str = "[TASK COMPLETE]"


# ──────────────────────────────────────────────────────────────
# Agent Action
# ──────────────────────────────────────────────────────────────

class AgentFormatError(Exception):
    """LLM output didn't match expected format."""


@dataclass
class AgentAction:
    type: str  # "execute" or "exit"
    reasoning: str = ""
    content: str = ""  # the bash command or exit message


class AgentActionParser:
    """Parses LLM output into AgentAction."""

    BASH_PATTERN = re.compile(r"```bash\s*\n(.*?)\n```", re.DOTALL)

    def __init__(self, config: AgentOnlyConfig):
        self.config = config
        self._think_pattern = re.compile(
            rf"{re.escape(config.think_tags[0])}(.*?){re.escape(config.think_tags[1])}",
            re.DOTALL
        )
        self._action_pattern = re.compile(
            rf"{re.escape(config.action_tags[0])}(.*?){re.escape(config.action_tags[1])}",
            re.DOTALL
        )

    def parse(self, content: str) -> AgentAction:
        # Extract reasoning (optional for agent)
        think_match = self._think_pattern.search(content)
        reasoning = think_match.group(1).strip() if think_match else ""

        # Extract action block
        action_match = self._action_pattern.search(content)
        if not action_match:
            raise AgentFormatError("Missing <action>...</action> block")

        action_content = action_match.group(1).strip()

        # Check for exit
        if self.config.exit_code in action_content:
            return AgentAction(type="exit", reasoning=reasoning, content=action_content)

        # Extract bash command
        bash_matches = self.BASH_PATTERN.findall(action_content)
        if len(bash_matches) == 1:
            return AgentAction(type="execute", reasoning=reasoning, content=bash_matches[0].strip())
        elif len(bash_matches) > 1:
            raise AgentFormatError(f"Expected exactly one bash block, got {len(bash_matches)}")
        else:
            raise AgentFormatError("No bash block found in action. Use ```bash\\ncommand\\n```")


# ──────────────────────────────────────────────────────────────
# Agent
# ──────────────────────────────────────────────────────────────

class AutonomousAgent:
    """An agent that can execute commands directly."""

    def __init__(self, model, env, config: AgentOnlyConfig, **kwargs):
        self.model = model
        self.env = env
        self.config = config
        self.parser = AgentActionParser(config)
        self.extra_template_vars = kwargs

    def step(self, messages: list[dict]) -> str:
        full_messages = self._build_prompt(messages)
        response = self.model.query(full_messages)
        return response["content"]

    def parse(self, content: str) -> AgentAction:
        return self.parser.parse(content)

    async def execute(self, command: str) -> dict:
        try:
            result = await self.env.execute(command)
            return result if isinstance(result, dict) else {'output': str(result), 'returncode': 1}
        except (TimeoutError,) as e:
            output = getattr(e, "output", b"")
            if isinstance(output, bytes):
                output = output.decode("utf-8", errors="replace")
            return {'output': f"Timeout executing: {command}\n{output}", 'returncode': 1}
        except Exception as e:
            return {'output': f"Error executing: {command}\n{e}", 'returncode': 1}

    def _build_prompt(self, messages: list[dict]) -> list[dict]:
        prompt = []
        system = self._render(self.config.system_template)
        if system:
            prompt.append({"role": "system", "content": system})
        if self.config.instance_template:
            prompt.append({"role": "user", "content": self._render(self.config.instance_template)})
        prompt.extend(messages)
        return prompt

    def _render(self, template: str, **extra) -> str:
        vars = {
            **self.config.model_dump(),
            **self.env.get_template_vars(),
            **self.model.get_template_vars(),
            **self.extra_template_vars,
            **extra,
        }
        return Template(template, undefined=StrictUndefined).render(**vars)


# ──────────────────────────────────────────────────────────────
# Session
# ──────────────────────────────────────────────────────────────

async def run_agent_session(agent: AutonomousAgent, task: str, max_steps: int = 100, save_dir: Path = None):
    """Run an agent-only session where the agent solves the task autonomously."""
    chat_history = SessionHistory()
    print(f"\n{'='*60}")
    print(f"Task: {task}")
    print(f"{'='*60}\n")

    for step in range(1, max_steps + 1):
        import pdb; pdb.set_trace()
        try:
            content = agent.step(chat_history.get("agent"))
            action = agent.parse(content)
        except AgentFormatError as e:
            print(f"\n[Turn: {step}/{max_steps}] [Format error]: {e}")
            observation = format_error_observation(
                "FORMAT ERROR",
                str(e),
                "Your response must include <think>...</think> (optional) and <action>...</action> blocks. "
                "Inside <action>, use exactly one ```bash block or the exit code.",
            )
            chat_history.append(Message(
                role="environment",
                response=observation,
                visible_to=["agent"],
            ))
            continue

        if action.reasoning:
            print(f"\n[Agent thinks]: {action.reasoning[:300]}...")

        if action.type == "execute":
            print(f"[Turn: {step}/{max_steps}] [Agent executes]: {action.content}")
            chat_history.append(Message(
                role="agent",
                reasoning=action.reasoning,
                action=action.content,
                visible_to=["agent"],
            ))

            result = await agent.execute(action.content)
            output = result.get("output", "")
            returncode = result.get("returncode", 1)

            status = "Output" if returncode == 0 else "Error"
            print(f"[{status}]: {output[:1000] if output else '(empty)'}")

            if returncode == 0 and not output:
                output = "(command completed successfully with no output)"

            chat_history.append(Message(
                role="environment",
                response=output,
                visible_to=["agent"],
            ))

        if action.type == "exit":
            print(f"[Turn: {step}/{max_steps}] [Done]: {action.content}")
            chat_history.append(Message(
                role="agent",
                reasoning=action.reasoning,
                response=action.content,
                visible_to=["agent"],
            ))
            print(f"\n{'='*60}")
            print(f"Completed in {step} turns")
            print(f"{'='*60}\n")
            return chat_history
        
        save_messages(chat_history.messages, save_dir, "chat_history.json")

    print(f"[Warning]: Reached max steps ({max_steps})")
    observation = format_error_observation(
        "STEP LIMIT",
        f"Reached maximum steps ({max_steps})",
        "Task incomplete.",
    )
    chat_history.append(Message(
        role="environment",
        response=observation,
        visible_to=["agent"],
    ))
    return chat_history


async def _run_main(
    task_dir: Path,
    task_name: str,
    config_path: str,
    max_steps: int,
    cwd: str,
    progress_callback=None,
):
    """Async implementation of main logic."""
    config = load_config(config_path)

    async def report_progress(stage):
        if progress_callback:
            await progress_callback(task_name, stage)

    # Environment
    task_config = get_task_config(task_dir / task_name)
    task, setup_config = task_config['instruction'], task_config['setup_config']

    env_config = config.get("env", {})
    env_config.update(setup_config.get('environment', {}))

    # Config for E2B
    env_config["environment_dir"] = (task_dir / task_name / "environment")
    env_config["environment_name"] = task_name

    if cwd:
        env_config["cwd"] = cwd
    env = get_environment(env_config, default_type="local")

    # Start async environment if needed
    if hasattr(env, 'start'):
        await report_progress("launching sandbox")
        await env.start()

    try:
        import pdb; pdb.set_trace()
        # Model
        model_config = config.get("model", {})
        model_name = model_config.pop("model_name", None)
        if not model_name:
            raise ValueError("model_name required in config")
        model = get_model(model_name, model_config)

        # Agent
        agent_config = AgentOnlyConfig(**config.get("agent", {}))
        agent = AutonomousAgent(model, env, agent_config, task=task, max_steps=max_steps)

        # Run session
        save_dir = create_save_dir(env.config.jobs_dir, task_name, "agentonly")
        
        await report_progress("running agent")
        chat_history = await run_agent_session(agent, task, max_steps, save_dir)

        # Save history
        save_messages(chat_history.messages, save_dir, "chat_history.json")

        # Run verification for non-local environments
        await run_verification(env, task_dir, task_name, save_dir, report_progress)

    finally:
        if hasattr(env, 'stop'):
            await env.stop()

@app.command()
def main(
    task_dir: Path,
    task_name: str,
    config_path: str = str(package_dir / "config" / "agent_only.yaml"),
    max_steps: int = 100,
    cwd: str = ""
):
    """Run an agent-only session on a task.

    The agent autonomously solves the task without user interaction.
    """
    asyncio.run(_run_main(
        task_dir=task_dir,
        task_name=task_name,
        config_path=config_path,
        max_steps=max_steps,
        cwd=cwd,
    ))


if __name__ == "__main__":
    app()
