"""Tool to return the current time in the user's timezone (or UTC). Avoids LLM conversion errors (e.g. EST vs EDT)."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.tools.base import BaseTool, ToolContext


class CurrentTimeTool(BaseTool):
    name = "get_current_time"
    description = (
        "Get the current date and time in the user's timezone (or UTC if not set). "
        "Use this when the user asks 'what time is it?' or 'what's the time?' to return an accurate time "
        "without converting from UTC yourself (which can be wrong for daylight saving, e.g. EST vs EDT)."
    )

    def schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        }

    async def execute(self, ctx: ToolContext, **kwargs) -> dict:
        now_utc = datetime.now(timezone.utc)
        tz_name = ctx.timezone
        if tz_name:
            try:
                tz = ZoneInfo(tz_name)
                now_local = now_utc.astimezone(tz)
                formatted = now_local.strftime("%A, %B %d, %Y, %I:%M %p %Z").lstrip("0").replace(" 0", " ")
                return {
                    "timezone": tz_name,
                    "local_time": formatted,
                    "utc_time": now_utc.isoformat(timespec="seconds").replace("+00:00", "Z"),
                }
            except Exception:
                pass
        formatted_utc = now_utc.strftime("%A, %B %d, %Y, %I:%M %p UTC").lstrip("0").replace(" 0", " ")
        return {
            "timezone": None,
            "local_time": formatted_utc,
            "utc_time": now_utc.isoformat(timespec="seconds").replace("+00:00", "Z"),
        }


tool = CurrentTimeTool()
