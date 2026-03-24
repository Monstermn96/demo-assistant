import json
import logging

from app.agents.base import BaseAgent, AgentContext
from app.memory.client import MemoryClient

logger = logging.getLogger(__name__)


class LearningAgent(BaseAgent):
    name = "learning"
    description = "Tracks user preferences, mines behavioral patterns, and updates the user profile to improve future interactions."
    prompt_id = "learning_agent"

    def system_prompt(self) -> str:
        return """You are the Learning Agent for ARIM. Your job is to observe user interactions and learn from them.

You track:
- What the user accepts or rejects (corrections, preferences)
- Behavioral patterns (how often they want updates, what format they prefer)
- Communication style preferences
- Tool usage patterns

When you observe something worth learning, store it as:
- A procedural rule if it's about HOW to do things
- A profile update if it's about WHO the user is or what they prefer
- A semantic memory if it's a fact or preference

Be subtle and helpful. Don't over-track. Focus on high-signal observations."""

    def tools(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "learn_preference",
                    "description": "Record a learned user preference",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "key": {"type": "string", "description": "Preference key (e.g., 'response_length', 'proactive_check_ins')"},
                            "value": {"type": "string", "description": "Preference value"},
                            "confidence": {"type": "number", "description": "How confident 0.0-1.0"},
                            "reason": {"type": "string", "description": "Why this was learned"},
                        },
                        "required": ["key", "value"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "learn_rule",
                    "description": "Store a behavioral rule learned from user interactions",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Rule name"},
                            "rule": {"type": "string", "description": "The rule description"},
                            "category": {"type": "string", "description": "Category: communication, behavior, task_management, data_management, etc."},
                            "priority": {"type": "number"},
                        },
                        "required": ["name", "rule"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_user_profile",
                    "description": "Retrieve the current user profile to check existing preferences",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
        ]

    async def handle_tool_call(self, tc, ctx: AgentContext) -> dict:
        name = tc.function.name
        args = json.loads(tc.function.arguments) if tc.function.arguments else {}

        if name == "learn_preference":
            result = await MemoryClient.update_profile(
                user_id=ctx.user_id,
                key=args["key"],
                value=args["value"],
                confidence=args.get("confidence", 0.7),
                source="learned",
            )
            if not result.get("_error"):
                logger.info("Learned preference: %s=%s (%s)", args["key"], args["value"], args.get("reason", ""))
            return result

        if name == "learn_rule":
            result = await MemoryClient.add_procedural_rule(
                user_id=ctx.user_id,
                name=args["name"],
                rule=args["rule"],
                category=args.get("category", "general"),
                priority=args.get("priority", 0.5),
            )
            if not result.get("_error"):
                logger.info("Learned rule: %s", args["name"])
            return result

        if name == "get_user_profile":
            return await MemoryClient.get_profile(ctx.user_id)

        return {"error": f"Unknown tool: {name}"}

    async def observe_interaction(self, user_message: str, assistant_response: str, ctx: AgentContext, on_event=None, model: str | None = None):
        """Called after each interaction to look for learning opportunities."""
        observe_prompt = f"""Observe this interaction and decide if anything should be learned:

USER: {user_message}

A: {assistant_response}

If the user corrected the assistant, expressed a preference, or provided feedback, use the appropriate tool to record it. If nothing notable happened, just respond with "Nothing to learn from this interaction." """
        try:
            from app.db.database import async_session
            from app.prompts.manager import get_prompt
            async with async_session() as db:
                tmpl = await get_prompt(db, "learning_observe")
                if tmpl:
                    observe_prompt = tmpl.replace("{user_message}", user_message).replace("{assistant_response}", assistant_response)
        except Exception:
            pass
        messages = [
            {"role": "user", "content": observe_prompt}
        ]
        try:
            await self.run(messages, ctx, max_rounds=2, on_event=on_event, model=model)
        except Exception:
            logger.debug("Learning observation failed, non-critical")
