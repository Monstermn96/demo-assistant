# DemoAssistant

A public demo fork of ARIM — a personal AI assistant with persistent memory, notes, calendar, web search, weather, and file browsing. No smart home integration.

## Stack

- **Backend**: FastAPI + SQLite + OpenAI-compatible client (LM Studio)
- **Frontend**: React 19 + Vite + Tailwind CSS (PWA)
- **Auth**: Nexus identity service (supports guest login)
- **Memory**: arim-memory service (optional)

## Features

- Chat with an AI assistant (streaming, tool use, reasoning display)
- Long-term memory (remember / recall / forget)
- Notes with semantic search
- Calendar (create, view, manage events)
- Weather lookup
- Web search
- Sandboxed file browser
- Guest login (no account required)
- Full user accounts with individual data isolation

## Deployment

Runs on port `3093`. Deployed via Woodpecker CI on push to `master`.

### Environment Variables

Copy `.env.example` to `.env` and fill in values. Key vars:

| Variable | Description |
|---|---|
| `LM_STUDIO_URL` | LM Studio base URL |
| `DEFAULT_MODEL` | Default chat model |
| `NEXUS_URL` | Nexus identity service URL |
| `NEXUS_API_KEY` | App API key from Nexus |
| `MEMORY_URL` | arim-memory service URL (optional) |
| `SECRET_KEY` | JWT signing key |
| `PORT` | App port (default 3093) |

---

*DemoAssistant is deployed at [demo.bischetsrieder-labs.com](https://demo.bischetsrieder-labs.com)*
