import asyncio
import logging
from typing import Optional, Dict, Any, List
from langchain_mcp_adapters.tools import load_mcp_tools

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from dotenv import load_dotenv

load_dotenv()

class ZerodhaMCPClient:
    """
    Simple Zerodha MCP client using official MCP Python SDK.
    Maintains single persistent session for OAuth flow.
    """
    
    def __init__(self, server_url: str = "https://mcp.kite.trade/mcp"):
        self.server_url = server_url
        self.session: Optional[ClientSession] = None
        self.client_context = None
        self.logger = logging.getLogger(__name__)

    async def connect_to_server(self) -> bool:
        """Connect and maintain single session for OAuth"""
        if self.session:  #  if already connected
            return True
            
        try:
            # Create streamable HTTP transport
            self.client_context = streamablehttp_client(self.server_url)
            read_stream, write_stream, get_session_id = await self.client_context.__aenter__()
            
            # Create and enter ClientSession
            self.session = ClientSession(read_stream, write_stream)
            await self.session.__aenter__()
            
            # Initialize session
            await self.session.initialize()
            
            print("Connected to Zerodha MCP Server")
            return True
            
        except Exception as e:
            self.logger.error(f"Connection failed: {e}")
            if self.client_context:
                try:
                    await self.client_context.__aexit__(None, None, None)
                except:
                    pass
                self.client_context = None
            return False

    async def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get tools using persistent session"""
        if not self.session:
            raise RuntimeError("Not connected to MCP server")
        
        tools = await self.session.list_tools()
        return [{"name": t.name, "description": t.description, "schema": t.inputSchema} 
                for t in tools.tools]

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call tool using SAME persistent session for OAuth continuity"""
        if not self.session:
            raise RuntimeError("Not connected to MCP server")
            
        try:
            result = await self.session.call_tool(tool_name, arguments)
            
            # Extract text content
            text_results = []
            for content in result.content:
                if hasattr(content, 'text'):
                    text_results.append(content.text)
            
            structured = getattr(result, 'structuredContent', None)
            
            return {
                "success": True,
                "text": "\n".join(text_results),
                "structured": structured,
                "error": None
            }
            
        except Exception as e:
            return {
                "success": False,
                "text": None,
                "structured": None,
                "error": str(e)
            }
        

    async def authenticate_with_zerodha(self) -> Dict[str, Any]:
        """OAuth flow - uses persistent session"""
        return await self.call_tool("login", {})
    
    async def health_check(self) -> bool:
        """Check session health"""
        try:
            if not self.session:
                return False
            await self.session.list_tools()
            return True
        except Exception:
            return False
    
    async def cleanup(self):
        """Clean up session and context"""
        if self.session:
            try:
                await self.session.__aexit__(None, None, None)
            except Exception as e:
                self.logger.error(f"Session cleanup error: {e}")
            self.session = None
        
        if self.client_context:
            try:
                await self.client_context.__aexit__(None, None, None)
            except Exception as e:
                self.logger.error(f"Client context cleanup error: {e}")
            self.client_context = None

