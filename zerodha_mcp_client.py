import asyncio
import logging
from typing import Optional
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import PromptReference, ResourceTemplateReference, AnyUrl
import httpx


import asyncio
import logging
from typing import Optional, Dict, Any, List
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import PromptReference, ResourceTemplateReference, AnyUrl
import httpx
import time

class ZerodhaMCPClient:
    """
    A robust MCP client for connecting to the Zerodha Kite MCP server.
    Handles OAuth authentication flow, connection management, and provides
    comprehensive error handling with networking best practices.
    """
    
    def __init__(self, server_url="https://mcp.kite.trade/mcp"):
        self.server_url = server_url
        self.session: Optional[ClientSession] = None
        self.client_context = None
        self.logger = logging.getLogger(__name__)
        self._connected = False
        self._connection_attempts = 0
        self._max_retries = 3
        self._retry_delay = 2.0
        
    async def connect(self, timeout_seconds: float = 30.0) -> bool:
        """
        Connect to Zerodha MCP server using streamable HTTP with retry logic.
        
        Args:
            timeout_seconds: Total timeout for connection attempt
            
        Returns:
            bool: True if connection successful, False otherwise
        """
        if self._connected:
            self.logger.info("Already connected to MCP server")
            return True
            
        start_time = time.time()
        
        for attempt in range(self._max_retries):
            if time.time() - start_time > timeout_seconds:
                self.logger.error(f"Connection timeout after {timeout_seconds}s")
                break
                
            try:
                self.logger.info(f"Connection attempt {attempt + 1}/{self._max_retries} to {self.server_url}")
                
                # Use streamable HTTP transport with reasonable timeout
                self.client_context = streamablehttp_client(self.server_url)
                
                read_stream, write_stream, _ = await asyncio.wait_for(
                    self.client_context.__aenter__(), 
                    timeout=timeout_seconds
                )
                
                self.session = ClientSession(read_stream, write_stream)
                await self.session.__aenter__()
                
                # Initialize the connection with proper error handling
                init_result = await asyncio.wait_for(
                    self.session.initialize(),
                    timeout=timeout_seconds / 2
                )
                
                self._connected = True
                self.logger.info(f"✅ Connected to Zerodha MCP Server - Protocol: {init_result.protocolVersion}")
                self.logger.info(f"🔌 Server capabilities: {init_result.capabilities}")
                return True
                
            except asyncio.TimeoutError:
                self.logger.warning(f"Connection attempt {attempt + 1} timed out")
                await self._cleanup_on_error()
                
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                self.logger.warning(f"Network error on attempt {attempt + 1}: {e}")
                await self._cleanup_on_error()
                
            except Exception as e:
                self.logger.error(f"Connection attempt {attempt + 1} failed: {e}")
                await self._cleanup_on_error()
            
            if attempt < self._max_retries - 1:
                await asyncio.sleep(self._retry_delay * (attempt + 1))
        
        self.logger.error("All connection attempts failed")
        return False
    
    async def _cleanup_on_error(self):
        """Cleanup resources on connection error"""
        self._connected = False
        try:
            if self.session:
                await self.session.__aexit__(None, None, None)
                self.session = None
        except:
            pass
        try:
            if self.client_context:
                await self.client_context.__aexit__(None, None, None)
                self.client_context = None
        except:
            pass
    
    async def disconnect(self):
        """Disconnect from server"""
        try:
            self._connected = False
            if self.session:
                await self.session.__aexit__(None, None, None)
                self.session = None
            if self.client_context:
                await self.client_context.__aexit__(None, None, None)
                self.client_context = None
            self.logger.info("🔌 Disconnected from Zerodha MCP Server")
        except Exception as e:
            self.logger.error(f"Error during disconnect: {e}")
    
    async def ensure_connected(self) -> bool:
        """Ensure we have an active connection, reconnect if needed"""
        if not self._connected or not self.session:
            return await self.connect()
        return True
    
    async def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get list of available tools"""
        if not await self.ensure_connected():
            raise RuntimeError("Cannot connect to MCP server")
        
        try:
            tools = await self.session.list_tools()
            return [{"name": t.name, "description": t.description, "schema": t.inputSchema} 
                    for t in tools.tools]
        except Exception as e:
            self.logger.error(f"Error getting tools: {e}")
            raise
    
    async def get_available_resources(self) -> List[Dict[str, Any]]:
        """Get list of available resources"""
        if not await self.ensure_connected():
            raise RuntimeError("Cannot connect to MCP server")
            
        try:
            resources = await self.session.list_resources()
            return [{"uri": r.uri, "name": r.name, "description": r.description}
                    for r in resources.resources]
        except Exception as e:
            self.logger.warning(f"Error getting resources: {e}")
            return []
    
    async def get_resource_templates(self) -> List[Dict[str, Any]]:
        """Get list of available resource templates"""
        if not await self.ensure_connected():
            raise RuntimeError("Cannot connect to MCP server")
            
        try:
            templates = await self.session.list_resource_templates()
            return [{"uri_template": t.uriTemplate, "name": t.name, "description": t.description}
                    for t in templates.resourceTemplates]
        except Exception as e:
            self.logger.warning(f"Error getting resource templates: {e}")
            return []

    async def get_available_prompts(self) -> List[Dict[str, Any]]:
        """Get list of available prompts"""
        if not await self.ensure_connected():
            raise RuntimeError("Cannot connect to MCP server")
            
        try:
            prompts = await self.session.list_prompts()
            return [{"name": p.name, "description": p.description, "arguments": p.arguments}
                    for p in prompts.prompts]
        except Exception as e:
            self.logger.warning(f"Error getting prompts: {e}")
            return []

    async def complete_resource_template(self, uri_template: str, argument_name: str, 
                                       partial_value: str = "", context_arguments: Optional[Dict] = None) -> Dict[str, Any]:
        """Complete arguments for a resource template"""
        if not await self.ensure_connected():
            raise RuntimeError("Cannot connect to MCP server")
            
        try:
            result = await self.session.complete(
                ref=ResourceTemplateReference(type="ref/resource", uri=uri_template),
                argument={"name": argument_name, "value": partial_value},
                context_arguments=context_arguments or {}
            )
            return {
                "success": True,
                "completions": result.completion.values,
                "error": None
            }
        except Exception as e:
            self.logger.error(f"Error completing resource template: {e}")
            return {
                "success": False,
                "completions": [],
                "error": str(e)
            }

    async def complete_prompt_argument(self, prompt_name: str, argument_name: str, 
                                     partial_value: str = "", context_arguments: Optional[Dict] = None) -> Dict[str, Any]:
        """Complete arguments for a prompt"""
        if not await self.ensure_connected():
            raise RuntimeError("Cannot connect to MCP server")
            
        try:
            result = await self.session.complete(
                ref=PromptReference(type="ref/prompt", name=prompt_name),
                argument={"name": argument_name, "value": partial_value},
                context_arguments=context_arguments or {}
            )
            return {
                "success": True,
                "completions": result.completion.values,
                "error": None
            }
        except Exception as e:
            self.logger.error(f"Error completing prompt argument: {e}")
            return {
                "success": False,
                "completions": [],
                "error": str(e)
            }
    
    async def get_resource(self, uri: str) -> Dict[str, Any]:
        """Get a specific resource"""
        if not await self.ensure_connected():
            raise RuntimeError("Cannot connect to MCP server")
            
        try:
            result = await self.session.read_resource(AnyUrl(uri))
            
            # Extract text content
            text_results = []
            for content in result.contents:
                if hasattr(content, 'text'):
                    text_results.append(content.text)
            
            return {
                "success": True,
                "text": "\n".join(text_results),
                "contents": result.contents,
                "error": None
            }
        except Exception as e:
            self.logger.error(f"Error reading resource {uri}: {e}")
            return {
                "success": False,
                "text": None,
                "contents": None,
                "error": str(e)
            }
    
    async def get_prompt(self, name: str, arguments: Optional[Dict] = None) -> Dict[str, Any]:
        """Get a prompt with arguments"""
        if not await self.ensure_connected():
            raise RuntimeError("Cannot connect to MCP server")
            
        try:
            result = await self.session.get_prompt(name, arguments or {})
            
            # Extract messages
            messages = []
            for message in result.messages:
                content_text = []
                for content in message.content:
                    if hasattr(content, 'text'):
                        content_text.append(content.text)
                
                messages.append({
                    "role": message.role,
                    "content": "\n".join(content_text)
                })
            
            return {
                "success": True,
                "messages": messages,
                "error": None
            }
        except Exception as e:
            self.logger.error(f"Error getting prompt {name}: {e}")
            return {
                "success": False,
                "messages": [],
                "error": str(e)
            }
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call a specific tool. This is the main method for OAuth authentication and trading operations.
        
        Args:
            tool_name: Name of the tool to call (e.g., 'login', 'get_profile', 'place_order')
            arguments: Tool-specific arguments
            
        Returns:
            Dict with success status, response text, structured data, and error information
        """
        if not await self.ensure_connected():
            raise RuntimeError("Cannot connect to MCP server")
            
        try:
            self.logger.info(f"Calling tool: {tool_name} with args: {arguments}")
            result = await self.session.call_tool(tool_name, arguments)
            
            # Extract text content
            text_results = []
            for content in result.content:
                if hasattr(content, 'text'):
                    text_results.append(content.text)
            
            # Get structured content if available
            structured = None
            if hasattr(result, 'structuredContent') and result.structuredContent:
                structured = result.structuredContent
            
            response = {
                "success": True,
                "text": "\n".join(text_results),
                "structured": structured,
                "error": None
            }
            
            self.logger.info(f"Tool {tool_name} completed successfully")
            return response
            
        except Exception as e:
            self.logger.error(f"Error calling tool {tool_name}: {e}")
            return {
                "success": False,
                "text": None,
                "structured": None,
                "error": str(e)
            }
            
    async def authenticate_with_zerodha(self) -> Dict[str, Any]:
        """
        Start the OAuth authentication flow with Zerodha.
        This will generate a login URL that needs to be visited manually.
        
        Returns:
            Dict containing the login URL and session information
        """
        return await self.call_tool("login", {})
    
    async def health_check(self) -> bool:
        """Check if the connection is healthy"""
        try:
            if not self._connected or not self.session:
                return False
            # Try to list tools as a health check
            await self.session.list_tools()
            return True
        except:
            self._connected = False
            return False


