from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.middleware import get_current_user
from app.calendar.models import BulkDeleteBody, CalendarEventCreate, CalendarEventUpdate, CalendarEventOut
from app.db.database import get_db
from app.db.models import User, CalendarEvent
from app.usage.client import log_event, get_client_ip

router = APIRouter(prefix="/calendar", tags=["calendar"])


def _event_to_out(e: CalendarEvent) -> CalendarEventOut:
    return CalendarEventOut(
        id=e.id,
        title=e.title,
        description=e.description,
        start_time=e.start_time,
        end_time=e.end_time,
        all_day=e.all_day,
        recurrence=e.recurrence,
        created_at=e.created_at,
    )


@router.get("/events", response_model=list[CalendarEventOut])
async def list_events(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    start_date: date | None = Query(default=None, description="Filter events overlapping from this date"),
    end_date: date | None = Query(default=None, description="Filter events overlapping until this date"),
):
    q = select(CalendarEvent).where(CalendarEvent.user_id == user.id).order_by(CalendarEvent.start_time.asc())
    result = await db.execute(q)
    events = list(result.scalars().all())

    if start_date is not None or end_date is not None:
        filtered = []
        for e in events:
            event_start = e.start_time.date()
            event_end = (e.end_time.date() if e.end_time else event_start)
            if start_date is not None and event_end < start_date:
                continue
            if end_date is not None and event_start > end_date:
                continue
            filtered.append(e)
        events = filtered

    return [_event_to_out(e) for e in events]


@router.post("/events", response_model=CalendarEventOut, status_code=201)
async def create_event(
    body: CalendarEventCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    event = CalendarEvent(
        user_id=user.id,
        title=body.title,
        description=body.description,
        start_time=body.start_time,
        end_time=body.end_time,
        all_day=body.all_day,
        recurrence=body.recurrence,
    )
    db.add(event)
    await db.flush()
    log_event(user.username, "calendar_create", event_data={"title": body.title, "start_time": str(body.start_time)}, ip_address=get_client_ip(request))
    return _event_to_out(event)


@router.get("/events/{event_id}", response_model=CalendarEventOut)
async def get_event(
    event_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CalendarEvent).where(CalendarEvent.id == event_id, CalendarEvent.user_id == user.id)
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return _event_to_out(event)


@router.put("/events/{event_id}", response_model=CalendarEventOut)
async def update_event(
    event_id: int,
    body: CalendarEventUpdate,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CalendarEvent).where(CalendarEvent.id == event_id, CalendarEvent.user_id == user.id)
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(event, field, value)

    await db.flush()
    log_event(user.username, "calendar_update", event_data={"event_id": event_id, "title": event.title}, ip_address=get_client_ip(request))
    return _event_to_out(event)


@router.delete("/events/{event_id}")
async def delete_event(
    event_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CalendarEvent).where(CalendarEvent.id == event_id, CalendarEvent.user_id == user.id)
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    title = event.title
    await db.delete(event)
    log_event(user.username, "calendar_delete", event_data={"event_id": event_id, "title": title}, ip_address=get_client_ip(request))
    return {"success": True, "deleted_id": event_id}


@router.post("/events/bulk-delete")
async def bulk_delete_events(
    body: BulkDeleteBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    deleted_ids: list[int] = []
    for event_id in body.event_ids:
        result = await db.execute(
            select(CalendarEvent).where(
                CalendarEvent.id == event_id,
                CalendarEvent.user_id == user.id,
            )
        )
        event = result.scalar_one_or_none()
        if event:
            await db.delete(event)
            deleted_ids.append(event_id)
    return {
        "success": True,
        "deleted_ids": deleted_ids,
        "deleted_count": len(deleted_ids),
    }
