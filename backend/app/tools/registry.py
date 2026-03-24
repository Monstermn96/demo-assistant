import importlib
import pkgutil
import logging
from app.tools.base import BaseTool

logger = logging.getLogger(__name__)

tool_registry: dict[str, BaseTool] = {}


def register_tool(tool: BaseTool):
    tool_registry[tool.name] = tool
    logger.info(f"Registered tool: {tool.name}")


def discover_tools():
    """Auto-discover and register all tool modules in this package."""
    import app.tools as tools_pkg

    for _, module_name, _ in pkgutil.iter_modules(tools_pkg.__path__):
        if module_name in ("base", "registry"):
            continue
        try:
            module = importlib.import_module(f"app.tools.{module_name}")
            if hasattr(module, "tool"):
                register_tool(module.tool)
        except Exception:
            logger.exception(f"Failed to load tool module: {module_name}")
