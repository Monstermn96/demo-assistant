import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
from app.config import get_settings
from app.db.database import init_db
from app.tools.registry import discover_tools
from app.auth.router import router as auth_router
from app.chat.router import router as chat_router
from app.settings.router import router as settings_router
from app.notes.router import router as notes_router
from app.account.router import router as account_router
from app.tts.router import router as tts_router
from app.prompts.router import router as prompts_router
from app.calendar.router import router as calendar_router
from app.prompts.manager import seed_prompts
from app.llm.client import list_models, list_models_native, llm_manager
from app.settings.router import get_or_create_global_settings, global_load_config_from_row

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
settings = get_settings()

STATIC_DIR = Path(__file__).parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting DemoAssistant...")
    Path("data").mkdir(exist_ok=True)
    await init_db()
    discover_tools()

    from app.db.database import async_session
    async with async_session() as db:
        await seed_prompts(db)
        await db.commit()
        global_row = await get_or_create_global_settings(db)
        await db.commit()
        load_config = global_load_config_from_row(global_row)
        keep_alive = (global_row.keep_alive_interval_seconds if global_row.keep_alive_interval_seconds is not None else None) or getattr(settings, "lm_studio_keep_alive_interval_seconds", 0) or 0
        llm_manager.set_keep_alive_interval(keep_alive)

    try:
        await llm_manager.ensure_ready(load_config=load_config)
    except Exception:
        logger.warning("Could not pre-load models; LM Studio may be unavailable")

    logger.info("DemoAssistant ready")
    yield


app = FastAPI(title="DemoAssistant", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(settings_router, prefix="/api")
app.include_router(notes_router, prefix="/api")
app.include_router(account_router, prefix="/api")
app.include_router(tts_router, prefix="/api")
app.include_router(prompts_router, prefix="/api")
app.include_router(calendar_router, prefix="/api")


@app.get("/api/models")
async def get_models():
    try:
        models = await list_models_native()
        if not models:
            models = await list_models()
        for m in models:
            if "owned_by" not in m and "publisher" in m:
                m["owned_by"] = m.get("publisher", "")
        return {"models": models}
    except Exception as e:
        return {"models": [], "error": str(e)}


@app.get("/api/health")
async def health():
    return {"status": "ok", "name": settings.app_name}


if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{path:path}")
    async def serve_spa(path: str):
        file_path = STATIC_DIR / path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(STATIC_DIR / "index.html")
