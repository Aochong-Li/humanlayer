"""
Test script for next_task_node LLM query.

Usage:
    uv run python tests/test_next_node.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import yaml
from humanlayer import package_dir
from humanlayer.models import get_model
from humanlayer.orchestrators.default import TaskNode, WorkingMemory, OrchestratorConfig
from humanlayer.sessions.history import ChatHistory, Message
from jinja2 import Template, StrictUndefined


def load_config():
    config_path = package_dir / "config" / "orchestrated.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


def test_next_node():
    config = load_config()

    # Get model
    model_config = config.get("model", {})
    model_name = model_config.pop("model_name", "anthropic/claude-sonnet-4-5")
    model = get_model(model_name, model_config)

    # COBOL example task tree (from config example)
    task_tree = TaskNode(
        id="root",
        description="Re-implement the functionality of a COBOL program in Python, producing identical output files.",
        children=[
            TaskNode(id="1", description="Source COBOL program context and specifications.", status="completed", children=[
                TaskNode(id="1.1", description="The COBOL program is located at /app/src/program.cbl.", status="completed"),
                TaskNode(id="1.2", description="The program reads input data from /app/src/INPUT.DAT.", status="completed"),
                TaskNode(id="1.3", description="The program modifies one or more .DAT files located in the /app/data/ directory.", status="completed"),
                TaskNode(id="1.4", description="The program is designed to be run from the /app/ directory.", status="completed"),
                TaskNode(id="1.5", description="The program should be compiled and executed using GnuCOBOL 3.", status="completed"),
            ]),
            TaskNode(id="2", description="Python implementation requirements.", status="pending", children=[
                TaskNode(id="2.1", description="A new Python script must be created at /app/program.py.", status="pending"),
                TaskNode(id="2.2", description="The Python script must perform the exact same operations as the COBOL program.", status="pending", children=[
                    TaskNode(id="2.2.1", description="The script must read inputs from /app/src/INPUT.DAT.", status="pending"),
                    TaskNode(id="2.2.2", description="The script must apply the same logic to modify the .DAT files in /app/data/.", status="pending"),
                    TaskNode(id="2.2.3", description="The .DAT files produced must be identical to those from the COBOL program.", status="pending"),
                ]),
            ]),
            TaskNode(id="3", description="Success criteria for validation.", status="pending", children=[
                TaskNode(id="3.1", description="Given the same INPUT.DAT and initial .DAT files.", status="pending"),
                TaskNode(id="3.2", description="Output files must be identical after running Python script.", status="pending"),
            ]),
        ]
    )

    # Simulate: user has explored the COBOL program and is now ready to implement
    history = ChatHistory()
    history.append(Message(role="user", response="Can you help me understand the COBOL program?", visible_to=["user", "agent"]))
    history.append(Message(role="agent", response="Sure! The COBOL program at /app/src/program.cbl reads INPUT.DAT and modifies .DAT files. Let me explain the structure...", visible_to=["user", "agent"]))
    history.append(Message(role="user", action="cat /app/src/program.cbl", visible_to=["user"]))
    history.append(Message(role="environment", response="IDENTIFICATION DIVISION.\nPROGRAM-ID. DATAPROC.\n...(COBOL code)...", visible_to=["user"]))
    history.append(Message(role="user", response="Ok I think I understand. Now how do I start writing the Python version?", visible_to=["user", "agent"]))
    history.append(Message(role="agent", response="Let's create /app/program.py. First, we need to read the INPUT.DAT file...", visible_to=["user", "agent"]))

    # Build history summary
    history_lines = []
    for msg in history.messages:
        if msg.action:
            history_lines.append(f"[{msg.role}] executed: {msg.action}")
        elif msg.response:
            history_lines.append(f"[{msg.role}]: {msg.response[:200]}")
    session_history = "\n".join(history_lines)

    # Get template
    next_node_template = config["orchestrator"]["next_node_template"]

    # Render prompt
    prompt = Template(next_node_template, undefined=StrictUndefined).render(
        task_tree=json.dumps(task_tree.to_dict(), indent=2),
        session_history=session_history,
    )

    print("=" * 60)
    print("TASK TREE:")
    print("=" * 60)
    print(json.dumps(task_tree.to_dict(), indent=2))

    print("\n" + "=" * 60)
    print("SESSION HISTORY:")
    print("=" * 60)
    print(session_history)

    print("\n" + "=" * 60)
    print("QUERYING MODEL...")
    print("=" * 60)

    messages = [{"role": "user", "content": prompt}]
    response = model.query(messages)
    content = response.get("content", "")

    print("RAW RESPONSE:")
    print(content)

    print("\n" + "=" * 60)
    print("PARSED NODE IDS:")
    print("=" * 60)

    import re
    try:
        json_match = re.search(r'\[[\s\S]*?\]', content)
        if json_match:
            node_ids = json.loads(json_match.group())
            print(f"Node IDs: {node_ids}")
        else:
            print("No JSON array found")
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}")


if __name__ == "__main__":
    test_next_node()
