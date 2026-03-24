import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.db.models import Base
from app.db.database import get_db
from app.auth.security import hash_password, create_access_token
from app.main import app

# ---------------------------------------------------------------------------
# In-memory async SQLite engine & session, rebuilt per-test
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = "sqlite+aiosqlite://"


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session


# ---------------------------------------------------------------------------
# Override the FastAPI get_db dependency so all requests use the test DB
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def client(db_engine):
    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def _override_get_db():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Authenticated client — creates a test user and provides a valid JWT
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def auth_client(db_engine):
    """Yields (AsyncClient, user_id) with a valid Authorization header."""
    from app.db.models import User

    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    # Create a test user
    async with session_factory() as session:
        user = User(username="testuser", hashed_password=hash_password("testpass"))
        session.add(user)
        await session.flush()
        user_id = user.id
        await session.commit()

    token = create_access_token(user_id)

    async def _override_get_db():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
        headers={"Authorization": f"Bearer {token}"},
    ) as ac:
        yield ac, user_id

    app.dependency_overrides.clear()
