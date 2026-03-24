import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import get_settings
from app.db.models import Base

log = logging.getLogger(__name__)

settings = get_settings()
engine = create_async_engine(settings.database_url, echo=settings.debug)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def _run_migrations(conn):
    """Add columns that create_all won't add to existing tables."""
    try:
        await conn.execute(text("SELECT nexus_id FROM users LIMIT 1"))
    except Exception:
        log.info("Adding nexus_id column to users table")
        await conn.execute(text("ALTER TABLE users ADD COLUMN nexus_id VARCHAR(36)"))
        await conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_nexus_id ON users(nexus_id)"))

    try:
        await conn.execute(text("SELECT chat_verbosity FROM user_settings LIMIT 1"))
    except Exception:
        log.info("Adding chat_verbosity and chat_style columns to user_settings")
        await conn.execute(text("ALTER TABLE user_settings ADD COLUMN chat_verbosity VARCHAR(20) DEFAULT 'standard'"))
        await conn.execute(text("ALTER TABLE user_settings ADD COLUMN chat_style VARCHAR(20) DEFAULT 'bubbles'"))

    try:
        await conn.execute(text("SELECT timezone FROM user_settings LIMIT 1"))
    except Exception:
        log.info("Adding timezone column to user_settings")
        await conn.execute(text("ALTER TABLE user_settings ADD COLUMN timezone VARCHAR(64)"))

    try:
        await conn.execute(text("SELECT agent_events FROM messages LIMIT 1"))
    except Exception:
        log.info("Adding agent_events column to messages table")
        await conn.execute(text("ALTER TABLE messages ADD COLUMN agent_events JSON"))

    try:
        await conn.execute(text("SELECT id FROM global_settings LIMIT 1"))
    except Exception:
        log.info("Creating global_settings table")
        await conn.execute(text("""
            CREATE TABLE global_settings (
                id INTEGER NOT NULL PRIMARY KEY,
                default_model VARCHAR(200),
                context_length INTEGER,
                num_experts INTEGER,
                flash_attention BOOLEAN,
                eval_batch_size INTEGER,
                offload_kv_cache_to_gpu BOOLEAN,
                reasoning_effort VARCHAR(20),
                updated_at DATETIME
            )
        """))
        await conn.execute(text("INSERT INTO global_settings (id, updated_at) VALUES (1, datetime('now'))"))

    try:
        await conn.execute(text("SELECT keep_alive_interval_seconds FROM global_settings LIMIT 1"))
    except Exception:
        log.info("Adding keep_alive_interval_seconds to global_settings")
        await conn.execute(text("ALTER TABLE global_settings ADD COLUMN keep_alive_interval_seconds INTEGER"))
    try:
        await conn.execute(text("SELECT max_concurrent_predictions FROM global_settings LIMIT 1"))
    except Exception:
        log.info("Adding max_concurrent_predictions to global_settings")
        await conn.execute(text("ALTER TABLE global_settings ADD COLUMN max_concurrent_predictions INTEGER"))




async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _run_migrations(conn)


async def get_db() -> AsyncSession:
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
