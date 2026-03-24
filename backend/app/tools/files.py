from pathlib import Path
from app.tools.base import BaseTool, ToolContext
from app.config import get_settings

settings = get_settings()


class FilesTool(BaseTool):
    name = "files"
    description = "List and read files in sandboxed directories."

    def schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list", "read"],
                        "description": "The action to perform",
                    },
                    "path": {
                        "type": "string",
                        "description": "File or directory path (relative to sandboxed root)",
                    },
                },
                "required": ["action", "path"],
            },
        }

    def _resolve_path(self, rel_path: str) -> Path | None:
        """Resolve and validate path is within a sandboxed directory."""
        for sandbox in settings.sandboxed_dirs:
            candidate = Path(sandbox) / rel_path
            try:
                resolved = candidate.resolve()
                if resolved.is_relative_to(Path(sandbox).resolve()):
                    return resolved
            except (ValueError, OSError):
                continue
        return None

    async def execute(self, ctx: ToolContext, action: str, path: str, **kwargs) -> dict:
        if not settings.sandboxed_dirs:
            return {"error": "No sandboxed directories configured"}

        resolved = self._resolve_path(path)
        if not resolved:
            return {"error": "Path is outside sandboxed directories"}

        if action == "list":
            if not resolved.is_dir():
                return {"error": "Not a directory"}
            entries = []
            for entry in sorted(resolved.iterdir()):
                entries.append({
                    "name": entry.name,
                    "type": "dir" if entry.is_dir() else "file",
                    "size": entry.stat().st_size if entry.is_file() else None,
                })
            return {"path": str(path), "entries": entries}

        elif action == "read":
            if not resolved.is_file():
                return {"error": "Not a file"}
            if resolved.stat().st_size > 1_000_000:
                return {"error": "File too large (>1MB)"}
            try:
                content = resolved.read_text(encoding="utf-8", errors="replace")
                return {"path": str(path), "content": content}
            except Exception as e:
                return {"error": str(e)}

        return {"error": f"Unknown action: {action}"}


tool = FilesTool()
