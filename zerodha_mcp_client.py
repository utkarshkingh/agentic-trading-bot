import asyncio
from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.types import PromptReference, ResourceTemplateReference


class ZerodhaMCPClient:
    def __init__(self, server_url="https://mcp.kite.trade/sse", enable_mock=False):
        self.server_url = server_url
        self.session = None
        self.client_context = None
        self.read = None
        self.write = None
        self._connected = False
        self.max_retries = 3
        self.retry_delay = 2.0
        self.enable_mock = enable_mock
        self._mock_mode = False
        
    async def connect(self):
        """Connect to Zerodha MCP server with retry logic"""
        for attempt in range(self.max_retries):
            try:
                print(f"🔌 Attempting to connect to {self.server_url} (attempt {attempt + 1}/{self.max_retries})")
                self.client_context = sse_client(self.server_url)
                self.read, self.write = await self.client_context.__aenter__()
                self.session = ClientSession(self.read, self.write)
                await self.session.__aenter__()
                await self.session.initialize()
                self._connected = True
                self._mock_mode = False
                print("✅ Connected to Zerodha MCP Server")
                return True
            except Exception as e:
                print(f"❌ Connection attempt {attempt + 1} failed: {e}")
                if "No address associated with hostname" in str(e) or "ConnectError" in str(e):
                    print("🔍 Server appears to be unreachable.")
                    break  # Don't retry for DNS/connection errors
                
                if attempt < self.max_retries - 1:
                    print(f"⏳ Retrying in {self.retry_delay} seconds...")
                    await asyncio.sleep(self.retry_delay)
                
                # Clean up on failed attempt
                await self._cleanup_failed_connection()
        
        # If connection failed and mock mode is enabled, use mock mode
        if self.enable_mock:
            print("🧪 Enabling mock mode for development")
            self._connected = True
            self._mock_mode = True
            return True
        
        self._connected = False
        print("❌ All connection attempts failed")
        return False
    
    async def _cleanup_failed_connection(self):
        """Clean up partial connection state"""
        try:
            if hasattr(self, 'session') and self.session:
                await self.session.__aexit__(None, None, None)
        except:
            pass
        try:
            if hasattr(self, 'client_context') and self.client_context:
                await self.client_context.__aexit__(None, None, None)
        except:
            pass
        self.session = None
        self.client_context = None
        self.read = None
        self.write = None
    
    async def disconnect(self):
        """Disconnect from server"""
        try:
            if self.session:
                await self.session.__aexit__(None, None, None)
            if hasattr(self, 'client_context') and self.client_context:
                await self.client_context.__aexit__(None, None, None)
        except Exception as e:
            print(f"Error during disconnect: {e}")
        finally:
            self._connected = False
            self.session = None
            self.client_context = None
            self.read = None
            self.write = None
    
    def is_connected(self):
        """Check if connection is active"""
        return self._connected and (self._mock_mode or self.session is not None)
    
    async def ensure_connected(self):
        """Ensure connection is active, reconnect if needed"""
        if not self.is_connected():
            print("🔄 Reconnecting to Zerodha MCP Server...")
            return await self.connect()
        return True
    
    def _get_mock_tools(self):
        """Mock tools for development"""
        return [
            {
                "name": "get_portfolio",
                "description": "Get current portfolio holdings",
                "schema": {"type": "object", "properties": {}}
            },
            {
                "name": "get_positions",
                "description": "Get current trading positions",
                "schema": {"type": "object", "properties": {}}
            },
            {
                "name": "place_order",
                "description": "Place a trading order",
                "schema": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string"},
                        "quantity": {"type": "number"},
                        "order_type": {"type": "string"},
                        "transaction_type": {"type": "string"}
                    }
                }
            },
            {
                "name": "get_quote",
                "description": "Get real-time quote for a symbol",
                "schema": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string"}
                    }
                }
            }
        ]
    
    async def get_available_tools(self):
        """Get list of available tools"""
        if not await self.ensure_connected():
            return []
        
        if self._mock_mode:
            return self._get_mock_tools()
            
        try:
            tools = await self.session.list_tools()
            return [{"name": t.name, "description": t.description, "schema": t.inputSchema} 
                    for t in tools.tools]
        except Exception as e:
            print(f"Error getting tools: {e}")
            self._connected = False
            return []
    
    async def get_available_resources(self):
        """Get list of available resources"""
        if not await self.ensure_connected():
            return []
        
        if self._mock_mode:
            return []  # No mock resources for now
            
        try:
            resources = await self.session.list_resources()
            return [{"uri": r.uri, "name": r.name, "description": r.description}
                    for r in resources.resources]
        except Exception as e:
            print(f"Error getting resources: {e}")
            self._connected = False
            return []
    
    async def get_resource_templates(self):
        """Get list of available resource templates"""
        if not await self.ensure_connected():
            return []
        
        if self._mock_mode:
            return []  # No mock resource templates for now
            
        try:
            templates = await self.session.list_resource_templates()
            return [{"uri_template": t.uriTemplate, "name": t.name, "description": t.description}
                    for t in templates.resourceTemplates]
        except Exception as e:
            print(f"Error getting resource templates: {e}")
            self._connected = False
            return []
    
    async def get_available_prompts(self):
        """Get list of available prompts"""
        if not await self.ensure_connected():
            return []
        
        if self._mock_mode:
            return []  # No mock prompts for now
            
        try:
            prompts = await self.session.list_prompts()
            return [{"name": p.name, "description": p.description, "arguments": p.arguments}
                    for p in prompts.prompts]
        except Exception as e:
            print(f"Error getting prompts: {e}")
            self._connected = False
            return []
    
    async def complete_resource_template(self, uri_template, argument_name, partial_value="", context_arguments=None):
        """Complete arguments for a resource template"""
        if not await self.ensure_connected():
            return {
                "success": False,
                "completions": [],
                "error": "Connection lost, unable to reconnect"
            }
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
            self._connected = False
            return {
                "success": False,
                "completions": [],
                "error": str(e)
            }
    
    async def complete_prompt_argument(self, prompt_name, argument_name, partial_value="", context_arguments=None):
        """Complete arguments for a prompt"""
        if not await self.ensure_connected():
            return {
                "success": False,
                "completions": [],
                "error": "Connection lost, unable to reconnect"
            }
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
            self._connected = False
            return {
                "success": False,
                "completions": [],
                "error": str(e)
            }
    
    async def get_resource(self, uri):
        """Get a specific resource"""
        if not await self.ensure_connected():
            return {
                "success": False,
                "text": None,
                "contents": None,
                "error": "Connection lost, unable to reconnect"
            }
        try:
            result = await self.session.read_resource(uri)
            
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
            self._connected = False
            return {
                "success": False,
                "text": None,
                "contents": None,
                "error": str(e)
            }
    
    async def get_prompt(self, name, arguments=None):
        """Get a prompt with arguments"""
        if not await self.ensure_connected():
            return {
                "success": False,
                "messages": [],
                "error": "Connection lost, unable to reconnect"
            }
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
            self._connected = False
            return {
                "success": False,
                "messages": [],
                "error": str(e)
            }
    
    async def call_tool(self, tool_name, arguments):
        """Call a specific tool"""
        if not await self.ensure_connected():
            return {
                "success": False,
                "text": None,
                "structured": None,
                "error": "Connection lost, unable to reconnect"
            }
        
        if self._mock_mode:
            return self._mock_call_tool(tool_name, arguments)
            
        try:
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
            
            return {
                "success": True,
                "text": "\n".join(text_results),
                "structured": structured,
                "error": None
            }
        except Exception as e:
            print(f"Error calling tool {tool_name}: {e}")
            self._connected = False
            return {
                "success": False,
                "text": None,
                "structured": None,
                "error": str(e)
            }
    
    def _mock_call_tool(self, tool_name, arguments):
        """Mock tool execution for development"""
        mock_responses = {
            "get_portfolio": {
                "success": True,
                "text": "Portfolio: RELIANCE (100 shares, ₹2,500/share), TCS (50 shares, ₹3,200/share), Total Value: ₹4,10,000",
                "structured": None,
                "error": None
            },
            "get_positions": {
                "success": True, 
                "text": "Current Positions: NIFTY 18000 CE (Long 2 lots, LTP: ₹45), BANKNIFTY 44000 PE (Short 1 lot, LTP: ₹80)",
                "structured": None,
                "error": None
            },
            "place_order": {
                "success": True,
                "text": f"Mock order placed: {arguments.get('transaction_type', 'BUY')} {arguments.get('quantity', 1)} shares of {arguments.get('symbol', 'UNKNOWN')} at {arguments.get('order_type', 'MARKET')} price. Order ID: MOCK123456",
                "structured": None,
                "error": None
            },
            "get_quote": {
                "success": True,
                "text": f"Quote for {arguments.get('symbol', 'UNKNOWN')}: LTP: ₹2,450.50, Change: +15.25 (+0.63%), Volume: 1,25,000",
                "structured": None,
                "error": None
            }
        }
        
        return mock_responses.get(tool_name, {
            "success": False,
            "text": None,
            "structured": None,
            "error": f"Unknown tool: {tool_name}"
        })


