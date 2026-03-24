from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models import Conversation, Message


MAX_CONTEXT_MESSAGES = 50


async def get_or_create_conversation(
    db: AsyncSession, user_id: int, conversation_id: int | None = None
) -> Conversation:
    if conversation_id:
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
            )
        )
        conv = result.scalar_one_or_none()
        if conv:
            return conv

    conv = Conversation(user_id=user_id)
    db.add(conv)
    await db.flush()
    return conv


async def get_context_messages(db: AsyncSession, conversation_id: int) -> list[dict]:
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    messages = result.scalars().all()

    context = []
    for msg in messages[-MAX_CONTEXT_MESSAGES:]:
        entry = {"role": msg.role, "content": msg.content or ""}
        if msg.tool_calls:
            entry["tool_calls"] = msg.tool_calls
        if msg.tool_call_id:
            entry["tool_call_id"] = msg.tool_call_id
        context.append(entry)

    return context


async def save_message(
    db: AsyncSession,
    conversation_id: int,
    role: str,
    content: str | None,
    model: str | None = None,
    tool_calls: dict | list | None = None,
    tool_call_id: str | None = None,
    agent_events: list | None = None,
) -> Message:
    msg = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        model=model,
        tool_calls=tool_calls,
        tool_call_id=tool_call_id,
        agent_events=agent_events,
    )
    db.add(msg)
    await db.flush()
    return msg


async def auto_title(db: AsyncSession, conversation: Conversation, user_message: str):
    """Set title from first user message if still default."""
    if conversation.title == "New Conversation":
        conversation.title = user_message[:100].strip() or "Chat"
        await db.flush()
