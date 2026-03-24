import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Prompt

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"

_cache: dict[str, str] = {}


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Parse a markdown file with --- delimited frontmatter."""
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", text, re.DOTALL)
    if not match:
        return {}, text.strip()

    meta = {}
    for line in match.group(1).strip().splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            meta[key.strip()] = val.strip()

    return meta, match.group(2).strip()


def _read_seed_files() -> list[dict]:
    """Read all .md files from the prompts directory."""
    seeds = []
    if not PROMPTS_DIR.exists():
        return seeds

    for path in sorted(PROMPTS_DIR.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
            meta, content = _parse_frontmatter(text)
            if "id" not in meta:
                continue
            seeds.append({
                "id": meta["id"],
                "name": meta.get("name", meta["id"]),
                "description": meta.get("description", ""),
                "agent": meta.get("agent", ""),
                "content": content,
                "filename": path.name,
            })
        except Exception:
            logger.exception(f"Failed to read seed file: {path}")

    return seeds


async def seed_prompts(db: AsyncSession):
    """Seed DB from .md files. Only inserts prompts that don't already exist."""
    seeds = _read_seed_files()
    inserted = 0

    for seed in seeds:
        result = await db.execute(
            select(Prompt).where(Prompt.id == seed["id"])
        )
        if result.scalar_one_or_none() is not None:
            continue

        prompt = Prompt(
            id=seed["id"],
            name=seed["name"],
            description=seed["description"],
            agent=seed["agent"],
            content=seed["content"],
        )
        db.add(prompt)
        inserted += 1

    if inserted > 0:
        await db.flush()
        logger.info(f"Seeded {inserted} prompts from files")

    _cache.clear()


async def get_prompt(db: AsyncSession, prompt_id: str) -> str:
    """Get prompt content by ID. Uses in-memory cache."""
    if prompt_id in _cache:
        return _cache[prompt_id]

    result = await db.execute(
        select(Prompt).where(Prompt.id == prompt_id)
    )
    prompt = result.scalar_one_or_none()
    if prompt is None:
        logger.warning(f"Prompt not found: {prompt_id}")
        return ""

    _cache[prompt_id] = prompt.content
    return prompt.content


async def get_prompt_full(db: AsyncSession, prompt_id: str) -> Prompt | None:
    result = await db.execute(
        select(Prompt).where(Prompt.id == prompt_id)
    )
    return result.scalar_one_or_none()


async def list_prompts(db: AsyncSession) -> list[Prompt]:
    result = await db.execute(select(Prompt).order_by(Prompt.name))
    return list(result.scalars().all())


async def update_prompt(db: AsyncSession, prompt_id: str, content: str) -> Prompt | None:
    result = await db.execute(
        select(Prompt).where(Prompt.id == prompt_id)
    )
    prompt = result.scalar_one_or_none()
    if prompt is None:
        return None

    prompt.content = content
    prompt.updated_at = datetime.now(timezone.utc)
    await db.flush()

    _cache.pop(prompt_id, None)
    return prompt


async def reset_prompt(db: AsyncSession, prompt_id: str) -> Prompt | None:
    """Reset a prompt to its seed file version."""
    seeds = _read_seed_files()
    seed = next((s for s in seeds if s["id"] == prompt_id), None)
    if seed is None:
        return None

    result = await db.execute(
        select(Prompt).where(Prompt.id == prompt_id)
    )
    prompt = result.scalar_one_or_none()
    if prompt is None:
        return None

    prompt.content = seed["content"]
    prompt.name = seed["name"]
    prompt.description = seed["description"]
    prompt.agent = seed["agent"]
    prompt.updated_at = datetime.now(timezone.utc)
    await db.flush()

    _cache.pop(prompt_id, None)
    return prompt


def export_prompt_md(prompt: Prompt) -> str:
    """Export a prompt as a markdown file with frontmatter."""
    lines = [
        "---",
        f"id: {prompt.id}",
        f"name: {prompt.name}",
    ]
    if prompt.description:
        lines.append(f"description: {prompt.description}")
    if prompt.agent:
        lines.append(f"agent: {prompt.agent}")
    lines.append("---")
    lines.append("")
    lines.append(prompt.content)
    return "\n".join(lines) + "\n"