# Enhanced test function
async def test_enhanced_client():
    client = ZerodhaMCPClient(enable_mock=True)  # Enable mock mode for testing
    
    if await client.connect():
        print("=== Testing Enhanced MCP Client ===\n")
        
        # Get available tools
        tools = await client.get_available_tools()
        print(f" Available tools ({len(tools)}):")
        for tool in tools:
            print(f"  - {tool['name']}: {tool['description']}")
        print()
        
        # Get available resources
        resources = await client.get_available_resources()
        print(f"📁 Available resources ({len(resources)}):")
        for resource in resources:
            print(f"  - {resource['uri']}: {resource['name']}")
        print()
        
        # Get resource templates
        templates = await client.get_resource_templates()
        print(f" Available resource templates ({len(templates)}):")
        for template in templates:
            print(f"  - {template['uri_template']}: {template['name']}")
        print()
        
        # Get available prompts
        prompts = await client.get_available_prompts()
        print(f" Available prompts ({len(prompts)}):")
        for prompt in prompts:
            print(f"  - {prompt['name']}: {prompt['description']}")
        print()
        
        # Test completion for resource templates
        if templates:
            template = templates[0]
            print(f" Testing completion for template: {template['uri_template']}")
            
            # You can customize these based on your actual template parameters
            completion_result = await client.complete_resource_template(
                uri_template=template['uri_template'],
                argument_name="symbol",  # Adjust based on your template
                partial_value="RELIANCE"
            )
            
            if completion_result['success']:
                print(f"  Completions: {completion_result['completions']}")
            else:
                print(f"  Error: {completion_result['error']}")
            print()
        
        # Test completion for prompts
        if prompts:
            prompt = prompts[0]
            print(f" Testing completion for prompt: {prompt['name']}")
            
            # Adjust argument name based on your actual prompt arguments
            if prompt.get('arguments'):
                arg_name = list(prompt['arguments'].keys())[0] if prompt['arguments'] else "query"
                completion_result = await client.complete_prompt_argument(
                    prompt_name=prompt['name'],
                    argument_name=arg_name,
                    partial_value=""
                )
                
                if completion_result['success']:
                    print(f"  Completions: {completion_result['completions']}")
                else:
                    print(f"  Error: {completion_result['error']}")
            print()
        
        # Test reading a resource (if available)
        if resources:
            resource = resources[0]
            print(f" Testing resource read: {resource['uri']}")
            
            resource_result = await client.get_resource(resource['uri'])
            if resource_result['success']:
                print(f"  Content preview: {resource_result['text'][:200]}...")
            else:
                print(f"  Error: {resource_result['error']}")
            print()
        
        # Test getting a prompt (if available)
        if prompts:
            prompt = prompts[0]
            print(f" Testing prompt get: {prompt['name']}")
            
            prompt_result = await client.get_prompt(prompt['name'], {})
            if prompt_result['success']:
                for i, message in enumerate(prompt_result['messages']):
                    print(f"  Message {i+1} ({message['role']}): {message['content'][:100]}...")
            else:
                print(f"  Error: {prompt_result['error']}")
            print()
        
        await client.disconnect()
    else:
        print("Failed to connect to server")


if __name__ == "__main__":
    asyncio.run(test_enhanced_client())
