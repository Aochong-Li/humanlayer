from dataclasses import dataclass

@dataclass
class Message:
    role: str
    reasoning: str
    response: str
    visibility: list[str]
