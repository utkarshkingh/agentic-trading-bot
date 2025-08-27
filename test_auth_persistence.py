#!/usr/bin/env python3

import asyncio
import os
from openrouter_bridge import MCPLiteLLMBridge

async def test_auth_persistence():
    """Test authentication persistence across multiple messages"""
    print("=== Testing Authentication Persistence ===")
    
    bridge = MCPLiteLLMBridge(enable_mock=True)
    
    if not await bridge.initialize():
        print("❌ Failed to initialize bridge")
        return
    
    print("✅ Bridge initialized")
    
    # Simulate multiple messages to test persistence
    test_messages = [
        "Hello, what trading tools do you have available?",
        "Can you get my current portfolio?",
        "What are my current positions?", 
        "Get a quote for RELIANCE",
        "Place a buy order for 10 shares of TCS",
        "Check my portfolio again"
    ]
    
    print(f"\n🧪 Simulating {len(test_messages)} consecutive messages...")
    
    for i, message in enumerate(test_messages, 1):
        print(f"\n--- Message {i}/{len(test_messages)} ---")
        print(f"User: {message}")
        
        # Check connection before each message
        connection_status = await bridge.ensure_mcp_connection()
        print(f"Connection status: {'✅ Connected' if connection_status else '❌ Disconnected'}")
        
        # For testing, we'll simulate tool calls for certain messages
        if any(keyword in message.lower() for keyword in ['portfolio', 'positions', 'quote', 'order']):
            print("🔧 This message would trigger tool calls")
            
            # Test calling tools directly to simulate the chat flow
            if 'portfolio' in message.lower():
                result = await bridge.mcp_client.call_tool('get_portfolio', {})
                print(f"Tool result: {result['text'] if result['success'] else f'Error: {result['error']}'}")
            elif 'positions' in message.lower():
                result = await bridge.mcp_client.call_tool('get_positions', {})
                print(f"Tool result: {result['text'] if result['success'] else f'Error: {result['error']}'}")
            elif 'quote' in message.lower():
                result = await bridge.mcp_client.call_tool('get_quote', {'symbol': 'RELIANCE'})
                print(f"Tool result: {result['text'] if result['success'] else f'Error: {result['error']}'}")
            elif 'order' in message.lower():
                result = await bridge.mcp_client.call_tool('place_order', {
                    'symbol': 'TCS',
                    'quantity': 10,
                    'transaction_type': 'BUY',
                    'order_type': 'MARKET'
                })
                print(f"Tool result: {result['text'] if result['success'] else f'Error: {result['error']}'}")
        else:
            print("💬 Regular chat message (no tools needed)")
        
        # Check if connection is still valid after each operation
        if not bridge.mcp_client.is_connected():
            print("⚠️  Connection lost after operation")
        else:
            print("✅ Connection maintained")
    
    print("\n=== Final Test Results ===")
    final_connection = await bridge.ensure_mcp_connection()
    print(f"Final connection status: {'✅ Connected' if final_connection else '❌ Disconnected'}")
    
    # Test one more tool call to ensure everything still works
    print("\n🔧 Final tool test...")
    result = await bridge.mcp_client.call_tool('get_portfolio', {})
    if result['success']:
        print("✅ Final tool call successful - authentication persisted!")
        print(f"Result: {result['text']}")
    else:
        print(f"❌ Final tool call failed: {result['error']}")
    
    await bridge.cleanup()
    print("\n✅ Test completed")

if __name__ == "__main__":
    asyncio.run(test_auth_persistence())