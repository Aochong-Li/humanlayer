from pydantic import BaseModel
from dataclasses import dataclass
from jinja2 import StrictUndefined, Template

@dataclass
class Message:
    role: str # role of the creator of the message (user, agent, environment)
    isvisibleto: list[str] # permission to see the message
    reasoning: str = "" # user internal reasoning trace
    action: str = "" # action is user's bash command
    response: str = "" # response can be 1. request to agent 2. response from agent to user 3. observation from user's execution

class SessionHistory:
    """
    Assumptions:
    - User's reasoning trace should never be visible to agent
    - The environment's response should never be visible to agent
    """
    def __init__(self):
        self.history = []

    def append(self, message: Message):
        self.history.append(message)

    def render_template(self, by_role: str, to_role: str, **kwargs) -> str:
        if by_role == 'user' and to_role=='agent':
            return kwargs.get('response', '')
        elif by_role == 'user' and to_role == 'user':
            reasoning = kwargs.get('reasoning', '')
            action = kwargs.get('action', '')
            response = kwargs.get('response', '')
            if action:
                return f"<think>{reasoning}</think>\n<response>```bash\n{action}\n```</response>"
            elif response:
                return f"<think>{reasoning}</think>\n<response>```request\n{response}\n```</response>"
            else:
                return f"<think>{reasoning}</think>\n<response></response>"
            
        elif by_role=='observation' and to_role == 'user':
            return kwargs.get('response', '')
        elif by_role=="agent" and to_role=="user":
            agent_response = kwargs.get('response', '')
            return f"This is the AI agent's response to your last request: {agent_response}"
        else:
            raise ValueError(f"Invalid roles: {by_role} and {to_role}")

    def get(self, role: str) -> list[dict]:
        result = []
        for message in self.history:
            if role in message.isvisibleto:
                content = self.render_template(
                    message.role, role,
                    reasoning=message.reasoning,
                    action=message.action,
                    response=message.response
                    )
                llm_role = "assistant" if message.role == role else "user"
                result.append({"role": llm_role, "content": content})
                
        return result