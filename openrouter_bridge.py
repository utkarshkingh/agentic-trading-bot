import asyncio
import json
import os
from dotenv import load_dotenv
import litellm
from zerodha_mcp_client import ZerodhaMCPClient

load_dotenv()

# Set OpenRouter API key globally for LiteLLM
os.environ["OPENROUTER_API_KEY"] = os.getenv("OPENROUTER_API_KEY")

class MCPLiteLLMBridge:
    def __init__(self):
        self.mcp_client = ZerodhaMCPClient()
        self.tools = []

    async def initialize(self):
        if not await self.mcp_client.connect():
            return False
        
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
        
        print(f" Loaded {len(self.tools)} trading tools")
        return True

    async def chat(self, user_message, model="openrouter/google/gemini-2.5-pro"):
        """Chat using OpenRouter models via LiteLLM"""
        messages = [
            {
                "role": "system",
                "content": "You are a professional trading assistant with access to Zerodha trading tools. Help the user with their trading requests."
            },
            {"role": "user", "content": user_message}
        ]
        
        try:
            # First API call - all models use OpenRouter API key
            response = litellm.completion(
                model=model,  # Use openrouter/ prefix
                messages=messages,
                tools=self.tools,
                timeout=600000
            )
            
            assistant_message = response.choices[0].message
            
            # Check for tool calls
            tool_calls = getattr(assistant_message, 'tool_calls', None)
            if tool_calls:
                print("🔧 Executing trading tools...")
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
                
                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    arguments = json.loads(tool_call.function.arguments)
                    
                    print(f"Calling: {function_name}")
                    
                    # Execute MCP tool
                    result = await self.mcp_client.call_tool(function_name, arguments)
                    
                    # Add tool result to messages
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result["text"] if result["success"] else f"Error: {result['error']}"
                    })
                
                # Second API call with tool results
                final_response = litellm.completion(
                    model=model,
                    messages=messages,
                    timeout=60
                )
                
                return final_response.choices[0].message.content
            
            else:
                return assistant_message.content
        
        except Exception as e:
            print(f"Full error: {e}")
            return f" Error: {e}"

    async def cleanup(self):
        await self.mcp_client.disconnect()

async def trading_chat():
    bridge = MCPLiteLLMBridge()
    
    if not await bridge.initialize():
        print("Failed to initialize")
        return
    
    print(" Trading Assistant Ready! (type 'quit' to exit)")
    print("\n Available OpenRouter Models:")
    print("1. openrouter/openai/gpt-4o")
    print("2. openrouter/openai/gpt-3.5-turbo")  
    print("3. openrouter/anthropic/claude-3-sonnet")
    print("4. openrouter/anthropic/claude-3-haiku")
    print("5. openrouter/meta-llama/llama-3.1-8b-instruct")
    print("6. openrouter/meta-llama/llama-3.1-70b-instruct")
    print("7. openrouter/google/gemini-pro")
    print("8. openrouter/mistralai/mistral-7b-instruct")
    
    current_model = "openrouter/google/gemini-2.5-pro"
    print(f"\n Current model: {current_model}")
    print("\n Commands:")
    print("  /model <model_name> - Switch model")
    print("  /models - Show available models")
    print("  quit - Exit")
    
    while True:
        user_input = input("\nYou: ")
        
        if user_input.lower() in ['quit', 'exit']:
            break
        elif user_input.startswith("/model "):
            # Switch model
            new_model = user_input[7:].strip()
            if not new_model.startswith("openrouter/"):
                new_model = f"openrouter/{new_model}"
            current_model = new_model
            print(f" Switched to model: {current_model}")
            continue
        elif user_input == "/models":
            # Show available models
            print("\n Popular OpenRouter Models:")
            print("• openrouter/openai/gpt-4o (Best for complex tasks)")
            print("• openrouter/openai/gpt-3.5-turbo (Fast and reliable)")
            print("• openrouter/anthropic/claude-3-sonnet (Great reasoning)")
            print("• openrouter/anthropic/claude-3-haiku (Fast Claude)")
            print("• openrouter/meta-llama/llama-3.1-8b-instruct (Open source)")
            print("• openrouter/meta-llama/llama-3.1-70b-instruct (Large Llama)")
            print("• openrouter/google/gemini-pro (Google's model)")
            print("• openrouter/mistralai/mistral-7b-instruct (European model)")
            print("\nUse: /model <model_name> to switch")
            continue
        
        response = await bridge.chat(user_input, model=current_model)
        print(" Assistant:", response)
    
    await bridge.cleanup()

if __name__ == "__main__":
    asyncio.run(trading_chat())
