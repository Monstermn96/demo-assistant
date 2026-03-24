import json
import logging
import numpy as np
from sqlalchemy import select
from app.tools.base import BaseTool, ToolContext
from app.db.database import async_session
from app.db.models import Note

logger = logging.getLogger(__name__)


class NotesTool(BaseTool):
    name = "notes"
    description = "Create, list, search, and delete personal notes. Search uses semantic embeddings for intelligent matching."

    def schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["create", "list", "search", "get", "delete"],
                        "description": "The action to perform",
                    },
                    "title": {"type": "string", "description": "Note title"},
                    "content": {"type": "string", "description": "Note content"},
                    "query": {"type": "string", "description": "Search query for semantic search"},
                    "note_id": {"type": "integer", "description": "Note ID"},
                },
                "required": ["action"],
            },
        }

    async def execute(self, ctx: ToolContext, action: str, **kwargs) -> dict:
        async with async_session() as session:
            if action == "create":
                title = kwargs.get("title", "Untitled")
                content = kwargs.get("content", "")

                embedding_data = None
                try:
                    from app.llm.client import get_embedding
                    embedding = await get_embedding(f"{title}\n{content}")
                    embedding_data = json.dumps(embedding)
                except Exception:
                    logger.debug("Embedding unavailable, creating note without embedding")

                note = Note(
                    user_id=ctx.user_id,
                    title=title,
                    content=content,
                    embedding=embedding_data,
                )
                session.add(note)
                await session.commit()
                return {"success": True, "note_id": note.id, "title": note.title}

            elif action == "list":
                result = await session.execute(
                    select(Note).where(Note.user_id == ctx.user_id).order_by(Note.updated_at.desc())
                )
                notes = result.scalars().all()
                return {
                    "notes": [
                        {"id": n.id, "title": n.title, "updated_at": n.updated_at.isoformat()}
                        for n in notes
                    ]
                }

            elif action == "search":
                query = kwargs.get("query", "")

                query_embedding = None
                try:
                    from app.llm.client import get_embedding
                    query_embedding = np.array(await get_embedding(query))
                except Exception:
                    logger.debug("Embedding unavailable, falling back to text search")

                result = await session.execute(
                    select(Note).where(Note.user_id == ctx.user_id)
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
                    return {
                        "results": [
                            {
                                "id": note.id,
                                "title": note.title,
                                "content": note.content[:500],
                                "score": round(score, 4),
                            }
                            for score, note in scored[:5]
                        ]
                    }
                else:
                    q = query.lower()
                    matched = [
                        n for n in notes
                        if q in n.title.lower() or q in n.content.lower()
                    ][:5]
                    return {
                        "results": [
                            {"id": n.id, "title": n.title, "content": n.content[:500]}
                            for n in matched
                        ]
                    }

            elif action == "get":
                note_id = kwargs.get("note_id")
                result = await session.execute(
                    select(Note).where(Note.id == note_id, Note.user_id == ctx.user_id)
                )
                note = result.scalar_one_or_none()
                if not note:
                    return {"error": "Note not found"}
                return {"id": note.id, "title": note.title, "content": note.content}

            elif action == "delete":
                note_id = kwargs.get("note_id")
                result = await session.execute(
                    select(Note).where(Note.id == note_id, Note.user_id == ctx.user_id)
                )
                note = result.scalar_one_or_none()
                if not note:
                    return {"error": "Note not found"}
                await session.delete(note)
                await session.commit()
                return {"success": True, "deleted_id": note_id}

            return {"error": f"Unknown action: {action}"}


tool = NotesTool()
