import asyncio
import json
import logging
from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.db.database import get_db
from app.db.models import User, Conversation, Message, UserSettings
from app.auth.middleware import get_current_user, get_current_user_flexible
from app.auth.security import decode_token
from app.settings.router import (
    get_or_create_settings,
    get_or_create_global_settings,
    get_effective_default_model,
    global_load_config_from_row,
)
from app.chat.models import ChatRequest, ChatResponse, ConversationSummary, MessageOut
from app.chat.manager import (
    get_or_create_conversation,
    get_context_messages,
    save_message,
    auto_title,
)
from app.llm.agent import run_agent
from app.agents.orchestrator import run_orchestrated_agent
from app.usage.client import log_event, get_client_ip

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("")
async def chat(
    body: ChatRequest,
    request: Request,
    user: User = Depends(get_current_user_flexible),
    db: AsyncSession = Depends(get_db),
):
    conv = await get_or_create_conversation(db, user.id, body.conversation_id)
    await auto_title(db, conv, body.message)
    await save_message(db, conv.id, "user", body.message)

    user_settings = await get_or_create_settings(db, user.id)
    global_row = await get_or_create_global_settings(db)
    model = body.model or get_effective_default_model(
        user_settings.default_model,
        global_row.default_model,
    )

    context = await get_context_messages(db, conv.id)
    await db.commit()

    load_config = global_load_config_from_row(global_row)
    accept = request.headers.get("accept", "")
    if "text/event-stream" in accept:
        return StreamingResponse(
            _sse_generator(context, model, user_settings, user.id, conv.id, db, load_config, global_row.reasoning_effort,
                           actor=user.username, prompt=body.message, client_ip=get_client_ip(request)),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    collected_events: list[dict] = []

    async def on_event(event: dict):
        collected_events.append({k: v for k, v in event.items() if k != "conversation_id"})

    result = await run_orchestrated_agent(
        context,
        model=model,
        temperature=user_settings.temperature,
        max_tokens=user_settings.max_tokens,
        top_p=user_settings.top_p,
        user_id=user.id,
        user_timezone=user_settings.timezone,
        on_event=on_event,
        load_config=load_config,
        reasoning_effort=global_row.reasoning_effort,
    )

    await save_message(
        db, conv.id, "assistant", result["content"],
        model=result.get("model"),
        agent_events=collected_events or None,
    )
    await db.commit()

    log_event(
        user.username, "chat",
        event_data={
            "conversation_id": conv.id,
            "model": result.get("model", model),
            "prompt": body.message,
            "response": result["content"],
            "tools_used": [e.get("tool") for e in collected_events if e.get("type") == "tool_call"],
        },
        ip_address=get_client_ip(request),
    )

    return ChatResponse(
        conversation_id=conv.id,
        message=result["content"],
        model=result.get("model", ""),
    )


async def _sse_generator(context, model, user_settings, user_id, conv_id, db, load_config=None, reasoning_effort=None,
                         actor=None, prompt=None, client_ip=None):
    queue: asyncio.Queue = asyncio.Queue()
    collected_events: list[dict] = []

    async def on_token(token: str):
        await queue.put({"type": "token", "content": token, "conversation_id": conv_id})

    async def on_event(event: dict):
        collected_events.append({k: v for k, v in event.items() if k != "conversation_id"})
        event["conversation_id"] = conv_id
        await queue.put(event)

    async def run():
        try:
            result = await run_orchestrated_agent(
                context,
                model=model,
                on_token=on_token,
                on_event=on_event,
                temperature=user_settings.temperature,
                max_tokens=user_settings.max_tokens,
                top_p=user_settings.top_p,
                user_id=user_id,
                user_timezone=user_settings.timezone,
                load_config=load_config,
                reasoning_effort=reasoning_effort,
            )
            await save_message(
                db, conv_id, "assistant", result["content"],
                model=result.get("model"),
                agent_events=collected_events or None,
            )
            await db.commit()
            if actor:
                log_event(
                    actor, "chat",
                    event_data={
                        "conversation_id": conv_id,
                        "model": result.get("model", model),
                        "prompt": prompt,
                        "response": result["content"],
                        "tools_used": [e.get("tool") for e in collected_events if e.get("type") == "tool_call"],
                    },
                    ip_address=client_ip,
                )
            await queue.put({"type": "done", "conversation_id": conv_id, "model": result.get("model", "")})
        except Exception as e:
            logger.exception("SSE agent error")
            await queue.put({"type": "error", "content": str(e)})
        await queue.put(None)

    task = asyncio.create_task(run())

    try:
        while True:
            event = await queue.get()
            if event is None:
                break
            yield f"data: {json.dumps(event)}\n\n"
    finally:
        if not task.done():
            task.cancel()


@router.get("/conversations", response_model=list[ConversationSummary])
async def list_conversations(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(Conversation.updated_at.desc())
    )
    return [
        ConversationSummary(
            id=c.id, title=c.title, created_at=c.created_at, updated_at=c.updated_at
        )
        for c in result.scalars().all()
    ]


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageOut])
async def get_messages(
    conversation_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id, Conversation.user_id == user.id
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Conversation not found")

    msgs = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    return [
        MessageOut(
            id=m.id,
            role=m.role,
            content=m.content,
            tool_calls=m.tool_calls,
            model=m.model,
            agent_events=m.agent_events,
            created_at=m.created_at,
        )
        for m in msgs.scalars().all()
    ]


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id, Conversation.user_id == user.id
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    await db.delete(conv)
    await db.commit()
    return {"success": True}


@router.websocket("/ws")
async def websocket_chat(ws: WebSocket):
    await ws.accept()

    token = ws.query_params.get("token", "")
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        await ws.close(code=4001, reason="Unauthorized")
        return

    user_id = int(payload["sub"])

    try:
        while True:
            data = await ws.receive_json()
            message = data.get("message", "")
            conversation_id = data.get("conversation_id")
            model = data.get("model")

            async with get_db_session() as db:
                conv = await get_or_create_conversation(db, user_id, conversation_id)
                await auto_title(db, conv, message)
                await save_message(db, conv.id, "user", message)

                user_settings = await get_or_create_settings(db, user_id)
                global_row = await get_or_create_global_settings(db)
                effective_model = model or get_effective_default_model(
                    user_settings.default_model,
                    global_row.default_model,
                )
                load_config = global_load_config_from_row(global_row)

                context = await get_context_messages(db, conv.id)
                await db.commit()

                full_response = []
                collected_events: list[dict] = []

                async def on_token(token: str):
                    full_response.append(token)
                    await ws.send_json({"type": "token", "content": token, "conversation_id": conv.id})

                async def on_event(event: dict):
                    collected_events.append({k: v for k, v in event.items() if k != "conversation_id"})
                    event["conversation_id"] = conv.id
                    await ws.send_json(event)

                try:
                    result = await run_orchestrated_agent(
                        context,
                        model=effective_model,
                        on_token=on_token,
                        on_event=on_event,
                        temperature=user_settings.temperature,
                        max_tokens=user_settings.max_tokens,
                        top_p=user_settings.top_p,
                        user_id=user_id,
                        user_timezone=user_settings.timezone,
                        load_config=load_config,
                        reasoning_effort=global_row.reasoning_effort,
                    )
                except Exception as agent_err:
                    logger.exception("Agent error during streaming")
                    content = "".join(full_response) or f"Sorry, something went wrong: {agent_err}"
                    await save_message(
                        db, conv.id, "assistant", content,
                        model=effective_model,
                        agent_events=collected_events or None,
                    )
                    await db.commit()
                    ws_user_err = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
                    log_event(
                        ws_user_err.username if ws_user_err else str(user_id), "chat",
                        event_data={
                            "conversation_id": conv.id,
                            "model": effective_model,
                            "prompt": message,
                            "response": content,
                            "error": str(agent_err),
                            "transport": "websocket",
                        },
                    )
                    await ws.send_json({"type": "error", "content": str(agent_err), "conversation_id": conv.id})
                    await ws.send_json({"type": "done", "conversation_id": conv.id, "model": effective_model or ""})
                    continue

                saved_content = "".join(full_response) if full_response else result["content"]
                await save_message(
                    db, conv.id, "assistant", saved_content,
                    model=result.get("model"),
                    agent_events=collected_events or None,
                )
                await db.commit()

                ws_user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
                ws_username = ws_user.username if ws_user else str(user_id)
                log_event(
                    ws_username, "chat",
                    event_data={
                        "conversation_id": conv.id,
                        "model": result.get("model", effective_model),
                        "prompt": message,
                        "response": saved_content,
                        "tools_used": [e.get("tool") for e in collected_events if e.get("type") == "tool_call"],
                        "transport": "websocket",
                    },
                )

                await ws.send_json({
                    "type": "done",
                    "conversation_id": conv.id,
                    "model": result.get("model", ""),
                })

    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("WebSocket error")
        try:
            await ws.close(code=1011)
        except Exception:
            pass


def get_db_session():
    from app.db.database import async_session
    return async_session()
