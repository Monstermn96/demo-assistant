# AGENTS.md

## Cursor Cloud specific instructions

### Overview

DemoAssistant is a public demo fork of ARIM — a self-hosted personal AI assistant with a **Python/FastAPI backend** and a **React/Vite frontend**. No smart home integration. See `README.md` for features.

### Services

| Service | Port | Command | Notes |
|---------|------|---------|-------|
| Backend (FastAPI) | 3093 | `cd backend && source venv/bin/activate && uvicorn app.main:app --reload --port 3093` | Serves API; logs warnings if LM Studio is unreachable but starts fine |
| Frontend (Vite) | 5173 | `cd frontend && npm run dev` | Proxies `/api` to `localhost:3093` (see `vite.config.ts`) |

### Running tests

- **Backend**: `cd backend && source venv/bin/activate && pytest -v` (uses in-memory SQLite, no external deps)
- **Frontend**: `cd frontend && npm run test` (vitest)
- **Frontend lint**: `cd frontend && npm run lint` (eslint)

### Authentication caveat

All auth endpoints (login, register, setup) require a running **Nexus** identity service (`NEXUS_URL` in `.env`). Guest login also requires Nexus with `guest_enabled: true` for the `demo-assistant` app. Without Nexus, you cannot log in through the UI. To bypass for development/testing, create a user directly in the database and generate JWT tokens programmatically:

```python
cd backend && source venv/bin/activate && python3 -c "
import asyncio
from app.db.database import init_db, async_session
from app.db.models import User
from app.auth.security import hash_password, create_access_token

async def create_user():
    await init_db()
    async with async_session() as db:
        user = User(username='admin', hashed_password=hash_password('Admin1234'))
        db.add(user)
        await db.flush()
        await db.commit()
        print(create_access_token(user.id))

asyncio.run(create_user())
"
```

Then inject the token into the browser via `localStorage.setItem('access_token', '<token>')` and reload.

### Notes endpoint gotcha

The `POST /api/notes` endpoint attempts to generate embeddings via LM Studio. Without LM Studio running, this request will hang ~10 seconds before timing out and storing the note without an embedding. Other endpoints (calendar, settings, health, etc.) work instantly without LM Studio.

### Environment file

The backend reads `.env` from its own directory (`backend/.env`). Copy `../.env.example` to `backend/.env` for initial setup. The app will start with default config values even without a `.env` file.

### Pre-existing test issues

- 2 backend tests (`test_get_settings_default`, `test_clear_default_model`) fail because they expect `default_model` to be `None` but the config provides a default value from `.env`. These are pre-existing.
- Frontend ESLint reports some errors (mostly `@typescript-eslint/no-explicit-any`) and warnings. These are pre-existing.
