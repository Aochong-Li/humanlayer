from humanlayer.agents.chat import ChatAgent as Agent
from humanlayer.environments.local import LocalEnvironment
from humanlayer.models import get_model
from humanlayer.users.default import DefaultUser as User, FormatError
from humanlayer.sessions.history import SessionHistory, Message
from humanlayer import package_dir
import yaml
import typer
from pydantic import BaseModel
import re

app = typer.Typer()


class AgentAction(BaseModel):
    reasoning: str = ""
    response: str = ""


def parse_agent_output(response: dict) -> AgentAction:
    return AgentAction(response=response.get("content", ""))
    
    # content = response.get("content", "")
    # reasoning = ""
    # match = re.search(fr'{think_tags[0]}(.*?){think_tags[1]}', content, re.DOTALL)
    # if match:
    #     reasoning = match.group(1).strip()
    # response_text = content
    # match = re.search(fr'{output_tags[0]}(.*?){output_tags[1]}', content, re.DOTALL)
    # if match:
    #     response_text = match.group(1).strip()
    # return AgentAction(reasoning=reasoning, response=response_text)


def load_config(config_path: str):
    with open(config_path, 'r') as file:
        return yaml.safe_load(file)


@app.command()
def main(
    task: str = typer.Option(..., "-t", "--task", help="Task for the user"),
    config_path: str = typer.Option(
        str(package_dir / "config" / "user_agent.yaml"),
        "-c", "--config", help="Config file path"
    ),
    user_profile: str = typer.Option(
        "A junior developer learning to code",
        "-u", "--user-profile", help="User profile"
    ),
    cwd: str = typer.Option(
        "",
        "-w", "--cwd", help="Current working directory"
    )
):
    config = load_config(config_path)
    env_config = config.get("env", {})
    if cwd:
        env_config["cwd"] = cwd
    env = LocalEnvironment(**env_config)

    model_config = config.get("model", {})
    model_name = model_config.pop("model_name", None)
    if not model_name:
        raise ValueError("model_name required in config")
    model = get_model(model_name, model_config)

    agent = Agent(model, env, **config.get("agent", {}))
    user = User(model, env, **{**config.get("user", {}), "user_profile": user_profile, "task": task})

    session_history = SessionHistory()

    print(f"\n{'='*60}")
    print(f"Task: {task}")
    print(f"{'='*60}\n")

    step = 0
    while True:
        step += 1
        print(f"\n--- Step {step} ---")
        import pdb; pdb.set_trace()
        user_outputs = user.query(session_history.get("user"))
        try:
            user_action = user.parse_outputs(user_outputs)
        except FormatError as e:
            session_history.append(Message(
                role="environment", response="User response format does not match the expected format.", isvisibleto=["user"]
            ))
            continue

        if user_action.reasoning:
            print(f"[User thinks]: {user_action.reasoning[:200]}...")

        if user_action.action_type == "request":
            print(f"[User requests]: {user_action.request}")
            session_history.append(Message(
                role="user", reasoning=user_action.reasoning,
                response=user_action.request, isvisibleto=["user", "agent"]
            ))

            agent_outputs = agent.query(session_history.get("agent"))
            agent_action = parse_agent_output(agent_outputs)
            print(f"[Agent]: {agent_action.response}")

            session_history.append(Message(
                role="agent", response=agent_action.response, isvisibleto=["user", "agent"]
            ))

        elif user_action.action_type == "execute":
            print(f"[User executes]: {user_action.action}")
            session_history.append(Message(
                role="user", reasoning=user_action.reasoning,
                action=user_action.action, isvisibleto=["user"]
            ))

            results = user.execute_action(user_action.action)
            if isinstance(results, dict):
                print(f"[Return]: {results.get('returncode', 0)}")
                output = results.get("output", "")
                if output:
                    print(f"[Output]: {output[:500]}")
            else:
                output = results
                print(f"[Output]: {str(output)[:500]}")

            session_history.append(Message(
                role="environment", response=str(output), isvisibleto=["user"]
            ))

        elif user_action.action_type == "exit":
            print(f"[Done]: {user_action.request}")
            session_history.append(Message(
                role="user", response=user_action.request, isvisibleto=["user", "agent"]
            ))
            print(f"\n{'='*60}")
            print(f"Completed in {step} steps")
            print(f"{'='*60}\n")
            break


if __name__ == "__main__":
    app()