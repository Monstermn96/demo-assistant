import json
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import get_db
from app.db.models import User, Note
from app.auth.middleware import get_current_user, get_current_user_flexible
from app.notes.models import NoteCreate, NoteUpdate, NoteOut, NoteSearch

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/notes", tags=["notes"])


@router.get("", response_model=list[NoteOut])
async def list_notes(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Note)
        .where(Note.user_id == user.id)
        .order_by(Note.updated_at.desc())
    )
    return [
        NoteOut(
            id=n.id,
            title=n.title,
            content=n.content,
            created_at=n.created_at,
            updated_at=n.updated_at,
        )
        for n in result.scalars().all()
    ]


@router.post("", response_model=NoteOut, status_code=201)
async def create_note(
    body: NoteCreate,
    user: User = Depends(get_current_user_flexible),
    db: AsyncSession = Depends(get_db),
):
    note = Note(user_id=user.id, title=body.title, content=body.content)

    # Attempt to generate embedding in the background; never block creation
    try:
        from app.llm.client import get_embedding
        embedding = await get_embedding(f"{body.title}\n{body.content}")
        note.embedding = json.dumps(embedding)
    except Exception:
        logger.debug("Embedding model unavailable, storing note without embedding")

    db.add(note)
    await db.flush()
    return NoteOut(
        id=note.id,
        title=note.title,
        content=note.content,
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


@router.get("/{note_id}", response_model=NoteOut)
async def get_note(
    note_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Note).where(Note.id == note_id, Note.user_id == user.id)
    )
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return NoteOut(
        id=note.id,
        title=note.title,
        content=note.content,
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


@router.put("/{note_id}", response_model=NoteOut)
async def update_note(
    note_id: int,
    body: NoteUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Note).where(Note.id == note_id, Note.user_id == user.id)
    )
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(note, field, value)

    # Re-compute embedding if title or content changed
    if "title" in update_data or "content" in update_data:
        try:
            from app.llm.client import get_embedding
            embedding = await get_embedding(f"{note.title}\n{note.content}")
            note.embedding = json.dumps(embedding)
        except Exception:
            pass

    await db.flush()
    return NoteOut(
        id=note.id,
        title=note.title,
        content=note.content,
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


@router.delete("/{note_id}")
async def delete_note(
    note_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Note).where(Note.id == note_id, Note.user_id == user.id)
    )
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    await db.delete(note)
    return {"success": True, "deleted_id": note_id}


@router.post("/search", response_model=list[NoteOut])
async def search_notes(
    body: NoteSearch,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Semantic search across notes. Falls back to title/content substring match if embeddings are unavailable."""
    import numpy as np

    try:
        from app.llm.client import get_embedding
        query_embedding = np.array(await get_embedding(body.query))
    except Exception:
        query_embedding = None

    result = await db.execute(
        select(Note).where(Note.user_id == user.id)
    )
    notes = result.scalars().all()

    if query_embedding is not None:
        scored = []
        for note in notes:
            if not note.embedding:
                continue
            note_emb = np.array(json.loads(note.embedding))
            similarity = float(np.dot(query_embedding, note_emb) / (
                np.linalg.norm(query_embedding) * np.linalg.norm(note_emb) + 1e-10
            ))
            scored.append((similarity, note))
        scored.sort(key=lambda x: x[0], reverse=True)
        results = [note for _, note in scored[:body.limit]]
    else:
        q = body.query.lower()
        results = [
            n for n in notes
            if q in n.title.lower() or q in n.content.lower()
        ][:body.limit]

    return [
        NoteOut(
            id=n.id,
            title=n.title,
            content=n.content,
            created_at=n.created_at,
            updated_at=n.updated_at,
        )
        for n in results
    ]
