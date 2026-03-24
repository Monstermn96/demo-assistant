from datetime import datetime, timezone
from sqlalchemy import select, and_
from app.tools.base import BaseTool, ToolContext
from app.db.database import async_session
from app.db.models import CalendarEvent


def parse_iso_datetime(s: str) -> datetime:
    """Parse ISO 8601 datetime string; normalize Z to +00:00 for Python < 3.11."""
    if not s or not (s := s.strip()):
        raise ValueError("Empty datetime string")
    normalized = s.replace("Z", "+00:00")
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def parse_iso_date_or_datetime(s: str, end_of_day: bool = False) -> datetime | None:
    """Parse ISO date (YYYY-MM-DD) or datetime; for date-only, return start or end of day UTC."""
    if not s or not (s := s.strip()):
        return None
    normalized = s.replace("Z", "+00:00")
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    if end_of_day and "T" not in s:
        dt = dt.replace(hour=23, minute=59, second=59, microsecond=999999)
    return dt


class CalendarTool(BaseTool):
    name = "calendar"
    description = "Create, list, and delete calendar events and reminders. For user requests to fix duplicates or clean up events, list the relevant range first, then delete all duplicate or unwanted events (one delete per event, or use delete_events if available), and do not stop until cleanup is complete."

    def schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["create", "list", "delete", "update", "delete_events"],
                        "description": "The action to perform. delete_events removes multiple events at once (for cleanup/duplicates). When the user asks to fix duplicates or clean up: use list first (with start_date/end_date for the affected range), then use delete_events or delete for each duplicate or unwanted event until cleanup is complete, and confirm when done.",
                    },
                    "title": {"type": "string", "description": "Event title"},
                    "description": {"type": "string", "description": "Event description"},
                    "start_time": {
                        "type": "string",
                        "description": "Start time in ISO 8601 (e.g. 2025-03-16T09:00:00Z). Use the current date and time from your context to resolve relative expressions like 'tomorrow' or 'next Monday' before calling this tool.",
                    },
                    "end_time": {
                        "type": "string",
                        "description": "End time in ISO 8601. Use the current date and time from your context to resolve relative expressions.",
                    },
                    "all_day": {"type": "boolean", "description": "Whether this is an all-day event"},
                    "recurrence": {
                        "type": "string",
                        "enum": ["daily", "weekly", "monthly", "yearly"],
                        "description": "Recurrence pattern",
                    },
                    "event_id": {
                        "type": "integer",
                        "description": "Event ID; required for delete and update.",
                    },
                    "event_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "List of event IDs to delete; used with action delete_events.",
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Start of range for list (ISO date or datetime). Optional.",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End of range for list (ISO date or datetime). Optional.",
                    },
                },
                "required": ["action"],
            },
        }

    async def execute(self, ctx: ToolContext, action: str, **kwargs) -> dict:
        async with async_session() as session:
            if action == "create":
                all_day = kwargs.get("all_day", False)
                if isinstance(all_day, str):
                    all_day = all_day.lower() in ("true", "1", "yes")

                start_time_str = kwargs.get("start_time")
                if start_time_str:
                    try:
                        start_time = parse_iso_datetime(start_time_str)
                    except ValueError as e:
                        return {"error": f"Invalid start_time: {e}"}
                elif all_day:
                    start_time = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
                else:
                    return {"error": "start_time is required for non-all-day events"}

                end_time = None
                if kwargs.get("end_time"):
                    try:
                        end_time = parse_iso_datetime(kwargs["end_time"])
                    except ValueError as e:
                        return {"error": f"Invalid end_time: {e}"}

                event = CalendarEvent(
                    user_id=ctx.user_id,
                    title=kwargs.get("title", "Untitled"),
                    description=kwargs.get("description"),
                    start_time=start_time,
                    end_time=end_time,
                    all_day=all_day,
                    recurrence=kwargs.get("recurrence"),
                )
                session.add(event)
                await session.commit()
                return {"success": True, "event_id": event.id, "title": event.title}

            elif action == "list":
                q = select(CalendarEvent).where(CalendarEvent.user_id == ctx.user_id)
                start_date_str = kwargs.get("start_date")
                end_date_str = kwargs.get("end_date")
                if start_date_str:
                    try:
                        start_bound = parse_iso_date_or_datetime(start_date_str, end_of_day=False)
                        if start_bound is not None:
                            q = q.where(CalendarEvent.start_time >= start_bound)
                    except ValueError as e:
                        return {"error": f"Invalid start_date: {e}"}
                if end_date_str:
                    try:
                        end_bound = parse_iso_date_or_datetime(end_date_str, end_of_day=True)
                        if end_bound is not None:
                            q = q.where(CalendarEvent.start_time <= end_bound)
                    except ValueError as e:
                        return {"error": f"Invalid end_date: {e}"}
                result = await session.execute(q.order_by(CalendarEvent.start_time))
                events = result.scalars().all()
                return {
                    "events": [
                        {
                            "id": e.id,
                            "title": e.title,
                            "description": e.description,
                            "start_time": e.start_time.isoformat(),
                            "end_time": e.end_time.isoformat() if e.end_time else None,
                            "all_day": e.all_day,
                            "recurrence": e.recurrence,
                        }
                        for e in events
                    ]
                }

            elif action == "delete":
                event_id = kwargs.get("event_id")
                result = await session.execute(
                    select(CalendarEvent).where(
                        and_(CalendarEvent.id == event_id, CalendarEvent.user_id == ctx.user_id)
                    )
                )
                event = result.scalar_one_or_none()
                if not event:
                    return {"error": "Event not found"}
                await session.delete(event)
                await session.commit()
                return {"success": True, "deleted_id": event_id}

            elif action == "delete_events":
                event_ids = kwargs.get("event_ids")
                if not event_ids:
                    return {"error": "event_ids is required for delete_events"}
                event_ids = [int(eid) for eid in event_ids]
                deleted_ids = []
                for eid in event_ids:
                    result = await session.execute(
                        select(CalendarEvent).where(
                            and_(CalendarEvent.id == eid, CalendarEvent.user_id == ctx.user_id)
                        )
                    )
                    event = result.scalar_one_or_none()
                    if event:
                        await session.delete(event)
                        deleted_ids.append(eid)
                await session.commit()
                return {"success": True, "deleted_ids": deleted_ids, "deleted_count": len(deleted_ids)}

            elif action == "update":
                event_id = kwargs.get("event_id")
                if event_id is None:
                    return {"error": "event_id is required for update"}
                result = await session.execute(
                    select(CalendarEvent).where(
                        and_(CalendarEvent.id == event_id, CalendarEvent.user_id == ctx.user_id)
                    )
                )
                event = result.scalar_one_or_none()
                if not event:
                    return {"error": "Event not found"}
                if "title" in kwargs and kwargs["title"] is not None:
                    event.title = kwargs["title"]
                if "description" in kwargs:
                    event.description = kwargs["description"]
                if "start_time" in kwargs and kwargs["start_time"] is not None:
                    try:
                        event.start_time = parse_iso_datetime(kwargs["start_time"])
                    except ValueError as e:
                        return {"error": f"Invalid start_time: {e}"}
                if "end_time" in kwargs:
                    if kwargs["end_time"] is None:
                        event.end_time = None
                    else:
                        try:
                            event.end_time = parse_iso_datetime(kwargs["end_time"])
                        except ValueError as e:
                            return {"error": f"Invalid end_time: {e}"}
                if "all_day" in kwargs and kwargs["all_day"] is not None:
                    all_day = kwargs["all_day"]
                    if isinstance(all_day, str):
                        all_day = all_day.lower() in ("true", "1", "yes")
                    event.all_day = all_day
                if "recurrence" in kwargs:
                    event.recurrence = kwargs["recurrence"]
                await session.commit()
                return {"success": True, "event_id": event.id, "title": event.title}

            return {"error": f"Unknown action: {action}"}


tool = CalendarTool()
