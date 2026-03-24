import json
import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from app.agents.base import BaseAgent, AgentContext
from app.agents.memory_agent import MemoryAgent
from app.agents.knowledge_agent import KnowledgeAgent
from app.agents.learning_agent import LearningAgent
from app.memory.client import MemoryClient
from app.llm.client import llm_manager
from app.llm.prompts import get_system_prompt
from app.tools.base import ToolContext
from app.tools.registry import tool_registry
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

MAX_TOOL_ROUNDS = 10

memory_agent = MemoryAgent()
knowledge_agent = KnowledgeAgent()
learning_agent = LearningAgent()


def _build_tool_schemas() -> list[dict]:
    """Build tool schemas from the tool registry plus agent-specific tools."""
    schemas = [
        {"type": "function", "function": tool.schema()}
        for tool in tool_registry.values()
    ]
    schemas.append({
        "type": "function",
        "function": {
            "name": "remember",
            "description": "Store something in long-term memory for future reference",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "What to remember"},
                    "topic": {"type": "string", "description": "Topic/category"},
                    "importance": {"type": "number", "description": "Importance 0.0-1.0"},
                },
                "required": ["content"],
            },
        },
    })
    schemas.append({
        "type": "function",
        "function": {
            "name": "recall",
            "description": "Search long-term memory for relevant information",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "What to search for"},
                },
                "required": ["query"],
            },
        },
    })
    schemas.append({
        "type": "function",
        "function": {
            "name": "forget",
            "description": (
                "Delete something from long-term memory. Use when the user says "
                "'forget that', 'delete that memory', 'that's wrong, remove it', etc. "
                "Provide either a memory_id (from a previous recall/remember result) "
                "or a query to search for and delete matching memories."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "memory_id": {
                        "type": "string",
                        "description": "Specific memory ID to delete (from a recall or remember result)",
                    },
                    "query": {
                        "type": "string",
                        "description": "Search query to find memories to delete. Matching memories will be removed.",
                    },
                },
            },
        },
    })
    return schemas


