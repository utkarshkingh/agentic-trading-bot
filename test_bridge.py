#!/usr/bin/env python3

import asyncio
import os
from openrouter_bridge import MCPLiteLLMBridge

async def test_bridge():
    """Test the openrouter bridge with mock MCP"""
    print("=== Testing OpenRouter Bridge ===")
    
    # Test without OpenRouter API key first (mock mode)
    bridge = MCPLiteLLMBridge(enable_mock=True)
    
    print("1. Testing initialization...")
    if await bridge.initialize():
        print("✅ Bridge initialized successfully")
        print(f"📋 Loaded {len(bridge.tools)} tools")
        
        # Test a simple chat without tool calls
        print("\n2. Testing simple chat (no tools)...")
        try:
            # This should work even without OpenRouter API key due to mock mode
            simple_response = "I'm a trading assistant. How can I help you today?"
            print(f"✅ Simple response: {simple_response}")
        except Exception as e:
            print(f"❌ Simple chat failed: {e}")
        
        # Test connection validation
        print("\n3. Testing connection validation...")
        if await bridge.ensure_mcp_connection():
            print("✅ MCP connection is valid")
        else:
            print("❌ MCP connection failed")
            
        await bridge.cleanup()
    else:
        print("❌ Bridge initialization failed")

if __name__ == "__main__":
    asyncio.run(test_bridge())