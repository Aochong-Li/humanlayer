import asyncio
import json
import yaml
import traceback
import typer
from datetime import datetime
from pathlib import Path

from humanlayer import package_dir
from humanlayer.agents.chat import ChatAgentConfig as AgentConfig, ChatAgent as Agent
from humanlayer.environments import get_environment
from humanlayer.models import get_model
from humanlayer.users.default import User, UserConfig, FormatError, ExecutionTimeout
from humanlayer.sessions.history import ChatHistory, Message
from humanlayer.environments.utils.task import get_task_config

app = typer.Typer()


def load_config(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def format_error_observation(error_type: str, details: str, hint: str = "") -> str:
    """Format an error as a structured observation for the user."""
    parts = [f"[{error_type}]", details]
    if hint:
        parts.append(f"Hint: {hint}")
    return "\n".join(parts)


def save_chat_history(chat_history: ChatHistory, save_dir: str):
    """Save chat history to jobs/{MM}-{DD}-{HH}/chat_history.json"""
    timestamp = datetime.now().strftime("%m-%d-%H:%M:%S")
    save_dir = Path(save_dir) / timestamp
    save_dir.mkdir(parents=True, exist_ok=True)

    # Convert messages to dicts
    messages_data = [
        {
            "role": msg.role,
            "visible_to": msg.visible_to,
            "reasoning": msg.reasoning,
            "action": msg.action,
            "response": msg.response,
        }
        for msg in chat_history.messages
    ]

    save_path = save_dir / "chat_history.json"
    with open(save_path, "w") as f:
        json.dump(messages_data, f, indent=2)

    print(f"Chat history saved to: {save_path}")


async def run_session(user: User, agent: Agent, task: str, max_steps: int = 100):
    chat_history = ChatHistory()

    print(f"\n{'='*60}")
    print(f"Task: {task}")
    print(f"{'='*60}\n")

    for step in range(1, max_steps + 1):
        try:
            content = user.query(chat_history.get("user"))
            action = user.parse(content)
        except FormatError as e:
            print(f"\n[Turn: {step}/{max_steps}] [Format error]: {e}")
            observation = format_error_observation(
                "ERROR:",
                str(e),
                "Note: Your response must include <think>...</think> and <response>...</response> blocks. "
                "Inside <response>, use exactly one ```bash or ```request block.",
            )
            chat_history.append(Message(
                role="environment",
                response=observation,
                visible_to=["user"],
            ))
            continue

        if action.reasoning:
            print(f"\n[User thinks]: {action.reasoning[:200]}...")

        if action.type == "request":
            print(f"[Turn: {step}/{max_steps}] [User requests]: {action.content}")
            chat_history.append(Message(
                role="user",
                reasoning=action.reasoning,
                response=action.content,
                visible_to=["user", "agent"],
            ))

            response = agent.query(chat_history.get("agent"))
            print(f"[Agent]: {response}")
            chat_history.append(Message(
                role="agent",
                response=response,
                visible_to=["user", "agent"],
            ))

        elif action.type == "execute":
            print(f"[Turn: {step}/{max_steps}] [User executes]: {action.content}")
            chat_history.append(Message(
                role="user",
                reasoning=action.reasoning,
                action=action.content,
                visible_to=["user"],
            ))

            try:
                result = await user.execute(action.content)
                output = result.get("output", "")
                returncode = result.get("returncode", 1)
            except ExecutionTimeout as e:
                output = format_error_observation(
                    "TIMEOUT ERROR:",
                    f"Command timed out: {action.content}"
                )
                returncode = 1
            except Exception as e:
                output = format_error_observation(
                    "EXECUTION ERROR:",
                    f"Command: {action.content}\nError: {e}"
                )
                returncode = 1

            status = "Output" if returncode == 0 else "Error"
            print(f"[{status}]: {output[:1000] if output else '(empty)'}")

            if returncode == 0 and not output:
                output = "(command completed successfully with no output)"
            chat_history.append(Message(
                role="environment",
                response=output,
                visible_to=["user"],
            ))

        elif action.type == "exit":
            print(f"[Turn: {step}/{max_steps}] [Done]: {action.content}")
            chat_history.append(Message(
                role="user",
                response=action.content,
                visible_to=["user", "agent"],
            ))
            print(f"\n{'='*60}")
            print(f"Completed in {step} turns")
            print(f"{'='*60}\n")
            await user.env.stop()
            return chat_history

    print(f"[Warning]: Reached max steps ({max_steps})")
    observation = format_error_observation(
        "STEP LIMIT",
        f"Reached maximum steps ({max_steps})",
        "Task incomplete. Consider simplifying the approach.",
    )
    chat_history.append(Message(
        role="environment",
        response=observation,
        visible_to=["user"],
    ))
    await user.env.stop()
    return chat_history

async def _run_main(
    task_dir: Path,
    task_name: str,
    config_path: str,
    user_profile: str,
    user_behaviors: str,
    max_steps: int,
    cwd: str,
):
    """Async implementation of main logic."""
    config = load_config(config_path)

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

    # Start async environment if needed (e.g., E2B)
    if hasattr(env, 'start'):
        await env.start()

    try:
        # Model
        model_config = config.get("model", {})
        model_name = model_config.pop("model_name", None)
        if not model_name:
            raise ValueError("model_name required in config")
        model = get_model(model_name, model_config)

        # Agent & User
        agent_config = AgentConfig(**config.get("agent", {}))
        agent = Agent(model, env, agent_config)

        user_config = UserConfig(**{
            **config.get("user", {}),
            "user_profile": user_profile,
            "user_behaviors": user_behaviors,
            }
        )
        user = User(model, env, user_config, **{
            "task": task,
            "max_steps": max_steps,
        })

        # Run session and save history
        chat_history = await run_session(user, agent, task, max_steps)
        save_dir = env.config.jobs_dir + "/" + task_name
        save_chat_history(chat_history, save_dir)

    finally:
        # Stop async environment if needed
        if hasattr(env, 'stop'):
            await env.stop()


@app.command()
def main(
    task_dir: Path,
    task_name: str,
    config_path: str = str(package_dir / "config" / "user_agent.yaml"),
    user_profile: str = "A junior developer learning to code",
    user_behaviors: str = "",
    max_steps: int = 100,
    cwd: str = ""
):
    """Run a user-agent session on a task.

    Uses asyncio.run() as the single entry point for all async operations.
    """
    asyncio.run(_run_main(
        task_dir=task_dir,
        task_name=task_name,
        config_path=config_path,
        user_profile=user_profile,
        user_behaviors=user_behaviors,
        max_steps=max_steps,
        cwd=cwd,
    ))


if __name__ == "__main__":
    app()