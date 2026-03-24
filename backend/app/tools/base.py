from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ToolContext:
    """Context passed to every tool execution, providing user identity and config."""
    user_id: int = 1
    timezone: str | None = None  # IANA timezone from user settings, for time tools
    extras: dict = field(default_factory=dict)


class BaseTool(ABC):
    name: str
    description: str

    @abstractmethod
    def schema(self) -> dict:
        """Return OpenAI function-calling schema."""

    @abstractmethod
    async def execute(self, ctx: ToolContext, **kwargs) -> dict:
        """Execute the tool and return results."""
