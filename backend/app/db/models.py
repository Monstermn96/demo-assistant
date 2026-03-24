from sqlalchemy import Column, Integer, String, Text, DateTime, Float, ForeignKey, Boolean, JSON
from sqlalchemy.orm import DeclarativeBase, relationship
from datetime import datetime, timezone


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    nexus_id = Column(String(36), unique=True, nullable=True)
    username = Column(String(50), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    conversations = relationship("Conversation", back_populates="user")
    notes = relationship("Note", back_populates="user")
    calendar_events = relationship("CalendarEvent", back_populates="user")
    settings = relationship("UserSettings", back_populates="user", uselist=False)


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(200), default="New Conversation")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    role = Column(String(20), nullable=False)  # user, assistant, system, tool
    content = Column(Text, nullable=True)
    tool_calls = Column(JSON, nullable=True)
    tool_call_id = Column(String(100), nullable=True)
    model = Column(String(100), nullable=True)
    agent_events = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    conversation = relationship("Conversation", back_populates="messages")


class Note(Base):
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(Text, nullable=True)  # JSON-serialized float array
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="notes")


class CalendarEvent(Base):
    __tablename__ = "calendar_events"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=True)
    all_day = Column(Boolean, default=False)
    recurrence = Column(String(50), nullable=True)  # daily, weekly, monthly, yearly
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="calendar_events")


class UserSettings(Base):
    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    default_model = Column(String(200), nullable=True)
    temperature = Column(Float, default=0.7)
    max_tokens = Column(Integer, default=-1)  # -1 = unlimited / model decides
    top_p = Column(Float, default=1.0)
    context_length = Column(Integer, nullable=True)  # null = use model default
    chat_verbosity = Column(String(20), default="standard")  # minimal, standard, detailed, developer
    chat_style = Column(String(20), default="bubbles")  # bubbles, flat, compact
    timezone = Column(String(64), nullable=True)  # IANA timezone e.g. America/New_York
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user = relationship("User", back_populates="settings")


class GlobalSettings(Base):
    """Single-row table: household default model and load config (shared by all users)."""
    __tablename__ = "global_settings"

    id = Column(Integer, primary_key=True)
    default_model = Column(String(200), nullable=True)
    context_length = Column(Integer, nullable=True)
    num_experts = Column(Integer, nullable=True)
    flash_attention = Column(Boolean, nullable=True)
    eval_batch_size = Column(Integer, nullable=True)
    offload_kv_cache_to_gpu = Column(Boolean, nullable=True)
    reasoning_effort = Column(String(20), nullable=True)  # low, medium, high for chat
    keep_alive_interval_seconds = Column(Integer, nullable=True)  # 0 = disabled; ping interval to avoid LM Studio idle TTL unload
    max_concurrent_predictions = Column(Integer, nullable=True)  # LM Studio parallel request limit
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class Prompt(Base):
    __tablename__ = "prompts"

    id = Column(String(100), primary_key=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    agent = Column(String(100), nullable=True)
    content = Column(Text, nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
