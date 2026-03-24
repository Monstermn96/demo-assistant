import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import User
from app.auth.middleware import get_current_user
from app.prompts import manager as prompt_mgr

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/prompts", tags=["prompts"])


class PromptOut(BaseModel):
    id: str
    name: str
    description: str
    agent: str
    content: str
    updated_at: str


class PromptSummaryOut(BaseModel):
    id: str
    name: str
    description: str
    agent: str
    updated_at: str


class PromptUpdateIn(BaseModel):
    content: str


@router.get("", response_model=list[PromptSummaryOut])
async def list_prompts(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    prompts = await prompt_mgr.list_prompts(db)
    return [
        PromptSummaryOut(
            id=p.id,
            name=p.name,
            description=p.description or "",
            agent=p.agent or "",
            updated_at=p.updated_at.isoformat() if p.updated_at else "",
        )
        for p in prompts
    ]


@router.get("/{prompt_id}", response_model=PromptOut)
async def get_prompt(
    prompt_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    p = await prompt_mgr.get_prompt_full(db, prompt_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return PromptOut(
        id=p.id,
        name=p.name,
        description=p.description or "",
        agent=p.agent or "",
        content=p.content,
        updated_at=p.updated_at.isoformat() if p.updated_at else "",
    )


@router.put("/{prompt_id}", response_model=PromptOut)
async def update_prompt(
    prompt_id: str,
    body: PromptUpdateIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    p = await prompt_mgr.update_prompt(db, prompt_id, body.content)
    if p is None:
        raise HTTPException(status_code=404, detail="Prompt not found")
    await db.commit()
    return PromptOut(
        id=p.id,
        name=p.name,
        description=p.description or "",
        agent=p.agent or "",
        content=p.content,
        updated_at=p.updated_at.isoformat() if p.updated_at else "",
    )


@router.get("/{prompt_id}/download")
async def download_prompt(
    prompt_id: str,
    token: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    p = await prompt_mgr.get_prompt_full(db, prompt_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Prompt not found")
    md_content = prompt_mgr.export_prompt_md(p)
    return PlainTextResponse(
        content=md_content,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{prompt_id}.md"'},
    )


@router.post("/{prompt_id}/reset", response_model=PromptOut)
async def reset_prompt(
    prompt_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    p = await prompt_mgr.reset_prompt(db, prompt_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Prompt or seed file not found")
    await db.commit()
    return PromptOut(
        id=p.id,
        name=p.name,
        description=p.description or "",
        agent=p.agent or "",
        content=p.content,
        updated_at=p.updated_at.isoformat() if p.updated_at else "",
    )
