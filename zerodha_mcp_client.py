import asyncio
from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.types import PromptReference, ResourceTemplateReference


class ZerodhaMCPClient:
    def __init__(self, server_url="https://mcp.kite.trade/sse"):
        self.server_url = server_url
        self.session = None
        
    async def connect(self):
        """Connect to Zerodha MCP server"""
        try:
            self.client_context = sse_client(self.server_url)
            self.read, self.write = await self.client_context.__aenter__()
            self.session = ClientSession(self.read, self.write)
            await self.session.__aenter__()
            await self.session.initialize()
            print(" Connected to Zerodha MCP Server")
            return True
        except Exception as e:
            print(f" Connection failed: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from server"""
        if self.session:
            await self.session.__aexit__(None, None, None)
        if hasattr(self, 'client_context'):
            await self.client_context.__aexit__(None, None, None)
    
    async def get_available_tools(self):
        """Get list of available tools"""
        tools = await self.session.list_tools()
        return [{"name": t.name, "description": t.description, "schema": t.inputSchema} 
                for t in tools.tools]
    
    async def get_available_resources(self):
        """Get list of available resources"""
        try:
            resources = await self.session.list_resources()
            return [{"uri": r.uri, "name": r.name, "description": r.description}
                    for r in resources.resources]
        except Exception as e:
            print(f"Error getting resources: {e}")
            return []
    
    async def get_resource_templates(self):
        """Get list of available resource templates"""
        try:
            templates = await self.session.list_resource_templates()
            return [{"uri_template": t.uriTemplate, "name": t.name, "description": t.description}
                    for t in templates.resourceTemplates]
        except Exception as e:
            print(f"Error getting resource templates: {e}")
            return []
    
    async def get_available_prompts(self):
        """Get list of available prompts"""
        try:
            prompts = await self.session.list_prompts()
            return [{"name": p.name, "description": p.description, "arguments": p.arguments}
                    for p in prompts.prompts]
        except Exception as e:
            print(f"Error getting prompts: {e}")
            return []
    
    async def complete_resource_template(self, uri_template, argument_name, partial_value="", context_arguments=None):
        """Complete arguments for a resource template"""
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
            return {
                "success": False,
                "completions": [],
                "error": str(e)
            }
    
    async def complete_prompt_argument(self, prompt_name, argument_name, partial_value="", context_arguments=None):
        """Complete arguments for a prompt"""
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
            return {
                "success": False,
                "completions": [],
                "error": str(e)
            }
    
    async def get_resource(self, uri):
        """Get a specific resource"""
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
            return {
                "success": False,
                "text": None,
                "contents": None,
                "error": str(e)
            }
    
    async def get_prompt(self, name, arguments=None):
        """Get a prompt with arguments"""
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
            return {
                "success": False,
                "messages": [],
                "error": str(e)
            }
    
    async def call_tool(self, tool_name, arguments):
        """Call a specific tool"""
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
            return {
                "success": False,
                "text": None,
                "structured": None,
                "error": str(e)
            }


# Enhanced test function
async def test_enhanced_client():
    client = ZerodhaMCPClient()
    
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
