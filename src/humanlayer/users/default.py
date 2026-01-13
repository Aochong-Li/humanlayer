import re
import subprocess
import time

from jinja2 import StrictUndefined, Template
from pydantic import BaseModel

from humanlayer import Environment, Model


class UserConfig(BaseModel):
    system_template: str
    instance_template: str
    task: str
    user_profile: str
    # timeout_template: str
    # format_error_template: str
    # action_observation_template: str
    think_tags: list[str] = ["<think>", "</think>"]
    response_tags: list[str] = ["<response>", "</response>"]
    action_regex: str = r"```bash\s*\n(.*?)\n```"
    request_regex: str = r"```request\s*\n(.*?)\n```"
    exit_code: str = "[USER END]"
    step_limit: int = 100
    cost_limit: float = 3.0

class UserAction(BaseModel):
    action_type: str 
    reasoning: str | None = None
    action: str | None = None
    request: str | None = None

class NonTerminatingException(Exception):
    """Raised for conditions that can be handled by the user."""

class FormatError(NonTerminatingException):
    """Raised when the LM's output is not in the expected format."""
    
class ExecutionTimeoutError(NonTerminatingException):
    """Raised when the action execution timed out."""

class TerminatingException(Exception):
    """Raised for conditions that terminate the user."""

class Submitted(TerminatingException):
    """Raised when the LM declares that the user has finished its task."""

class LimitsExceeded(TerminatingException):
    """Raised when the user has reached its cost or step limit."""

class DefaultUser:
    def __init__(self, model: Model, env: Environment, *, config_class: type = UserConfig, **kwargs):
        self.config = config_class(**kwargs)
        self.model = model
        self.env = env
        self.task = self.config.task
        self.extra_template_vars = {}
        self.profile = [
            {'role': 'system', 'content': self.render_template(self.config.system_template)},
            {'role': 'user', 'content': self.render_template(self.config.instance_template)}
        ]

    def render_template(self, template: str, **kwargs) -> str:
        template_vars = self.config.model_dump() | self.env.get_template_vars() | self.model.get_template_vars()
        return Template(template, undefined=StrictUndefined).render(
            **kwargs, **template_vars, **self.extra_template_vars
        )
    
    def query(self, messages: list[dict]) -> dict:
        messages = self.profile + messages
        response = self.model.query(messages)

        return response

    def parse_outputs(self, response: dict) -> UserAction:
        match = re.search(fr'{self.config.think_tags[0]}(.*?){self.config.think_tags[1]}', response['content'], re.DOTALL)
        if match:
            reasoning = match.group(1).strip()
        else:
            # Need to define a error
            raise FormatError
        
        match = re.search(fr'{self.config.response_tags[0]}(.*?){self.config.response_tags[1]}', response['content'], re.DOTALL)
        if match:
            output = match.group(1).strip()
        else:
            # Need to define a error
            raise FormatError
        if self.config.exit_code in output:
            return UserAction(action_type='exit', request=output)

        actions = re.findall(self.config.action_regex, output, re.DOTALL)
        requests = re.findall(self.config.request_regex, output, re.DOTALL)

        if len(actions) and len(requests):
            raise FormatError
        elif len(actions) == 1:
            return UserAction(
                action_type='execute',
                reasoning=reasoning,
                action=actions[0].strip(),
                request=None
            )
        elif len(requests) == 1:
            return UserAction(
                action_type='request',
                reasoning=reasoning,
                action=None,
                request=requests[0].strip()
            )
        else:
            raise FormatError
    
    def execute_action(self, action: str) -> dict:
        try:
            output = self.env.execute(action)
        except (TimeoutError, subprocess.TimeoutExpired) as e:
            output = e.output.decode("utf-8", errors="replace") if getattr(e, "output", None) else ""
            return f"""Failed to execute command:\n```bash\n{action}\n```\n\nTimeOutError: {output}"""
        return output
        
        

  