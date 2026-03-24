import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.llm.client import llm_manager
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class AgentContext:
    """Shared context passed to all agents."""
    user_id: int = 1
    conversation_id: int | None = None
    source: str = "chat"
    extras: dict = field(default_factory=dict)


class BaseAgent(ABC):
    """Base class for all specialized agents in the hierarchy."""
    name: str
    description: str
    model: str | None = None

    prompt_id: str | None = None

    @abstractmethod
    def system_prompt(self) -> str:
        """Return the fallback system prompt for this agent."""

    @abstractmethod
    def tools(self) -> list[dict]:
        """Return the tool schemas this agent can use."""

    async def _resolve_system_prompt(self) -> str:
        """Load prompt from DB if prompt_id is set, otherwise use fallback."""
        if self.prompt_id:
            try:
                from app.db.database import async_session
                from app.prompts.manager import get_prompt
                async with async_session() as db:
                    content = await get_prompt(db, self.prompt_id)
                    if content:
                        return content
            except Exception:
                pass
        return self.system_prompt()

    async def run(self, messages: list[dict], ctx: AgentContext, **kwargs) -> dict:
        """Execute the agent with the given messages and context."""
        model = self.model or kwargs.get("model") or settings.default_model
        on_event = kwargs.get("on_event")
        system_msg = {"role": "system", "content": await self._resolve_system_prompt()}
        working = [system_msg] + messages

        tool_schemas = self.tools()
        call_kwargs = dict(model=model, messages=working)
        if tool_schemas:
            call_kwargs["tools"] = tool_schemas

        for k in ("temperature", "max_tokens", "top_p"):
            if k in kwargs and kwargs[k] is not None:
                call_kwargs[k] = kwargs[k]

        max_rounds = kwargs.get("max_rounds", 5)
        for round_num in range(max_rounds):
            if on_event:
                result = await self._run_streaming_round(call_kwargs, on_event)
            else:
                response = await llm_manager.chat(**call_kwargs)
                choice = response.choices[0]
                result = {
                    "content": choice.message.content or "",
                    "tool_calls": [tc.model_dump() for tc in (choice.message.tool_calls or [])],
                }

            if not result["tool_calls"]:
                return {"role": "assistant", "content": result["content"], "model": model, "agent": self.name}

            assistant_msg = {"role": "assistant", "content": result["content"] or None, "tool_calls": result["tool_calls"]}
            working.append(assistant_msg)
            logger.info(f"Agent {self.name} round {round_num + 1}: {len(result['tool_calls'])} tool call(s)")

            for tc_data in result["tool_calls"]:
                tc_func = tc_data.get("function", {})
                tc_args_str = tc_func.get("arguments", "")
                tc_args = json.loads(tc_args_str) if tc_args_str else {}
                tc = type("TC", (), {
                    "id": tc_data.get("id", ""),
                    "function": type("Fn", (), {"name": tc_func.get("name", ""), "arguments": tc_args_str})(),
                })()
                if on_event:
                    await on_event({"type": "tool_start", "agent": self.name, "tool": tc_func.get("name", ""), "args": tc_args})
                tool_result = await self.handle_tool_call(tc, ctx)
                if on_event:
                    await on_event({"type": "tool_done", "agent": self.name, "tool": tc_func.get("name", ""), "result": json.dumps(tool_result)[:500]})
                working.append({
                    "role": "tool",
                    "tool_call_id": tc_data.get("id", ""),
                    "content": json.dumps(tool_result),
                })

            call_kwargs["messages"] = working

        return {
            "role": "assistant",
            "content": "Agent reached maximum tool rounds.",
            "model": model,
            "agent": self.name,
        }

    async def _run_streaming_round(self, call_kwargs: dict, on_event) -> dict:
        """Run one LLM round with streaming, emitting agent_token events."""
        collected_content = []
        collected_tool_calls: dict[int, dict] = {}

        stream = await llm_manager.chat_stream(**call_kwargs)
        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if not delta:
                continue

            if delta.content:
                collected_content.append(delta.content)
                await on_event({"type": "agent_token", "agent": self.name, "content": delta.content})

            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in collected_tool_calls:
                        collected_tool_calls[idx] = {
                            "id": tc_delta.id or "",
                            "type": "function",
                            "function": {"name": "", "arguments": ""},
                        }
                    entry = collected_tool_calls[idx]
                    if tc_delta.id:
                        entry["id"] = tc_delta.id
                    if tc_delta.function:
                        if tc_delta.function.name:
                            entry["function"]["name"] += tc_delta.function.name
                        if tc_delta.function.arguments:
                            entry["function"]["arguments"] += tc_delta.function.arguments

        return {
            "content": "".join(collected_content),
            "tool_calls": [collected_tool_calls[i] for i in sorted(collected_tool_calls)],
        }

    async def handle_tool_call(self, tc, ctx: AgentContext) -> dict:
        """Override this to handle tool calls for the agent."""
        return {"error": f"Tool {tc.function.name} not implemented for agent {self.name}"}
