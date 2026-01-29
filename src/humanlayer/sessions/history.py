from dataclasses import dataclass, field

@dataclass
class Message:
    role: str  # creator: "user", "agent", "environment", "orchestrator", "system"
    visible_to: list[str] = field(default_factory=list)
    reasoning: str = ""
    action: str = ""
    response: str = ""


class SessionHistory:
    def __init__(self):
        self.messages: list[Message] = []

    def append(self, message: Message):
        self.messages.append(message)

    def get(self, viewer: str) -> list[dict]:
        """Return message history formatted for the given viewer."""
        result = []
        for msg in self.messages:
            if viewer not in msg.visible_to:
                continue

            content = self._format_message(msg, viewer)
            
            if not content or not content.strip():
                continue
            llm_role = "assistant" if msg.role == viewer else "user"
            result.append({"role": llm_role, "content": content})

        return result

    def _format_message(self, msg: Message, viewer: str) -> str:
        """Format a message's content based on who's viewing it."""

        # Orchestrator sees everything as-is (god's eye view)
        if viewer == "orchestrator":
            parts = []
            if msg.reasoning:
                parts.append(f"[reasoning] {msg.reasoning}")
            if msg.action:
                parts.append(f"[action] {msg.action}")
            if msg.response:
                parts.append(f"[response] {msg.response}")
            return "\n".join(parts) if parts else msg.response or ""

        # Agent viewing user's message - just show the request
        if msg.role == "user" and viewer == "agent":
            return msg.response

        # User viewing their own message - show full trace with <think><response> tags
        if msg.role == "user" and viewer == "user":
            if msg.action:
                body = f"```bash\n{msg.action}\n```"
            elif "[USER END]" in msg.response:
                body = msg.response
            else:
                body = f"```request\n{msg.response}\n```"

            return f"<think>{msg.reasoning}</think>\n<response>{body}</response>"

        # User viewing environment output
        if msg.role == "environment" and viewer == "user":
            return msg.response
            
        if msg.role == "system" and viewer == "user":
            return msg.response

        # User viewing agent's response
        if msg.role == "agent" and viewer == "user":
            return f"AI agent's response:\n\n{msg.response}"

        # Agent viewing agent's own message
        if msg.role == "agent" and viewer == "agent":
            # Format agent's own message with think/action tags for context
            if msg.action:
                body = f"```bash\n{msg.action}\n```"
            elif "[TASK COMPLETE]" in (msg.response or ""):
                body = msg.response
            else:
                body = msg.response or ""

            if msg.reasoning:
                return f"<think>{msg.reasoning}</think>\n<action>{body}</action>"
            return body

        # Agent viewing environment output (for agent-only mode)
        if msg.role == "environment" and viewer == "agent":
            return msg.response

        raise ValueError(f"No format rule for {msg.role} -> {viewer}")