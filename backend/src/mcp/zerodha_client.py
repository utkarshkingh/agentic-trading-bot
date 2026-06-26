"""Zerodha Kite MCP client — wraps the official MCP Python SDK."""
import logging
from typing import Any, Optional

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from src.settings import settings

logger = logging.getLogger(__name__)


class ZerodhaMCPClient:
    """Persistent MCP client for Zerodha's Kite MCP server.

    The OAuth session must survive across tool calls, so we maintain a single
    session object. Reconnect automatically if the session drops.
    """

    def __init__(self, server_url: Optional[str] = None):
        self.server_url = server_url or settings.zerodha_mcp_url
        self.session: Optional[ClientSession] = None
        self._client_ctx = None

    async def connect(self) -> bool:
        if self.session:
            return True
        try:
            self._client_ctx = streamablehttp_client(self.server_url)
            read, write, _ = await self._client_ctx.__aenter__()
            self.session = ClientSession(read, write)
            await self.session.__aenter__()
            await self.session.initialize()
            logger.info("Connected to Zerodha MCP: %s", self.server_url)
            return True
        except Exception as e:
            logger.error("Zerodha MCP connect failed: %s", e)
            await self._cleanup()
            return False

    async def list_tools(self) -> list[dict[str, Any]]:
        if not self.session:
            raise RuntimeError("Not connected")
        result = await self.session.list_tools()
        return [
            {"name": t.name, "description": t.description, "schema": t.inputSchema}
            for t in result.tools
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if not self.session:
            raise RuntimeError("Not connected")
        result = await self.session.call_tool(name, arguments)
        texts = [c.text for c in result.content if hasattr(c, "text")]
        structured = getattr(result, "structuredContent", None)
        return {
            "success": True,
            "text": "\n".join(texts),
            "structured": structured,
        }

    async def health(self) -> bool:
        try:
            if not self.session:
                return False
            await self.session.list_tools()
            return True
        except Exception:
            return False

    async def _cleanup(self):
        if self.session:
            try:
                await self.session.__aexit__(None, None, None)
            except Exception:
                pass
            self.session = None
        if self._client_ctx:
            try:
                await self._client_ctx.__aexit__(None, None, None)
            except Exception:
                pass
            self._client_ctx = None

    async def close(self):
        await self._cleanup()


# Module-level singleton for the FastAPI lifespan to own
zerodha_client = ZerodhaMCPClient()