async def run_orchestrated_agent(
    messages: list[dict],
    model: str | None = None,
    on_token=None,
    on_event=None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    top_p: float | None = None,
    user_id: int = 1,
    user_timezone: str | None = None,
    enable_learning: bool = True,
    enable_knowledge: bool = True,
    load_config: dict | None = None,
    reasoning_effort: str | None = None,
) -> dict:
    """
    Run the orchestrated agent with memory enrichment and learning.
    Falls back gracefully if memory service is unavailable.
    """
    model = model or settings.default_model
    ctx = AgentContext(user_id=user_id, source="chat")
    tool_ctx = ToolContext(user_id=user_id, timezone=user_timezone)

    system_content = await get_system_prompt()

    if on_event:
        await on_event({"type": "agent_start", "agent": "memory", "label": "Loading user context..."})
    user_context = await MemoryClient.load_user_context(user_id)
    if user_context:
        system_content += f"\n\n[User context from memory — use this to personalize your responses]\n{user_context}"
    if on_event:
        await on_event({"type": "agent_done", "agent": "memory", "content": user_context or "(no context)"})

    if enable_knowledge and messages:
        last_user_msg = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
        if last_user_msg:
            if on_event:
                await on_event({"type": "agent_start", "agent": knowledge_agent.name, "label": "Searching memory..."})
            knowledge_context = await knowledge_agent.enrich_context(last_user_msg, ctx, on_event=on_event, model=model)
            if on_event:
                await on_event({"type": "agent_done", "agent": knowledge_agent.name, "content": knowledge_context or "(nothing found)"})
            if knowledge_context:
                system_content += f"\n\n[Relevant knowledge from memory]\n{knowledge_context}"

    now = datetime.now(timezone.utc)
    date_time_block = (
        f"\n\n[Current date and time]\n"
        f"Today is {now.strftime('%A, %B %d, %Y')}. Current time (UTC): {now.isoformat(timespec='seconds').replace('+00:00', 'Z')}.\n"
        "Use this when the user says \"tomorrow\", \"next Monday\", \"in 2 days\", etc., and when creating calendar events."
    )
    if user_timezone:
        try:
            tz = ZoneInfo(user_timezone)
            now_local = now.astimezone(tz)
            formatted = now_local.strftime("%A, %B %d, %Y, %I:%M %p %Z").lstrip("0").replace(" 0", " ")
            date_time_block += (
                f"Current time in user's timezone ({user_timezone}): {formatted}.\n"
                "For 'what time is it?' or similar: use ONLY this line. Do not convert from UTC yourself. "
                "Do not use timezone from memory or profile (e.g. EST) for current time — use this line or the get_current_time tool.\n"
            )
        except Exception:
            pass
    else:
        date_time_block += (
            "No user timezone is set in Settings. If the user asks for the current time, give the time in UTC or suggest they set Time zone in Settings. "
            "Do not convert UTC using a timezone from memory (e.g. EST) — that often gives the wrong time (e.g. EST vs EDT in March). "
            "You may call the get_current_time tool to return UTC.\n"
        )
    system_content += date_time_block

    # If last user message looks like a correction/cleanup request, instruct full cleanup
    last_user_msg = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
    last_text = last_user_msg if isinstance(last_user_msg, str) else ""
    _correction_keywords = (
        "duplicate", "duplicates", "fix that", "clean up", "clean up the mess",
        "wrong", "remove them", "fix it",
    )
    if last_text and any(kw in last_text.lower() for kw in _correction_keywords):
        _line1 = "The user is asking for a correction/cleanup; list all affected items then fix or remove every one."
        _line2 = "This turn is a correction/cleanup: you must list all affected items, then remove or fix every one, and confirm when done."
        system_content += "\n\n[Correction/cleanup]\n" + _line1 + "\n" + _line2

    system_msg = {"role": "system", "content": system_content}
    working_messages = [system_msg] + messages

    tool_schemas = _build_tool_schemas()

    inference_kwargs: dict = {}
    if temperature is not None:
        inference_kwargs["temperature"] = temperature
    if max_tokens is not None and max_tokens > 0:
        inference_kwargs["max_tokens"] = max_tokens
    if top_p is not None:
        inference_kwargs["top_p"] = top_p
    if reasoning_effort:
        inference_kwargs["reasoning_effort"] = reasoning_effort

    for round_num in range(MAX_TOOL_ROUNDS):
        kwargs = dict(model=model, messages=working_messages, **inference_kwargs)
        if tool_schemas:
            kwargs["tools"] = tool_schemas
        if load_config:
            kwargs["load_config"] = load_config

        if on_token:
            result = await _stream_with_agents(kwargs, working_messages, on_token, tool_ctx, ctx, inference_kwargs, on_event=on_event)
        else:
            response = await llm_manager.chat(**kwargs)
            choice = response.choices[0]
            assistant_msg = choice.message

            if not assistant_msg.tool_calls:
                result = {"role": "assistant", "content": assistant_msg.content or "", "model": model}
                break

            working_messages.append(assistant_msg.model_dump())
            logger.info(f"Orchestrator round {round_num + 1}: {len(assistant_msg.tool_calls)} tool call(s)")

            for tc in assistant_msg.tool_calls:
                if on_event:
                    try:
                        args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                    except Exception:
                        args = {}
                    await on_event({"type": "tool_start", "agent": "orchestrator", "tool": tc.function.name, "args": args})
                tc_result = await _execute_agent_tool_call(tc, tool_ctx, ctx)
                if on_event:
                    await on_event({"type": "tool_done", "agent": "orchestrator", "tool": tc.function.name, "result": json.dumps(tc_result)[:500]})
                working_messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(tc_result),
                })
            continue

        if enable_learning and result.get("content"):
            last_user = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
            if last_user:
                if on_event:
                    await _learning_with_event(last_user, result["content"], ctx, on_event, model=model)
                else:
                    await learning_agent.observe_interaction(last_user, result["content"], ctx, model=model)

        return result
    else:
        result = {"role": "assistant", "content": "I hit the tool-call limit. Please try rephrasing.", "model": model}

    if enable_learning and result.get("content"):
        last_user = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
        if last_user:
            if on_event:
                await _learning_with_event(last_user, result["content"], ctx, on_event, model=model)
            else:
                await learning_agent.observe_interaction(last_user, result["content"], ctx, model=model)

    return result


