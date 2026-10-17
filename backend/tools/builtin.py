"""
tools/builtin.py – Built-in system tools for agent tasks.
"""

from __future__ import annotations

import datetime
import os
import zoneinfo
import logging
from typing import Any
import httpx

from backend.tools.base import BaseTool, ToolResult
from backend.tools.registry import registry

logger = logging.getLogger(__name__)


class GetCurrentTimeTool(BaseTool):
    name = "get_current_time"
    description = "Get the current date and time, optionally in a specific timezone."
    parameters_schema = {
        "type": "object",
        "properties": {
            "timezone": {
                "type": "string",
                "description": "Timezone name (e.g., 'UTC', 'America/New_York', 'Europe/London'). Default is UTC or user timezone.",
            }
        },
        "required": [],
    }

    async def execute(
        self,
        args: dict[str, Any],
        user_id: str,
        context: dict[str, Any] | None = None,
    ) -> ToolResult:
        tz_name = args.get("timezone") or (context.get("timezone") if context else "UTC") or "UTC"
        try:
            tz = zoneinfo.ZoneInfo(tz_name)
        except Exception:
            tz = zoneinfo.ZoneInfo("UTC")
            tz_name = "UTC (fallback)"

        now = datetime.datetime.now(tz)
        formatted = now.strftime("%Y-%m-%d %H:%M:%S %Z (Day %A)")
        return ToolResult(
            success=True,
            data={"current_time": formatted, "iso": now.isoformat(), "timezone": tz_name},
            error=None,
            metadata={},
        )


class WebSearchTool(BaseTool):
    name = "web_search"
    description = "Search the web for up-to-date information, news, or reference documentation."
    parameters_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The search keywords or question."}
        },
        "required": ["query"],
    }
    timeout_seconds = 15

    async def execute(
        self,
        args: dict[str, Any],
        user_id: str,
        context: dict[str, Any] | None = None,
    ) -> ToolResult:
        query = args.get("query", "").strip()
        if not query:
            return ToolResult(success=False, data=None, error="Search query cannot be empty.", metadata={})

        try:
            # DuckDuckGo Instant Answer API (Free, no API key required)
            url = "https://api.duckduckgo.com/"
            params = {"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"}
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    abstract = data.get("AbstractText", "")
                    related = data.get("RelatedTopics", [])
                    results = []
                    if abstract:
                        results.append({"title": data.get("Heading", "Abstract"), "snippet": abstract, "url": data.get("AbstractURL", "")})

                    for item in related[:4]:
                        if isinstance(item, dict) and "Text" in item:
                            results.append({
                                "title": item.get("FirstURL", "").split("/")[-1].replace("_", " "),
                                "snippet": item.get("Text", ""),
                                "url": item.get("FirstURL", ""),
                            })

                    if not results:
                        results.append({
                            "title": "Search Query",
                            "snippet": f"No direct summary found on DuckDuckGo for '{query}'. Information may be too specific or recent.",
                            "url": f"https://duckduckgo.com/?q={query}",
                        })

                    return ToolResult(
                        success=True,
                        data={"query": query, "results": results},
                        error=None,
                        metadata={"count": len(results)},
                    )
                else:
                    return ToolResult(
                        success=False,
                        data=None,
                        error=f"Search provider returned status code {resp.status_code}",
                        metadata={},
                    )
        except Exception as exc:
            logger.warning(f"Web search failed: {exc}")
            return ToolResult(
                success=True,
                data={
                    "query": query,
                    "results": [
                        {
                            "title": "Search Query",
                            "snippet": f"Web search could not be completed at this moment ({str(exc)}).",
                            "url": f"https://duckduckgo.com/?q={query}",
                        }
                    ],
                },
                error=None,
                metadata={"fallback": True},
            )


class FileReadTool(BaseTool):
    name = "read_uploaded_file"
    description = "Safely read and inspect the content of an uploaded text, markdown, or data document."
    parameters_schema = {
        "type": "object",
        "properties": {
            "filename": {"type": "string", "description": "The name or path of the uploaded file to read."}
        },
        "required": ["filename"],
    }

    async def execute(
        self,
        args: dict[str, Any],
        user_id: str,
        context: dict[str, Any] | None = None,
    ) -> ToolResult:
        filename = args.get("filename", "")
        # Safe directory check
        upload_dir = os.environ.get("UPLOAD_DIR", "uploads")
        safe_path = os.path.abspath(os.path.join(upload_dir, os.path.basename(filename)))

        if not os.path.exists(safe_path):
            return ToolResult(
                success=False,
                data=None,
                error=f"File '{filename}' was not found in the uploads directory.",
                metadata={},
            )

        try:
            # Enforce 10MB limit
            if os.path.getsize(safe_path) > 10 * 1024 * 1024:
                return ToolResult(
                    success=False,
                    data=None,
                    error="File size exceeds the 10MB safety limit.",
                    metadata={},
                )

            with open(safe_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(50000)  # Max 50,000 characters
                truncated = len(content) == 50000

            return ToolResult(
                success=True,
                data={"filename": filename, "content": content, "truncated": truncated},
                error=None,
                metadata={"size_bytes": os.path.getsize(safe_path)},
            )
        except Exception as exc:
            return ToolResult(
                success=False,
                data=None,
                error=f"Failed to read file: {str(exc)}",
                metadata={},
            )


def register_builtin_tools() -> None:
    """Register all default built-in tools into the global registry."""
    registry.register(GetCurrentTimeTool())
    registry.register(WebSearchTool())
    registry.register(FileReadTool())
