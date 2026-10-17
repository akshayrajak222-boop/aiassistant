"""
tests/test_tools.py – Agent tool schema validation, timeout, and execution tests.
"""

import asyncio
import pytest

from backend.tools.base import BaseTool, ToolResult
from backend.tools.builtin import GetCurrentTimeTool, WebSearchTool
from backend.tools.registry import ToolRegistry


class SlowTimeoutTool(BaseTool):
    name = "slow_timeout_tool"
    description = "A tool that sleeps longer than its timeout limit."
    parameters_schema = {"type": "object", "properties": {}}
    timeout_seconds = 1

    async def execute(self, args, user_id, context=None):
        await asyncio.sleep(2)
        return ToolResult(success=True, data="finished", error=None, metadata={})


class ValidatedTool(BaseTool):
    name = "validated_tool"
    description = "Requires specific input parameters."
    parameters_schema = {
        "type": "object",
        "properties": {"required_key": {"type": "string"}},
        "required": ["required_key"],
    }

    async def execute(self, args, user_id, context=None):
        return ToolResult(success=True, data=args["required_key"], error=None, metadata={})


@pytest.mark.asyncio
async def test_tool_registry_registration():
    reg = ToolRegistry()
    tool = GetCurrentTimeTool()
    reg.register(tool)

    assert "get_current_time" in reg.list_tools()
    schemas = reg.get_all_schemas()
    assert len(schemas) == 1
    assert schemas[0]["name"] == "get_current_time"


@pytest.mark.asyncio
async def test_tool_execution_success():
    reg = ToolRegistry()
    reg.register(GetCurrentTimeTool())

    res = await reg.execute("get_current_time", {"timezone": "UTC"}, user_id="user_123")
    assert res["success"] is True
    assert "current_time" in res["data"]
    assert res["data"]["timezone"] == "UTC"


@pytest.mark.asyncio
async def test_tool_timeout_enforcement():
    reg = ToolRegistry()
    reg.register(SlowTimeoutTool())

    res = await reg.execute("slow_timeout_tool", {}, user_id="user_123")
    assert res["success"] is False
    assert "timed out" in res["error"]
    assert res["metadata"].get("timed_out") is True


@pytest.mark.asyncio
async def test_tool_parameter_validation():
    reg = ToolRegistry()
    reg.register(ValidatedTool())

    # Missing required key
    res = await reg.execute("validated_tool", {}, user_id="user_123")
    assert res["success"] is False
    assert "Missing required parameter" in res["error"]

    # Valid call
    valid_res = await reg.execute("validated_tool", {"required_key": "val123"}, user_id="user_123")
    assert valid_res["success"] is True
    assert valid_res["data"] == "val123"
