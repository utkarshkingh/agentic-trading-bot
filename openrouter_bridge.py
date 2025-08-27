import asyncio
import json
import os
import logging
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
import litellm
from zerodha_mcp_client import ZerodhaMCPClient

load_dotenv()

# Set OpenRouter API key globally for LiteLLM
openrouter_key = os.getenv("OPENROUTER_API_KEY")
if openrouter_key:
    os.environ["OPENROUTER_API_KEY"] = openrouter_key

class MCPLiteLLMBridge:
    """
    Bridge between Zerodha MCP server and OpenRouter LLMs via LiteLLM.
    Provides a robust interface for AI-powered trading operations with proper
    error handling, connection management, and OAuth authentication flow.
    """
    
    def __init__(self, server_url: str = "https://mcp.kite.trade/mcp"):
        self.mcp_client = ZerodhaMCPClient(server_url)
        self.tools: List[Dict[str, Any]] = []
        self.logger = logging.getLogger(__name__)
        self._initialized = False

    async def initialize(self) -> bool:
        """Initialize the MCP client and load available tools"""
        if self._initialized:
            return True
            
        try:
            self.logger.info("Initializing MCP-LiteLLM Bridge...")
            
            # Connect to MCP server with timeout
            if not await self.mcp_client.connect(timeout_seconds=30.0):
                self.logger.error("Failed to connect to MCP server")
                return False
            
            # Load available tools
            mcp_tools = await self.mcp_client.get_available_tools()
            self.tools = []
            
            for tool in mcp_tools:
                self.tools.append({
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool["description"],
                        "parameters": tool.get("schema", {"type": "object", "properties": {}})
                    }
                })
            
            self._initialized = True
            self.logger.info(f"✅ Successfully loaded {len(self.tools)} trading tools")
            
            # Log available tools for debugging
            tool_names = [tool["function"]["name"] for tool in self.tools]
            self.logger.info(f"Available tools: {', '.join(tool_names)}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize: {e}")
            return False

    async def chat(self, user_message: str, model: str = "openrouter/google/gemini-2.0-flash-exp") -> str:
        """
        Chat using OpenRouter models via LiteLLM with MCP tool integration.
        
        Args:
            user_message: User's message/query
            model: OpenRouter model to use
            
        Returns:
            AI assistant's response
        """
        if not self._initialized:
            if not await self.initialize():
                return "❌ Failed to initialize MCP bridge. Please check connection to Zerodha MCP server."
        
        # Check MCP connection health
        if not await self.mcp_client.health_check():
            self.logger.warning("MCP connection unhealthy, attempting to reconnect...")
            if not await self.mcp_client.connect():
                return "❌ Lost connection to Zerodha MCP server. Please try again later."
        
        messages = [
            {
                "role": "system",
                "content": """You are a professional trading assistant with access to Zerodha Kite trading tools. 

IMPORTANT OAUTH AUTHENTICATION FLOW:
- When users want to access their trading data, use the 'login' tool first
- The login tool will generate a Zerodha OAuth URL
- Tell the user to visit that URL to authenticate manually
- After authentication, they can use other trading tools

Available capabilities:
- Portfolio management (view holdings, positions, margins)
- Order management (place, modify, cancel orders)
- Market data access (quotes, historical data)
- Authentication via OAuth flow

Always prioritize user security and explain the authentication process clearly."""
            },
            {"role": "user", "content": user_message}
        ]
        
        try:
            # Validate OpenRouter API key
            if not os.getenv("OPENROUTER_API_KEY"):
                return "❌ OpenRouter API key not configured. Please set OPENROUTER_API_KEY environment variable."
            
            self.logger.info(f"Sending request to {model}")
            
            # First API call with tools
            response = litellm.completion(
                model=model,
                messages=messages,
                tools=self.tools,
                timeout=120
            )
            
            assistant_message = response.choices[0].message
            
            # Check for tool calls
            tool_calls = getattr(assistant_message, 'tool_calls', None)
            if tool_calls:
                self.logger.info(f"🔧 Executing {len(tool_calls)} tool call(s)...")
                
                messages.append({
                    "role": "assistant",
                    "content": assistant_message.content,
                    "tool_calls": [
                        {
                            "id": tool_call.id,
                            "type": "function",
                            "function": {
                                "name": tool_call.function.name,
                                "arguments": tool_call.function.arguments
                            }
                        }
                        for tool_call in tool_calls
                    ]
                })
                
                # Execute each tool call
                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    try:
                        arguments = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError as e:
                        self.logger.error(f"Invalid JSON in tool arguments: {e}")
                        arguments = {}
                    
                    self.logger.info(f"Calling tool: {function_name} with args: {arguments}")
                    
                    # Execute MCP tool with error handling
                    try:
                        result = await self.mcp_client.call_tool(function_name, arguments)
                        
                        if result["success"]:
                            content = result["text"] or "Tool executed successfully"
                            if result.get("structured"):
                                content += f"\n\nStructured data: {json.dumps(result['structured'], indent=2)}"
                        else:
                            content = f"Error: {result['error']}"
                            
                    except Exception as e:
                        self.logger.error(f"Tool execution failed: {e}")
                        content = f"Tool execution failed: {str(e)}"
                    
                    # Add tool result to messages
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": content
                    })
                
                # Second API call with tool results
                self.logger.info("Generating final response with tool results...")
                final_response = litellm.completion(
                    model=model,
                    messages=messages,
                    timeout=60
                )
                
                return final_response.choices[0].message.content
            
            else:
                return assistant_message.content
        
        except Exception as e:
            self.logger.error(f"Chat error: {e}")
            return f"❌ Error: {str(e)}"

    async def cleanup(self):
        """Clean up resources"""
        self._initialized = False
        await self.mcp_client.disconnect()