async def _stream_with_agents(
    kwargs: dict, working_messages: list[dict], on_token,
    tool_ctx: ToolContext, agent_ctx: AgentContext, inference_kwargs: dict | None = None,
    on_event=None,
) -> dict:
    """Stream response with agent tool handling."""
    kwargs["stream"] = True
    model = kwargs["model"]

    for round_num in range(MAX_TOOL_ROUNDS):
        collected_content = []
        collected_tool_calls: dict[int, dict] = {}
        first_content_emitted = False

        stream = await llm_manager.chat_stream(**{k: v for k, v in kwargs.items() if k != "stream"})
        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if not delta:
                continue

            if delta.content:
                if not first_content_emitted and round_num > 0 and on_event:
                    await on_event({"type": "agent_done", "agent": "llm", "content": ""})
                    first_content_emitted = True
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

        for tc_data in assistant_msg["tool_calls"]:
            tc = type("TC", (), {
                "id": tc_data["id"],
                "function": type("Fn", (), {
                    "name": tc_data["function"]["name"],
                    "arguments": tc_data["function"]["arguments"],
                })(),
            })()
            if on_event:
                try:
                    args = json.loads(tc_data["function"]["arguments"]) if tc_data["function"]["arguments"] else {}
                except Exception:
                    args = {}
                await on_event({"type": "tool_start", "agent": "orchestrator", "tool": tc_data["function"]["name"], "args": args})
            result = await _execute_agent_tool_call(tc, tool_ctx, agent_ctx)
            if on_event:
                await on_event({"type": "tool_done", "agent": "orchestrator", "tool": tc_data["function"]["name"], "result": json.dumps(result)[:500]})
            working_messages.append({
                "role": "tool",
                "tool_call_id": tc_data["id"],
                "content": json.dumps(result),
            })

        if on_event:
            await on_event({"type": "agent_start", "agent": "llm", "label": "Generating response..."})

        kwargs["messages"] = working_messages
        kwargs.pop("stream", None)
        kwargs["stream"] = True

    return {"role": "assistant", "content": "I hit the tool-call limit. Please try rephrasing.", "model": model}


async def _execute_agent_tool_call(tc, tool_ctx: ToolContext, agent_ctx: AgentContext) -> dict:
    """Execute a tool call, routing to agents or tool registry as needed."""
    name = tc.function.name
    args = json.loads(tc.function.arguments) if tc.function.arguments else {}

    if name == "remember":
        result = await MemoryClient.store(
            content=args.get("content", ""),
            user_id=agent_ctx.user_id,
            topic=args.get("topic"),
            importance=args.get("importance", 0.5),
            source=agent_ctx.source,
        )
        if result.get("_error"):
            return {"note": "Memory service is currently unavailable — I'll proceed without saving this, but the interaction is still logged in conversation history."}
        return result

    if name == "recall":
        result = await MemoryClient.search(
            query=args.get("query", ""),
            user_id=agent_ctx.user_id,
            limit=args.get("limit", 5),
        )
        if result.get("_error"):
            return {"note": "Memory search is currently unavailable. I don't have access to long-term memory right now, but I can still help based on our current conversation."}
        return result

    if name == "forget":
        memory_id = args.get("memory_id")
        query = args.get("query")

        if memory_id:
            result = await MemoryClient.delete(memory_id, user_id=agent_ctx.user_id)
            if result.get("_error"):
                return {"note": "Memory service is currently unavailable — couldn't delete the memory."}
            return {"success": True, "deleted_id": memory_id}

        if query:
            search_result = await MemoryClient.search(
                query=query, user_id=agent_ctx.user_id, limit=5,
            )
            if search_result.get("_error"):
                return {"note": "Memory service is currently unavailable — couldn't search for memories to delete."}
            results = search_result.get("results", [])
            if not results:
                return {"note": "No matching memories found to delete."}
            deleted = []
            for item in results:
                mid = item.get("id")
                if mid:
                    del_result = await MemoryClient.delete(mid, user_id=agent_ctx.user_id)
                    if not del_result.get("_error"):
                        deleted.append({"id": mid, "content": item.get("content", "")[:100]})
            if deleted:
                return {"success": True, "deleted": deleted, "count": len(deleted)}
            return {"note": "Found matching memories but couldn't delete them."}

        return {"error": "Provide either memory_id or query to specify what to forget."}

    tool = tool_registry.get(name)
    if not tool:
        return {"error": f"Unknown tool: {name}"}
    try:
        logger.info(f"Executing tool: {name}({list(args.keys())})")
        return await tool.execute(tool_ctx, **args)
    except Exception as e:
        logger.exception(f"Tool {name} failed")
        return {"error": str(e)}


async def _learning_with_event(user_msg: str, assistant_msg: str, ctx: AgentContext, on_event, model: str | None = None):
    try:
        await on_event({"type": "agent_start", "agent": "learning", "label": "Observing interaction..."})
        await learning_agent.observe_interaction(user_msg, assistant_msg, ctx, on_event=on_event, model=model)
        await on_event({"type": "agent_done", "agent": "learning"})
    except Exception:
        logger.debug("Learning event emission failed (WS may have closed)")

