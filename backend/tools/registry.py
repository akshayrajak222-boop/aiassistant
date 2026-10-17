"""
tools/registry.py – Central Tool Registry for agent capabilities.
"""

from __future__ import annotations

import inspect
import logging
from typing import Any, Callable
from backend.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Registry maintaining available tools, permission checks, schemas, and execution."""

    def __init__(self) -> None:
        self._tools: dict[str, Any] = {}
        self._schemas: dict[str, dict[str, Any]] = {}

    def register(self, tool: Any, name: str | None = None, schema: dict[str, Any] | None = None) -> None:
        """Register a tool instance."""
        tool_name = name or getattr(tool, "name", tool.__class__.__name__)
        self._tools[tool_name] = tool

        if schema:
            self._schemas[tool_name] = schema
        elif hasattr(tool, "parameters_schema"):
            self._schemas[tool_name] = {
                "name": tool_name,
                "description": getattr(tool, "description", tool.__doc__ or ""),
                "parameters": tool.parameters_schema,
            }
        elif hasattr(tool, "__doc__"):
            self._schemas[tool_name] = {
                "name": tool_name,
                "description": tool.__doc__ or tool_name,
                "parameters": {"type": "object", "properties": {}},
            }
        logger.info(f"Registered tool: {tool_name}")

    def get_tool(self, name: str) -> Any | None:
        return self._tools.get(name)

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    def get_all_schemas(self) -> list[dict[str, Any]]:
        """Return JSON Schema descriptions for all registered tools."""
        return list(self._schemas.values())

    async def execute(
        self,
        name: str,
        args: dict[str, Any],
        user_id: str,
        context: dict[str, Any] | None = None,
    ) -> ToolResult:
        """Execute a tool by name with safety checks."""
        tool = self.get_tool(name)
        if not tool:
            return ToolResult(
                success=False,
                data=None,
                error=f"Tool '{name}' is not registered.",
                metadata={"tool_name": name},
            )

        # Audit log execution attempt
        logger.info(f"Executing tool '{name}' for user '{user_id}' with args: {list(args.keys())}")

        try:
            if hasattr(tool, "run"):
                # Handle BaseTool or email tool with .run()
                # Check signature of run
                sig = inspect.signature(tool.run)
                kwargs = dict(args)
                if "user_id" in sig.parameters and "user_id" not in kwargs:
                    kwargs["user_id"] = user_id
                if "context" in sig.parameters and "context" not in kwargs:
                    kwargs["context"] = context or {}

                res = await tool.run(**kwargs)
                if isinstance(res, dict):
                    return res  # type: ignore
                elif hasattr(res, "dict"):
                    d = res.dict()
                    return ToolResult(
                        success=d.get("success", True),
                        data=d.get("data"),
                        error=d.get("error"),
                        metadata={"type": type(res).__name__},
                    )
                return ToolResult(success=True, data=res, error=None, metadata={})
            elif hasattr(tool, "execute"):
                return await tool.execute(args, user_id, context or {})
            elif callable(tool):
                res = await tool(args, user_id=user_id, context=context)
                return ToolResult(success=True, data=res, error=None, metadata={})
            else:
                return ToolResult(
                    success=False,
                    data=None,
                    error=f"Tool '{name}' does not provide a callable interface.",
                    metadata={},
                )
        except Exception as exc:
            logger.exception(f"Tool execution exception in '{name}'")
            return ToolResult(
                success=False,
                data=None,
                error=f"Error executing tool '{name}': {str(exc)}",
                metadata={"exception": type(exc).__name__},
            )


# Global singleton
registry = ToolRegistry()
