"""Simple chat agent that just queries the model without executing actions."""

from jinja2 import StrictUndefined, Template
from pydantic import BaseModel

from humanlayer import Environment, Model


class ChatAgentConfig(BaseModel):
    system_template: str
    instance_template: str = ""


class ChatAgent:
    """A simple chatbot agent that only talks, doesn't execute commands."""

    def __init__(self, model: Model, env: Environment, *, config_class: type = ChatAgentConfig, **kwargs):
        self.config = config_class(**kwargs)
        self.model = model
        self.env = env
        self.extra_template_vars = {}

    def render_template(self, template: str, **kwargs) -> str:
        template_vars = self.config.model_dump() | self.env.get_template_vars() | self.model.get_template_vars()
        return Template(template, undefined=StrictUndefined).render(
            **kwargs, **template_vars, **self.extra_template_vars
        )

    def query(self, messages: list[dict]) -> dict:
        """Query the model and return response."""
        response = self.model.query(messages)
        
        return response
