import json
import logging
from app.llm.client import llm_manager
from app.llm.prompts import get_system_prompt
from app.tools.base import ToolContext
from app.tools.registry import tool_registry
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

MAX_TOOL_ROUNDS = 10
CHARS_PER_TOKEN_ESTIMATE = 4


def _build_tool_schemas() -> list[dict]:
    return [
        {"type": "function", "function": tool.schema()}
        for tool in tool_registry.values()
    ]


def _estimate_tokens(messages: list[dict]) -> int:
    """Rough token estimate based on character count."""
    total_chars = sum(len(json.dumps(m)) for m in messages)
    return total_chars // CHARS_PER_TOKEN_ESTIMATE


async def run_agent(
    messages: list[dict],
    model: str | None = None,
    on_token=None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    top_p: float | None = None,
    user_id: int = 1,
) -> dict:
    """
    Run the agent loop: send messages to LLM, execute tool calls, feed results back.
    Returns the final assistant message dict.
    """
    model = model or settings.default_model
    tool_schemas = _build_tool_schemas()
    tool_ctx = ToolContext(user_id=user_id)

    system_msg = {"role": "system", "content": await get_system_prompt()}
    working_messages = [system_msg] + messages

    inference_kwargs: dict = {}
    if temperature is not None:
        inference_kwargs["temperature"] = temperature
    if max_tokens is not None and max_tokens > 0:
        inference_kwargs["max_tokens"] = max_tokens
    if top_p is not None:
        inference_kwargs["top_p"] = top_p

    estimated = _estimate_tokens(working_messages)
    logger.info(f"Agent start: model={model}, ~{estimated} tokens, {len(tool_schemas)} tools")

    for round_num in range(MAX_TOOL_ROUNDS):
        kwargs = dict(model=model, messages=working_messages, **inference_kwargs)
        if tool_schemas:
            kwargs["tools"] = tool_schemas

        if on_token:
            return await _stream_with_tools(kwargs, working_messages, on_token, tool_ctx, inference_kwargs)

        response = await llm_manager.chat(**kwargs)
        choice = response.choices[0]
        assistant_msg = choice.message

        if not assistant_msg.tool_calls:
            return {
                "role": "assistant",
                "content": assistant_msg.content or "",
                "model": model,
            }

        working_messages.append(assistant_msg.model_dump())
        logger.info(f"Round {round_num + 1}: {len(assistant_msg.tool_calls)} tool call(s)")

        for tc in assistant_msg.tool_calls:
            result = await _execute_tool_call(tc, tool_ctx)
            working_messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result),
            })

    return {"role": "assistant", "content": "I hit the tool-call limit. Please try rephrasing.", "model": model}


async def _stream_with_tools(
    kwargs: dict, working_messages: list[dict], on_token, tool_ctx: ToolContext, inference_kwargs: dict | None = None
) -> dict:
    """Stream response, handling tool calls mid-stream."""
    kwargs["stream"] = True
    model = kwargs["model"]

    for round_num in range(MAX_TOOL_ROUNDS):
        collected_content = []
        collected_tool_calls: dict[int, dict] = {}

        stream = await llm_manager.chat_stream(**{k: v for k, v in kwargs.items() if k != "stream"})
        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if not delta:
                continue

            if delta.content:
                collected_content.append(delta.content)
                await on_token(delta.content)

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

        if not collected_tool_calls:
            return {"role": "assistant", "content": "".join(collected_content), "model": model}

        assistant_msg = {
            "role": "assistant",
            "content": "".join(collected_content) or None,
            "tool_calls": [collected_tool_calls[i] for i in sorted(collected_tool_calls)],
        }
        working_messages.append(assistant_msg)
        logger.info(f"Stream round {round_num + 1}: {len(assistant_msg['tool_calls'])} tool call(s)")

        for tc_data in assistant_msg["tool_calls"]:
            tc = type("TC", (), {
                "id": tc_data["id"],
                "function": type("Fn", (), {
                    "name": tc_data["function"]["name"],
                    "arguments": tc_data["function"]["arguments"],
                })(),
            })()
            result = await _execute_tool_call(tc, tool_ctx)
            working_messages.append({
                "role": "tool",
                "tool_call_id": tc_data["id"],
                "content": json.dumps(result),
            })

        kwargs["messages"] = working_messages
        kwargs.pop("stream", None)
        kwargs["stream"] = True

    return {"role": "assistant", "content": "I hit the tool-call limit. Please try rephrasing.", "model": model}


async def _execute_tool_call(tc, ctx: ToolContext) -> dict:
    name = tc.function.name
    tool = tool_registry.get(name)
    if not tool:
        return {"error": f"Unknown tool: {name}"}
    try:
        args = json.loads(tc.function.arguments) if tc.function.arguments else {}
        logger.info(f"Executing tool: {name}({list(args.keys())})")
        return await tool.execute(ctx, **args)
    except Exception as e:
        logger.exception(f"Tool {name} failed")
        return {"error": str(e)}
