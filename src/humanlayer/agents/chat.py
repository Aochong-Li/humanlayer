from jinja2 import StrictUndefined, Template
from pydantic import BaseModel

from humanlayer import Environment, Model


class ChatAgentConfig(BaseModel):
    system_template: str
    instance_template: str = ""


class ChatAgent:
    def __init__(self, model: Model, env: Environment, config: ChatAgentConfig):
        self.model = model
        self.env = env
        self.config = config

    def query(self, messages: list[dict]) -> str:
        full_messages = self._build_prompt(messages)
        response = self.model.query(full_messages)
        return response["content"]

    def _build_prompt(self, messages: list[dict]) -> list[dict]:
        prompt = []
        system = self._render(self.config.system_template)
        if system:
            prompt.append({"role": "system", "content": system})
        if self.config.instance_template:
            prompt.append({"role": "user", "content": self._render(self.config.instance_template)})
        prompt.extend(messages)
        return prompt

    def _render(self, template: str, **extra) -> str:
        vars = {
            **self.config.model_dump(),
            **self.env.get_template_vars(),
            **self.model.get_template_vars(),
            **extra,
        }
        return Template(template, undefined=StrictUndefined).render(**vars)