"""
tools/base.py – Abstract base classes and data structures for the Agent Tool Registry.
"""

from __future__ import annotations

import abc
import asyncio
import logging
from typing import Any, TypedDict
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)


class ToolResult(TypedDict):
    success: bool
    data: Any
    error: str | None
    metadata: dict[str, Any]


class BaseTool(abc.ABC):
    """Abstract Base Class for all tools available to the Hermes / Assistant agent."""

    name: str
    description: str
    parameters_schema: dict[str, Any]
    required_permission: str = "general"
    timeout_seconds: int = 30

    @abc.abstractmethod
    async def execute(
        self,
        args: dict[str, Any],
        user_id: str,
        context: dict[str, Any] | None = None,
    ) -> ToolResult:
        """Execute the tool with validated arguments and return a ToolResult."""
        pass

    def validate_args(self, args: dict[str, Any]) -> dict[str, Any]:
        """Validate input arguments against parameters_schema if required properties are specified."""
        required = self.parameters_schema.get("required", [])
        for field in required:
            if field not in args:
                raise ValueError(f"Missing required parameter: '{field}' for tool '{self.name}'")
        return args

    async def run(
        self,
        args: dict[str, Any],
        user_id: str,
        context: dict[str, Any] | None = None,
    ) -> ToolResult:
        """Run tool with validation, timeout enforcement, and exception handling."""
        try:
            validated = self.validate_args(args)
            result = await asyncio.wait_for(
                self.execute(validated, user_id, context or {}),
                timeout=float(self.timeout_seconds),
            )
            return result
        except asyncio.TimeoutError:
            err_msg = f"Tool '{self.name}' timed out after {self.timeout_seconds} seconds."
            logger.warning(err_msg)
            return ToolResult(
                success=False,
                data=None,
                error=err_msg,
                metadata={"timed_out": True},
            )
        except Exception as exc:
            err_msg = f"Tool '{self.name}' failed: {str(exc)}"
            logger.exception(err_msg)
            return ToolResult(
                success=False,
                data=None,
                error=err_msg,
                metadata={"exception": type(exc).__name__},
            )
