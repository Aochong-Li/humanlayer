import re
import subprocess
from dataclasses import dataclass, field
from typing import Callable

from jinja2 import StrictUndefined, Template
from pydantic import BaseModel

from humanlayer import Environment, Model

# ──────────────────────────────────────────────────────────────
# Exceptions
# ──────────────────────────────────────────────────────────────

class UserException(Exception):
    """Base for all user-related exceptions."""

class FormatError(UserException):
    """LLM output didn't match expected format."""

class ExecutionTimeout(UserException):
    """Action execution timed out."""

# ──────────────────────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────────────────────

class UserConfig(BaseModel):
    system_template: str
    instance_template: str
    user_profile: str
    user_behaviors: str

    # parsing
    think_tags: list[str] = ["<think>", "</think>"]
    response_tags: list[str] = ["<response>", "</response>"]
    exit_code: str = "[USER END]"

# ──────────────────────────────────────────────────────────────
# User Action
# ──────────────────────────────────────────────────────────────

@dataclass
class UserAction:
    type: str  # "execute", "request", "exit"
    reasoning: str = ""
    content: str = ""  # the bash command, request text, or exit message

class ActionParser:
    """Parses LLM output into UserAction."""
    
    ACTION_PATTERN = re.compile(r"```bash\s*\n(.*?)\n```", re.DOTALL)
    REQUEST_PATTERN = re.compile(r"```request\s*\n(.*?)\n```", re.DOTALL)

    def __init__(self, config: UserConfig):
        self.config = config
        self._think_pattern = re.compile(
            rf"{re.escape(config.think_tags[0])}(.*?){re.escape(config.think_tags[1])}", 
            re.DOTALL
        )
        self._response_pattern = re.compile(
            rf"{re.escape(config.response_tags[0])}(.*?){re.escape(config.response_tags[1])}", 
            re.DOTALL
        )

    def parse(self, content: str) -> UserAction:
        reasoning = self._extract_required(self._think_pattern, content, "thinking")
        response = self._extract_required(self._response_pattern, content, "response")

        if self.config.exit_code in response:
            return UserAction(type="exit", reasoning=reasoning, content=response)

        actions = self.ACTION_PATTERN.findall(response)
        requests = self.REQUEST_PATTERN.findall(response)

        if len(actions) == 1 and not requests:
            return UserAction(type="execute", reasoning=reasoning, content=actions[0].strip())
        if len(requests) == 1 and not actions:
            return UserAction(type="request", reasoning=reasoning, content=requests[0].strip())
        
        raise FormatError(f"Expected exactly one action or request, got {len(actions)} actions and {len(requests)} requests")

    def _extract_required(self, pattern: re.Pattern, text: str, name: str) -> str:
        match = pattern.search(text)
        if not match:
            raise FormatError(f"Missing {name} block")
        return match.group(1).strip()


# ──────────────────────────────────────────────────────────────
# User
# ──────────────────────────────────────────────────────────────

class User:
    def __init__(self, model: Model, env: Environment, config: UserConfig, **kwargs):
        self.model = model
        self.env = env
        self.config = config
        self.parser = ActionParser(config)
        self.extra_template_vars = kwargs

    def query(self, messages: list[dict]) -> str:
        full_messages = self._build_prompt(messages)
        response = self.model.query(full_messages)
        return response["content"]

    def parse(self, content: str) -> UserAction:
        return self.parser.parse(content)

    async def execute(self, command: str) -> dict:
        try:
            result = await self.env.execute(command)
            return result if isinstance(result, dict) else {'output': str(result), 'returncode': 1}
        except (TimeoutError, subprocess.TimeoutExpired) as e:
            output = getattr(e, "output", b"").decode("utf-8", errors="replace")
            raise ExecutionTimeout(f"Timeout executing: {command}\n{output}.")

    def _build_prompt(self, messages: list[dict]) -> list[dict]:    
        return [
            {"role": "system", "content": self._render(self.config.system_template)},
            {"role": "user", "content": self._render(self.config.instance_template)},
            *messages,
        ]

    def _render(self, template: str, **extra) -> str:
        vars = {
            **self.config.model_dump(),
            **self.env.get_template_vars(),
            **self.model.get_template_vars(),
            **self.extra_template_vars,
            **extra,
        }
        return Template(template, undefined=StrictUndefined).render(**vars)