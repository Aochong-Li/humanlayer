"""
Orchestrator: The puppet master that controls simulated user-agent interactions.

The orchestrator has a god's eye view - sees everything that user, agent, and
environment do - and models realistic human limitations:
- Imperfect articulation: Users don't express requests perfectly
- Imperfect perception: Users don't perceive everything
- Mistakes: Users make execution errors
"""

import json
import re
from dataclasses import dataclass, field
from typing import Literal

from jinja2 import StrictUndefined, Template
from pydantic import BaseModel

from humanlayer import Environment, Model
from humanlayer.agents.chat import ChatAgent
from humanlayer.sessions.history import SessionHistory, Message
from humanlayer.users.default import User, UserAction, FormatError


# ──────────────────────────────────────────────────────────────
# Task Tree
# ──────────────────────────────────────────────────────────────

@dataclass
class TaskNode:
    """A node in the task tree representing a subtask."""
    id: str
    description: str
    children: list["TaskNode"] = field(default_factory=list)
    status: Literal["pending", "completed"] = "pending"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "description": self.description,
            "children": [c.to_dict() for c in self.children],
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TaskNode":
        return cls(
            id=data["id"],
            description=data["description"],
            children=[cls.from_dict(c) for c in data.get("children", [])],
            status=data.get("status", "pending"),
        )


# ──────────────────────────────────────────────────────────────
# User Memory
# ──────────────────────────────────────────────────────────────

@dataclass
class UserMemory:
    """
    User's memory system with two components:
    - working_memory: List of perceptions from each turn
    - external_memory: Dict of saved info (code, long content)
    """
    working_memory: list = field(default_factory=list)
    external_memory: dict = field(default_factory=dict)

    def to_prompt(self) -> str:
        """Format memory for user prompt: perceptions as bullets, external memory with id+summary."""
        lines = []

        # Perceptions as bullet points
        for perception in self.working_memory:
            lines.append(f"- {perception}")

        if self.external_memory:
            lines.append("\nExternal memory — treat as opaque. You can copy-paste these into requests or commands, but don't try to understand them:")
            for idx, entry in self.external_memory.items():
                lines.append(f"  [REF:{idx}] {entry['content']}") # let's just use content for now. it is easier than summary

        return "\n".join(lines) if lines else "(nothing yet)"

    def add_perception(self, perception: str):
        """Add a perception to working memory."""
        self.working_memory.append(perception)

    def add_external(self, summary: str, content: str):
        """Add entry to external memory."""
        index = len(self.external_memory)
        self.external_memory[index] = {"summary": summary, "content": content}
        return index


# ──────────────────────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────────────────────

class OrchestratorConfig(BaseModel):
    """Configuration for the orchestrator."""
    task_spec: str
    max_turns: int = 100

    # Prompt templates
    parse_task_template: str = ""
    next_node_template: str = ""
    perceive_template: str = ""
    task_progress_template: str = ""
    validate_template: str = ""


# ──────────────────────────────────────────────────────────────
# Orchestrator
# ──────────────────────────────────────────────────────────────