# Enhanced test function
async def test_enhanced_client():
    """Test the MCP client with comprehensive error handling"""
    # Setup logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    print(" Starting Zerodha MCP Client Test")
    print("=" * 50)
    
    client = ZerodhaMCPClient()
    
    # Test connection with timeout
    print(" Attempting to connect to Zerodha MCP server...")
    print(f" Server URL: {client.server_url}")
    
    connected = await client.connect(timeout_seconds=20.0)
    
    if connected:
        print(" Successfully connected to Zerodha MCP Server!")
        print("=" * 50)
        
        try:
            # Get available tools
            print("🛠 Fetching available tools...")
            tools = await client.get_available_tools()
            print(f" Found {len(tools)} tools:")
            for i, tool in enumerate(tools, 1):
                print(f"  {i}. {tool['name']}: {tool['description']}")
            print()
            
            # Get available resources
            print(" Fetching available resources...")
            resources = await client.get_available_resources()
            print(f" Found {len(resources)} resources:")
            for i, resource in enumerate(resources, 1):
                print(f"  {i}. {resource['uri']}: {resource['name']}")
            print()
            
            # Get resource templates
            print(" Fetching resource templates...")
            templates = await client.get_resource_templates()
            print(f" Found {len(templates)} templates:")
            for i, template in enumerate(templates, 1):
                print(f"  {i}. {template['uri_template']}: {template['name']}")
            print()
            
            # Get available prompts
            print(" Fetching available prompts...")
            prompts = await client.get_available_prompts()
            print(f" Found {len(prompts)} prompts:")
            for i, prompt in enumerate(prompts, 1):
                print(f"  {i}. {prompt['name']}: {prompt['description']}")
            print()
            
            # Test the most important functionality: OAuth authentication
            print(" Testing OAuth authentication flow...")
            if any(tool['name'] == 'login' for tool in tools):
                try:
                    login_result = await client.authenticate_with_zerodha()
                    if login_result['success']:
                        print(" OAuth URL generation successful!")
                        print(" Generated login URL - visit this to authenticate:")
                        print(f"   {login_result['text'][:200]}...")
                        print("\n Full OAuth Response:")
                        print(f"   Text: {login_result['text']}")
                        if login_result['structured']:
                            print(f"   Structured: {login_result['structured']}")
                    else:
                        print(f" OAuth authentication failed: {login_result['error']}")
                except Exception as e:
                    print(f" Error testing OAuth: {e}")
            else:
                print(" Login tool not available")
            print()
            
            # Test health check
            print(" Testing connection health...")
            healthy = await client.health_check()
            print(f" Connection health: {' Healthy' if healthy else '❌ Unhealthy'}")
            print()

        except Exception as e:
            print(f" Error during testing: {e}")
            
        finally:
            print("🔌 Disconnecting from server...")
            await client.disconnect()
            print(" Disconnected successfully")
            
    else:
        print(" Failed to connect to Zerodha MCP server")
        print("\n Troubleshooting tips:")
        print("  1. Check internet connectivity")
        print("  2. Verify the server URL is correct")
        print("  3. Ensure no firewall is blocking the connection")
        print("  4. Try connecting from a different network")
        print(f"  5. Test manual connection: curl -I {client.server_url}")
        
    print("\n" + "=" * 50)
    print("🏁 Test completed")


if __name__ == "__main__":
    asyncio.run(test_enhanced_client())