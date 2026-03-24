import json
import logging

from app.agents.base import BaseAgent, AgentContext
from app.memory.client import MemoryClient

logger = logging.getLogger(__name__)


class KnowledgeAgent(BaseAgent):
    name = "knowledge_retriever"
    description = "Retrieves relevant knowledge from the memory system to enrich context for the orchestrator."
    prompt_id = "knowledge_agent"

    def system_prompt(self) -> str:
        return """You are the Knowledge Retriever agent for ARIM. Your job is to find relevant information from the memory system.

When asked to retrieve context for a query:
1. Search semantic memory for related knowledge
2. Check for relevant procedural rules
3. Look up user profile preferences that might be relevant
4. Return a concise summary of what you found

Be thorough but concise. Only return genuinely relevant information."""

    def tools(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "search_knowledge",
                    "description": "Search the knowledge base",
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
                    "name": "get_rules",
                    "description": "Get procedural rules for a category",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "category": {"type": "string"},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_profile",
                    "description": "Get user profile/preferences",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
        ]

    async def handle_tool_call(self, tc, ctx: AgentContext) -> dict:
        name = tc.function.name
        args = json.loads(tc.function.arguments) if tc.function.arguments else {}

        if name == "search_knowledge":
            return await MemoryClient.search(
                query=args["query"],
                user_id=ctx.user_id,
                limit=args.get("limit", 5),
            )

        if name == "get_rules":
            return await MemoryClient.get_procedural_rules(
                user_id=ctx.user_id,
                category=args.get("category"),
            )

        if name == "get_profile":
            return await MemoryClient.get_profile(ctx.user_id)

        return {"error": f"Unknown tool: {name}"}

    async def enrich_context(self, query: str, ctx: AgentContext, on_event=None, model: str | None = None) -> str:
        """Retrieve relevant context for a user query. Returns a summary string."""
        query_template = f"Find any relevant knowledge, rules, or preferences for this query: {query}"
        try:
            from app.db.database import async_session
            from app.prompts.manager import get_prompt
            async with async_session() as db:
                tmpl = await get_prompt(db, "knowledge_query")
                if tmpl:
                    query_template = tmpl.replace("{query}", query)
        except Exception:
            pass
        messages = [
            {"role": "user", "content": query_template}
        ]
        try:
            result = await self.run(messages, ctx, max_rounds=3, on_event=on_event, model=model)
            return result.get("content", "")
        except Exception:
            logger.debug("Knowledge enrichment failed, non-critical")
            return ""
