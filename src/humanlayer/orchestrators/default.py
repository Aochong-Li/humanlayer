import re
import subprocess
import time

from jinja2 import StrictUndefined, Template
from pydantic import BaseModel

from humanlayer import Environment, Model
from humanlayer.users.default import User

# ──────────────────────────────────────────────────────────────
# Exceptions
# ──────────────────────────────────────────────────────────────

class OrchestratorException(Exception):
    """Base for all user-related exceptions."""

class FormatError(OrchestratorException):
    """LLM output didn't match expected format."""

class ExecutionTimeout(OrchestratorException):
    """Action execution timed out."""

# ──────────────────────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────────────────────

class OrchestratorConfig(BaseModel):
    system_template: str
    instance_template: str
    timeout_template: str
    
    think_tags: list[str] = ["<think>", "</think>"]
    response_tags: list[str] = ["<response>", "</response>"]
    exit_code: str = "[USER END]"

class OrchestratorAction:
    type: str  # "execute", "request", "exit"
    reasoning: str = ""
    content: str = ""  # the bash command, request text, or exit message


# ──────────────────────────────────────────────────────────────
# Orchestrator
# ──────────────────────────────────────────────────────────────

class Orchestrator:
    def __init__(self, model: Model, env: Environment, config: OrchestratorConfig,
                user: User, task: str, **kwargs):
        self.model = model
        self.env = env
        self.user = user
        self.config = config
        self.extra_template_vars = kwargs

    def query(self, messages: list[dict]) -> str:
    

    def 