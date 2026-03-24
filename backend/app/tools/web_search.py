import httpx
from app.tools.base import BaseTool, ToolContext

DDGS_URL = "https://api.duckduckgo.com/"


class WebSearchTool(BaseTool):
    name = "web_search"
    description = "Search the web using DuckDuckGo. Returns relevant results with titles, URLs, and snippets."

    def schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results (default 5)",
                    },
                },
                "required": ["query"],
            },
        }

    async def execute(self, ctx: ToolContext, query: str, max_results: int = 5, **kwargs) -> dict:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(DDGS_URL, params={
                "q": query,
                "format": "json",
                "no_html": 1,
                "skip_disambig": 1,
            })
            resp.raise_for_status()
            data = resp.json()

            results = []

            if data.get("Abstract"):
                results.append({
                    "title": data.get("Heading", ""),
                    "url": data.get("AbstractURL", ""),
                    "snippet": data["Abstract"],
                })

            for topic in data.get("RelatedTopics", [])[:max_results]:
                if "Text" in topic:
                    results.append({
                        "title": topic.get("Text", "")[:100],
                        "url": topic.get("FirstURL", ""),
                        "snippet": topic.get("Text", ""),
                    })

            if not results:
                html_resp = await client.get(
                    "https://html.duckduckgo.com/html/",
                    params={"q": query},
                    headers={"User-Agent": "ARIM/1.0"},
                )
                if html_resp.status_code == 200:
                    return {"results": [], "note": "Search returned no structured results. Try a more specific query."}

            return {"results": results[:max_results]}


tool = WebSearchTool()
