import json
import logging

from app.agents.base import BaseAgent, AgentContext
from app.memory.client import MemoryClient

logger = logging.getLogger(__name__)


class MemoryAgent(BaseAgent):
    name = "memory_manager"
    description = "Manages all memory tiers: stores, retrieves, searches, and consolidates memories."
    prompt_id = "memory_agent"

    def system_prompt(self) -> str:
        return """You are the Memory Manager agent for ARIM. Your sole responsibility is managing the memory system.

You can:
- Store new memories (semantic, episodic, procedural, or core)
- Search existing memories using semantic similarity
- Recall recent episodic memories
- Update the user profile (core memory)
- Add procedural rules (learned patterns)
- Consolidate/clean old memories

When asked to remember something, store it in the appropriate tier:
- Facts, preferences, knowledge -> semantic
- Events, conversations, interactions -> episodic
- Rules, patterns, behaviors -> procedural
- User identity, preferences -> core

Always confirm what you stored and in which tier."""

    def tools(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "memory_store",
                    "description": "Store a memory in the appropriate tier",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "content": {"type": "string", "description": "The memory content"},
                            "tier": {"type": "string", "enum": ["semantic", "episodic", "procedural", "core", "auto"]},
                            "topic": {"type": "string", "description": "Topic/category"},
                            "importance": {"type": "number", "description": "Importance 0.0-1.0"},
                        },
                        "required": ["content"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "memory_search",
                    "description": "Search memories across tiers",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "limit": {"type": "integer"},
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "memory_recall",
                    "description": "Recall recent episodic memories",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "limit": {"type": "integer"},
                            "topic": {"type": "string"},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "memory_profile_update",
                    "description": "Update the user profile (core memory)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "key": {"type": "string"},
                            "value": {"type": "string"},
                            "confidence": {"type": "number"},
                        },
                        "required": ["key", "value"],
                    },
                },
            },
        ]

    async def handle_tool_call(self, tc, ctx: AgentContext) -> dict:
        name = tc.function.name
        args = json.loads(tc.function.arguments) if tc.function.arguments else {}

        if name == "memory_store":
            return await MemoryClient.store(
                content=args["content"],
                user_id=ctx.user_id,
                tier=args.get("tier", "auto"),
                topic=args.get("topic"),
                importance=args.get("importance", 0.5),
                source=ctx.source,
            )

        if name == "memory_search":
            return await MemoryClient.search(
                query=args["query"],
                user_id=ctx.user_id,
                limit=args.get("limit", 10),
            )

        if name == "memory_recall":
            return await MemoryClient.recall(
                user_id=ctx.user_id,
                limit=args.get("limit", 20),
                topic=args.get("topic"),
            )

        if name == "memory_profile_update":
            return await MemoryClient.update_profile(
                user_id=ctx.user_id,
                key=args["key"],
                value=args["value"],
                confidence=args.get("confidence", 1.0),
            )

        return {"error": f"Unknown tool: {name}"}
