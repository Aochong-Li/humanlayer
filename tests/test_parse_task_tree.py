"""
Test script for task tree parsing.

Usage:
    uv run python tests/test_parse_task_tree.py "Your task description here"
    uv run python tests/test_parse_task_tree.py --file path/to/task.txt
"""

import json
import sys
import yaml
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from humanlayer import package_dir
from humanlayer.models import get_model
from humanlayer.orchestrators.default import Orchestrator, OrchestratorConfig, TaskNode


def load_config():
    config_path = package_dir / "config" / "orchestrated.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


def parse_and_print(task_spec: str):
    """Parse a task spec into a tree and print it."""
    config = load_config()

    # Get model
    model_config = config.get("model", {})
    model_name = model_config.pop("model_name", "anthropic/claude-sonnet-4-5")
    model = get_model(model_name, model_config)

    # Create minimal orchestrator config with just parse_task_template
    orch_cfg = config.get("orchestrator", {})
    orch_cfg["task_spec"] = task_spec
    orchestrator_config = OrchestratorConfig(**orch_cfg)

    # Create a minimal orchestrator just for parsing
    # We'll call parse_task_to_tree directly
    class MinimalOrchestrator:
        def __init__(self, model, config):
            self.model = model
            self.config = config

        def _render_template(self, template, **kwargs):
            from jinja2 import Template, StrictUndefined
            return Template(template, undefined=StrictUndefined).render(**kwargs)

    orch = MinimalOrchestrator(model, orchestrator_config)

    # Render the prompt
    prompt = orch._render_template(
        orchestrator_config.parse_task_template,
        task_spec=task_spec,
    )

    print("=" * 60)
    print("TASK SPEC:")
    print("=" * 60)
    print(task_spec[:500] + "..." if len(task_spec) > 500 else task_spec)
    print()

    # Query model
    print("=" * 60)
    print("QUERYING MODEL...")
    print("=" * 60)
    messages = [{"role": "user", "content": prompt}]
    response = model.query(messages)
    content = response.get("content", "")

    print("RAW RESPONSE:")
    print(content[:2000] + "..." if len(content) > 2000 else content)
    print()

    # Parse JSON
    import re
    json_match = re.search(r'\{[\s\S]*\}', content)
    if json_match:
        try:
            data = json.loads(json_match.group())
            tree = TaskNode.from_dict(data)

            print("=" * 60)
            print("PARSED TREE:")
            print("=" * 60)
            print(json.dumps(tree.to_dict(), indent=2))

            # Print tree structure visually
            # print()
            # print("=" * 60)
            # print("TREE STRUCTURE:")
            # print("=" * 60)
            # print_tree(tree)

        except json.JSONDecodeError as e:
            print(f"JSON parse error: {e}")
            print(f"Matched text: {json_match.group()[:500]}")
    else:
        print("No JSON found in response")


def print_tree(node: TaskNode, indent: int = 0):
    """Print tree structure visually."""
    prefix = "  " * indent
    status_marker = "[x]" if node.status == "completed" else "[ ]"
    print(f"{prefix}{status_marker} {node.id}: {node.description[:60]}{'...' if len(node.description) > 60 else ''}")
    for child in node.children:
        print_tree(child, indent + 1)


def main():
    
    task_spec = '''You are given the output file of a Raman Setup. We used it to measure some graphene sample.
Fit the G and 2D Peak of the spectrum and return the x0, gamma, amplitude and offset of the peaks and write them to a file called "/app/results.json".

The file should have the following format:
{
  "G": {
    "x0": <x0_value>,
    "gamma": <gamma_value>,
    "amplitude": <amplitude_value>,
    "offset": <offset_value>
  },
  "2D": {
    "x0": <x0_value>,
    "gamma": <gamma_value>,
    "amplitude": <amplitude_value>,
    "offset": <offset_value>
  }
}'''
    parse_and_print(task_spec)


if __name__ == "__main__":
    main()