async def trading_chat():
    """Interactive trading assistant using OpenRouter LLMs and Zerodha MCP"""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("🚀 Starting Trading Assistant")
    print("=" * 60)
    
    bridge = MCPLiteLLMBridge()
    
    # Initialize with connection check
    print("🔌 Initializing connection to Zerodha MCP server...")
    if not await bridge.initialize():
        print("❌ Failed to initialize MCP bridge")
        print("\n🛠 Troubleshooting:")
        print("  • Check internet connection")
        print("  • Verify Zerodha MCP server is accessible")
        print("  • Ensure no firewall blocking connections")
        return
    
    print("✅ Successfully connected to Zerodha MCP server!")
    print("🤖 Trading Assistant is ready!")
    print("=" * 60)
    
    print("\n💡 Available OpenRouter Models:")
    models = [
        "openrouter/google/gemini-2.0-flash-exp",
        "openrouter/openai/gpt-4o",
        "openrouter/openai/gpt-3.5-turbo",
        "openrouter/anthropic/claude-3-sonnet",
        "openrouter/anthropic/claude-3-haiku",
        "openrouter/meta-llama/llama-3.1-8b-instruct",
        "openrouter/meta-llama/llama-3.1-70b-instruct",
        "openrouter/google/gemini-pro",
        "openrouter/mistralai/mistral-7b-instruct"
    ]
    
    for i, model in enumerate(models, 1):
        print(f"  {i}. {model}")
    
    current_model = "openrouter/google/gemini-2.0-flash-exp"
    print(f"\n🎯 Current model: {current_model}")
    
    print("\n💬 Commands:")
    print("  /model <model_name> - Switch model")
    print("  /models - Show available models")
    print("  /auth - Start Zerodha authentication")
    print("  /status - Check connection status")
    print("  quit - Exit")
    print("=" * 60)
    
    try:
        while True:
            user_input = input("\n👤 You: ").strip()
            
            if user_input.lower() in ['quit', 'exit']:
                break
                
            elif user_input.startswith("/model "):
                # Switch model
                new_model = user_input[7:].strip()
                if not new_model.startswith("openrouter/"):
                    new_model = f"openrouter/{new_model}"
                current_model = new_model
                print(f"🎯 Switched to model: {current_model}")
                continue
                
            elif user_input == "/models":
                # Show available models
                print("\n🤖 Available OpenRouter Models:")
                for model in models:
                    indicator = "👈 Current" if model == current_model else "  "
                    print(f"{indicator} {model}")
                print("\nUse: /model <model_name> to switch")
                continue
                
            elif user_input == "/auth":
                # Start authentication
                print("🔐 Starting Zerodha OAuth authentication...")
                response = await bridge.chat("Please help me authenticate with Zerodha", current_model)
                print(f"🤖 Assistant: {response}")
                continue
                
            elif user_input == "/status":
                # Check status
                health = await bridge.mcp_client.health_check()
                print(f"🏥 MCP Connection: {'✅ Healthy' if health else '❌ Unhealthy'}")
                print(f"🎯 Current Model: {current_model}")
                print(f"📊 Available Tools: {len(bridge.tools)}")
                continue
                
            elif not user_input:
                continue
            
            # Regular chat
            print("🤖 Assistant: ", end="", flush=True)
            response = await bridge.chat(user_input, model=current_model)
            print(response)
    
    except KeyboardInterrupt:
        print("\n\n⚡ Interrupted by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
    finally:
        print("\n🔌 Cleaning up...")
        await bridge.cleanup()
        print("✅ Goodbye!")


if __name__ == "__main__":
    asyncio.run(trading_chat())
