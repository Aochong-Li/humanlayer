"""
Simple Orchestrator: Minimal orchestrated user-agent flow.

- Symbolic DFS task traversal (no LLM for next node)
- Mark complete after each action (no LLM for progress)
- User memory = session history (no UserMemory class)
- Perception = truncate NL + preserve code (no LLM)
"""

import json
import re
from dataclasses import dataclass, field
from typing import Literal

import tiktoken
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
    id: str
    description: str
    children: list["TaskNode"] = field(default_factory=list)
    status: Literal["pending", "completed"] = "pending"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "description": self.description,
            "children": [c.to_dict() for c in self.children]
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
# Config
# ──────────────────────────────────────────────────────────────

class SimpleOrchestratorConfig(BaseModel):
    task_spec: str
    max_turns: int = 100
    parse_task_template: str = ""


# ──────────────────────────────────────────────────────────────
# Simple Orchestrator
# ──────────────────────────────────────────────────────────────

class SimpleOrchestrator:
    """
    Minimal orchestrator with symbolic task traversal.
    No LLM calls for task progression or perception.
    """

    def __init__(
        self,
        model: Model,
        config: SimpleOrchestratorConfig,
        user: User,
        agent: ChatAgent,
        env: Environment,
        **kwargs
    ):
        self.model = model
        self.config = config
        self.user = user
        self.agent = agent
        self.env = env
        self.history = SessionHistory()
        self.task_tree: TaskNode | None = None
        self._turn_count = 0
        self.tokenizer = tiktoken.get_encoding("o200k_base")
        self.extra_template_vars = kwargs

        # DFS ordered nodes and current index
        self._nodes: list[TaskNode] = []
        self._node_idx = 0

    async def run(self) -> SessionHistory:
        self.task_tree = self.parse_task_to_tree(self.extra_template_vars)
        self._nodes = self._next_task_node(self.task_tree)
        self.update_user_context()
        self._node_idx = 0

        while True:
            self._turn_count += 1
            if self._turn_count > self.config.max_turns:
                break

            # Get current node
            current_node = self._nodes[self._node_idx] if self._node_idx < len(self._nodes) else self._nodes[-1]

            # Inject context into user: list of all nodes so far (completed + current)
            self.user.extra_template_vars["root_goal"] = self.task_tree.description
            self.user.extra_template_vars["task_nodes"] = "\n".join(["- " + node.description for node in self._nodes[:self._node_idx + 1]])
            self.history.append(Message(
                role="system",
                response=f"What is currently on user's mind:\n{self.user.extra_template_vars['task_nodes']}",
                visible_to=["system"],
            ))

            # Print current state
            print(f"\n{'#'*60}")
            print(f"TURN {self._turn_count} | Node {self._node_idx + 1}/{len(self._nodes)}")
            print(f"{'#'*60}")
            print(f"On user's mind:\n{self.user.extra_template_vars['task_nodes']}")
            # User generates action using session history
            try:
                user_output = self.user.step(self.history.get("user"))
            except FormatError as e:
                self.history.append(Message(
                    role="environment",
                    response=f"Format error: {e}",
                    visible_to=["user", "orchestrator"],
                ))
                print(f"\n{'='*60}\n[Turn {self._turn_count}] FORMAT ERROR: {e}\n{'='*60}")
                continue

            # Print user output
            print(f"\n{'='*60}")
            print(f"[Turn {self._turn_count}] USER ({user_output.type})")
            print(f"{'='*60}")
            print(f"Reasoning: {user_output.reasoning[:200]}..." if len(user_output.reasoning) > 200 else f"Reasoning: {user_output.reasoning}")
            print(f"Content: {user_output.content}")

            # Execute action
            if user_output.type == "request":
                response = self._handle_request(user_output)
                # Simple perception: truncate NL, keep code inline
                perceived = self._simple_perceive(response)
                self.history.append(Message(
                    role="system",
                    response=perceived,
                    visible_to=["user", "orchestrator"],
                ))

                # Print agent response and perception
                print(f"\n{'-'*60}")
                print(f"[Turn {self._turn_count}] AGENT RESPONSE")
                print(f"{'-'*60}")
                print(response[:500] + "..." if len(response) > 500 else response)
                print(f"\n{'-'*60}")
                print(f"[Turn {self._turn_count}] USER PERCEIVES")
                print(f"{'-'*60}")
                print(perceived[:500] + "..." if len(perceived) > 500 else perceived)

            elif user_output.type == "execute":
                output = await self._handle_execute(user_output)
                # Raw output, no processing
                self.history.append(Message(
                    role="environment",
                    response=output,
                    visible_to=["user", "orchestrator"],
                ))

                # Print execution output
                print(f"\n{'-'*60}")
                print(f"[Turn {self._turn_count}] EXECUTION OUTPUT")
                print(f"{'-'*60}")
                print(output[:500] + "..." if len(output) > 500 else output)

            elif user_output.type == "exit":
                self.history.append(Message(
                    role="user",
                    reasoning=user_output.reasoning,
                    response=user_output.content,
                    visible_to=["user", "agent", "orchestrator"],
                ))
                print(f"\n{'-'*60}")
                print(f"[Turn {self._turn_count}] USER EXIT")
                print(f"{'-'*60}")
                # Terminate if fully traversed
                if self._node_idx >= len(self._nodes) - 1:
                    break

            # Mark current node complete, move to next
            if current_node and current_node.status == "pending":
                current_node.status = "completed"
            
            # Move to next node every 2 turns
            if self._turn_count % 2 == 0 and self._node_idx < len(self._nodes) - 1:
                self._node_idx += 1

        return self.history, self.task_tree.to_dict()

    def _handle_request(self, user_output: UserAction) -> str:
        """Handle user request to agent."""
        self.history.append(Message(
            role="user",
            reasoning=user_output.reasoning,
            response=user_output.content,
            visible_to=["user", "agent", "orchestrator"],
        ))

        response = self.agent.step(self.history.get("agent"))
        self.history.append(Message(
            role="agent",
            response=response,
            visible_to=["agent", "orchestrator"],
        ))

        return response

    async def _handle_execute(self, user_output: UserAction) -> str:
        """Handle user command execution."""
        self.history.append(Message(
            role="user",
            reasoning=user_output.reasoning,
            action=user_output.content,
            visible_to=["user", "orchestrator"],
        ))

        result = await self.env.execute(user_output.content)
        output = result.get("output", "")
        if output == "":
            output = f"Empty stdout & stderr from executing {user_output.content} - return code: {result['returncode']}"

        return output

    # ──────────────────────────────────────────────────────────────
    # Task Tree
    # ──────────────────────────────────────────────────────────────

    def parse_task_to_tree(self, extra_template_vars: dict) -> TaskNode:
        """LLM: Parse task_spec into TaskNode tree."""
        if isinstance(extra_template_vars.get("task_tree", None), dict):
            return TaskNode.from_dict(extra_template_vars["task_tree"])

        if not self.config.parse_task_template:
            return TaskNode(id="root", description=self.config.task_spec)

        prompt = Template(self.config.parse_task_template, undefined=StrictUndefined).render(
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

    def _next_task_node(self, node: TaskNode) -> list[TaskNode]:
        """Get root + leaf nodes in DFS order."""
        result = [node]  # Start with root

        def dfs(n: TaskNode):
            if not n.children:
                result.append(n)
            else:
                for child in n.children:
                    dfs(child)

        if node.children:
            dfs(node)
        return result

    # ──────────────────────────────────────────────────────────────
    # Simple Perception
    # ──────────────────────────────────────────────────────────────

    def _simple_perceive(self, response: str, max_tokens: int = 64) -> str:
        """Truncate natural language to ~max_tokens, preserve code blocks indexed."""
        # Extract code blocks
        code_blocks = re.findall(r'```[\s\S]*?```', response)

        # Replace code blocks with indexed placeholders
        text_only = response
        for i, _ in enumerate(code_blocks):
            text_only = re.sub(r'```[\s\S]*?```', f'[CODE BLOCK {i}]', text_only, count=1)

        # Truncate text to ~max_tokens
        tokenized_text = self.tokenizer.encode(text_only)
        if len(tokenized_text) > max_tokens:
            tokenized_text = tokenized_text[:max_tokens]
            text_only = self.tokenizer.decode(tokenized_text)

        # Format output
        result = "========== What You Read from AI's Response ==========\n\n"
        result += text_only.strip()

        # Append indexed code blocks
        if code_blocks:
            result += "\n\n========== Code Blocks (You Can Copy and Paste/Execute But Don't Understand at all) ==========\n\n"
            result += "\n\n".join(f"[CODE BLOCK {i}]:\n{block}" for i, block in enumerate(code_blocks))

        return result
    
    def update_user_context(self) -> None:
        pass
        # prompt = Template(self.user.config.next_step_template, undefined=StrictUndefined).render(
        #     task_nodes="\n".join(
        #         f"- {n.description}" for n in self._nodes
        #     ) if self._nodes else "(nothing yet)"
        # )
        # message = Message(
        #     role="orchestrator",
        #     content=prompt,
        #     visible_to=["user", "orchestrator"],
        # )
        # self.history.append(message)

    # ──────────────────────────────────────────────────────────────
    # Utilities
    # ──────────────────────────────────────────────────────────────

    def is_complete(self) -> bool:
        """Check if all nodes are completed."""
        return self._node_idx >= len(self._nodes)