class Orchestrator:
    """
    The puppet master that controls simulated user-agent interactions.

    Has god's eye view: sees everything that user, agent, and environment do.
    Controls user's cognitive state and applies lossy channels to communication.
    """

    def __init__(
        self,
        model: Model,
        config: OrchestratorConfig,
        user: User,
        agent: ChatAgent,
        env: Environment,
        task_tree: TaskNode | None = None,
    ):
        self.model = model
        self.config = config
        self.user = user
        self.agent = agent
        self.env = env
        self.history = SessionHistory()
        self.task_tree: TaskNode | None = task_tree
        self.user_memory = UserMemory()
        self.current_nodes: list[TaskNode] = []  # Can be multiple active nodes
        self._turn_count = 0

    async def run(self) -> SessionHistory:
        """
        Main loop. Returns the full session history when complete.

        Flow per turn:
        1. next_task_node() - determine which nodes user should focus on
        2. User generates action
        3. Execute action (request or execute)
        4. user_perceive() - add perception to memory
        5. update_task_progress() - mark completed nodes
        """
        # Parse task into tree
        if not self.task_tree:
            self.task_tree = self.parse_task_to_tree()

        while True:
            import pdb; pdb.set_trace()
            self._turn_count += 1
            if self._turn_count > self.config.max_turns:
                break

            # 1. Determine next task nodes
            self.next_task_node()

            # 2. User generates action - inject memory and task context
            self.user.user_memory = self.user_memory
            self.user.extra_template_vars["root_goal"] = self.task_tree.description if self.task_tree else self.config.task_spec
            self.user.extra_template_vars["task_nodes"] = "\n".join(
                f"- {n.description}" for n in self.current_nodes
            ) if self.current_nodes else "(nothing yet)"
            
            try:
                user_output = self.user.step()
            except FormatError as e:
                self.history.append(Message(
                    role="environment",
                    response=f"Format error: {e}",
                    visible_to=["user", "orchestrator"],
                ))
                continue

            # 3. Validate (placeholder for future)
            msg, is_valid = "", True
            if not is_valid:
                self.history.append(Message(
                    role="orchestrator",
                    response=msg,
                    visible_to=["orchestrator"],
                ))
                continue

            # 4. Execute action and perceive result
            if user_output.type == "request":
                response = self._handle_request(user_output)
                self.user_perceive(response, "agent")

            elif user_output.type == "execute":
                output = await self._handle_execute(user_output)
                self.user_perceive(output, "environment")

            elif user_output.type == "exit":
                self.history.append(Message(
                    role="user",
                    reasoning=user_output.reasoning,
                    response=user_output.content,
                    visible_to=["user", "agent", "orchestrator"],
                ))
                break

            # 5. Update task progress
            self.update_task_progress()

        return self.history

    def _handle_request(self, user_output: UserAction) -> str:
        """Handle a user request action. Returns agent response."""
        self.history.append(Message(
            role="user",
            reasoning=user_output.reasoning,
            response=user_output.content,
            visible_to=["user", "agent", "orchestrator"],
        ))

        # Agent responds
        response = self.agent.query(self.history.get("agent"))
        self.history.append(Message(
            role="agent",
            response=response,
            visible_to=["agent", "orchestrator"],
        ))

        return response

    async def _handle_execute(self, user_output: UserAction) -> str:
        """Handle a user execute action. Returns command output."""
        self.history.append(Message(
            role="user",
            reasoning=user_output.reasoning,
            action=user_output.content,
            visible_to=["user", "orchestrator"],
        ))

        # Execute in environment
        result = await self.env.execute(user_output.content)
        output = result.get("output", "") if isinstance(result, dict) else str(result)

        self.history.append(Message(
            role="environment",
            response=output,
            visible_to=["orchestrator"],
        ))

        return output

    # ──────────────────────────────────────────────────────────────
    # Task Tree Methods
    # ──────────────────────────────────────────────────────────────

    def parse_task_to_tree(self) -> TaskNode:
        """LLM: Parse task_spec string into TaskNode tree."""
        if not self.config.parse_task_template:
            return TaskNode(id="root", description=self.config.task_spec)

        prompt = self._render_template(
            self.config.parse_task_template,
            task_spec=self.config.task_spec,
        )

        messages = [{"role": "user", "content": prompt}]
        response = self.model.query(messages)
        content = response.get("content", "")

        try:
            json_match = re.search(r'\[[\s\S]*\]|\{[\s\S]*\}', content)
            if json_match:
                data = json.loads(json_match.group())
                if isinstance(data, list):
                    children = [TaskNode.from_dict(d) for d in data]
                    return TaskNode(id="root", description=self.config.task_spec, children=children)
                else:
                    return TaskNode.from_dict(data)
        except (json.JSONDecodeError, KeyError):
            pass

        return TaskNode(id="root", description=self.config.task_spec)

    def next_task_node(self) -> list[TaskNode]:
        """LLM: Determine which task nodes should be considered next."""
        if not self.task_tree:
            return []

        # Current task node IDs
        task_node_ids = [n.id for n in self.current_nodes]

        prompt = self._render_template(
            self.config.next_node_template,
            task_tree=json.dumps(self.task_tree.to_dict(), indent=2),
            session_history=self._get_history_text(),
            task_nodes=task_node_ids,
            current_turn=self._turn_count,
            max_turns=self.config.max_turns,
        )

        messages = [{"role": "user", "content": prompt}]
        response = self.model.query(messages)
        content = response.get("content", "")

        node_ids = []
        try:
            match = re.search(r'<RETURN_NODES>\s*(\[[\s\S]*?\])\s*</RETURN_NODES>', content)
            if match:
                node_ids = json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

        # Find nodes by ID
        self.current_nodes = []
        for node_id in node_ids:
            node = self._find_node_by_id(self.task_tree, str(node_id))
            if node:
                self.current_nodes.append(node)

        return self.current_nodes

    def _find_node_by_id(self, node: TaskNode, target_id: str) -> TaskNode | None:
        """Find a node by its ID in the tree."""
        if node.id == target_id:
            return node
        for child in node.children:
            result = self._find_node_by_id(child, target_id)
            if result:
                return result
        return None

    # ──────────────────────────────────────────────────────────────
    # User Memory
    # ──────────────────────────────────────────────────────────────

    def user_perceive(self, raw_response: str, role: str):
        """
        LLM-based perception: determine what user understands from raw response.

        Args:
            raw_response: Raw output from agent or environment
            role: Who produced it ("agent" or "environment")
        """
        current_index = len(self.user_memory.external_memory)
        prompt = self._render_template(
            self.config.perceive_template,
            task_spec=self.config.task_spec,
            session_history=self._get_history_text(),
            user_profile=self.user.config.user_profile,
            raw_response=raw_response,
            role=role,
            current_index=current_index,
        )

        messages = [{"role": "user", "content": prompt}]
        response = self.model.query(messages)
        content = response.get("content", "")

        # Parse <PERCEPTION>...</PERCEPTION>
        perception_match = re.search(r'<PERCEPTION>([\s\S]*?)</PERCEPTION>', content)
        if not perception_match:
            raise FormatError("Missing <PERCEPTION>...</PERCEPTION> in output.")
        perception = perception_match.group(1).strip()
        self.user_memory.add_perception(perception)

        # Parse <EXTERNAL_MEMORY>{"0": {"summary": ..., "content": ...}, ...}</EXTERNAL_MEMORY>
        external_memory_match = re.search(r'<EXTERNAL_MEMORY>([\s\S]*?)</EXTERNAL_MEMORY>', content)
        if external_memory_match:
            external_text = external_memory_match.group(1).strip()
            if external_text:
                try:
                    external_data = json.loads(external_text)
                    # external_data format: {"0": {"summary": "...", "content": "..."}, ...}
                    for returned_index, entry in external_data.items():
                        index = self.user_memory.add_external(entry["summary"], entry["content"])
                        if returned_index != index:
                            raise FormatError(f"Index mismatch: {returned_index} != {index}. The indices in the `<EXTERNAL_MEMORY>` MUST BE continuous and start from {current_index}.")
                except (json.JSONDecodeError, KeyError) as e:
                    raise FormatError(f"Failed to parse external memory: {e}")

    def _get_history_text(self, n: int | None = None) -> str:
        """Get session history as text. If n is specified, return only last n messages."""
        messages = self.history.messages[-n:] if n else self.history.messages
        lines = []
        for msg in messages:
            if msg.role == "orchestrator":
                continue
            if msg.action:
                lines.append(f"[{msg.role}] executed: {msg.action}")
            elif msg.response:
                lines.append(f"[{msg.role}]: {msg.response}")
        return "\n".join(lines) if lines else "(no history yet)"

    # ──────────────────────────────────────────────────────────────
    # Task Progress
    # ──────────────────────────────────────────────────────────────

    def update_task_progress(self) -> list[str]:
        if not self.task_tree or not self.config.task_progress_template:
            return []

        current_nodes_desc = " | ".join(n.description for n in self.current_nodes) if self.current_nodes else ""

        prompt = self._render_template(
            self.config.task_progress_template,
            task_tree=json.dumps(self.task_tree.to_dict(), indent=2),
            current_nodes=current_nodes_desc,
            recent_history=self._get_history_text(n=10),
        )

        messages = [{"role": "user", "content": prompt}]
        response = self.model.query(messages)
        content = response.get("content", "")

        # Parse <COMPLETED_NODES>["node_id", ...]</COMPLETED_NODES>
        completed_ids = []
        try:
            match = re.search(r'<COMPLETED_NODES>\s*(\[[\s\S]*?\])\s*</COMPLETED_NODES>', content)
            if match:
                completed_ids = json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

        # Mark nodes as completed
        for node_id in completed_ids:
            node = self._find_node_by_id(self.task_tree, str(node_id))
            if node:
                node.status = "completed"

        # Check if parent nodes should also be marked complete
        self._check_parent_completion()

        return completed_ids

    # ──────────────────────────────────────────────────────────────
    # Validation (Placeholder for future)
    # ──────────────────────────────────────────────────────────────

    def is_step_valid(self, user_output: UserAction) -> tuple[str, bool]:
        """LLM: Check if action deviates from task scope."""
        if not self.config.validate_template:
            return ("", True)  # No validation

        current_nodes_desc = " | ".join(n.description for n in self.current_nodes) if self.current_nodes else ""
        prompt = self._render_template(
            self.config.validate_template,
            task_spec=self.config.task_spec,
            current_nodes=current_nodes_desc,
            action_type=user_output.type,
            action_content=user_output.content,
            reasoning=user_output.reasoning,
        )

        messages = [{"role": "user", "content": prompt}]
        response = self.model.query(messages)
        content = response.get("content", "")

        # Try to parse JSON response
        try:
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                data = json.loads(json_match.group())
                is_valid = data.get("valid", True)
                reason = data.get("reason", "")
                return (reason, is_valid)
        except (json.JSONDecodeError, KeyError):
            pass

        # Default: assume valid
        return ("", True)

    def _check_parent_completion(self):
        """Check if parent nodes should be marked complete."""
        if not self.task_tree:
            return

        def update_parents(node: TaskNode) -> bool:
            """Returns True if this node is completed."""
            if not node.children:
                return node.status == "completed"

            # Update all children first
            all_children_complete = all(update_parents(c) for c in node.children)

            if all_children_complete and node.status == "pending":
                node.status = "completed"

            return node.status == "completed"

        update_parents(self.task_tree)

    # ──────────────────────────────────────────────────────────────
    # Utilities
    # ──────────────────────────────────────────────────────────────

    def is_complete(self) -> bool:
        """Check if the task tree is complete (root node completed)."""
        if not self.task_tree:
            return False
        return self.task_tree.status == "completed"

    def _render_template(self, template: str, **kwargs) -> str:
        """Render a Jinja2 template with the given variables."""
        return Template(template, undefined=StrictUndefined).render(**kwargs)
