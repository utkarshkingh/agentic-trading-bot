#!/usr/bin/env python3

import asyncio
import httpx
from zerodha_mcp_client import ZerodhaMCPClient

async def test_basic_connection():
    """Test basic HTTP connection to the MCP server"""
    server_url = "https://mcp.kite.trade/sse"
    
    print(f"Testing basic HTTP connection to {server_url}")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(server_url)
            print(f"HTTP Response status: {response.status_code}")
            print(f"Response headers: {dict(response.headers)}")
            if response.text:
                print(f"Response content preview: {response.text[:200]}...")
    except Exception as e:
        print(f"HTTP connection failed: {e}")
        print(f"Error type: {type(e).__name__}")

async def test_mcp_client():
    """Test the MCP client connection"""
    print("\nTesting MCP client connection...")
    client = ZerodhaMCPClient()
    
    success = await client.connect()
    if success:
        print("✅ MCP connection successful!")
        
        # Test basic operations
        print("Testing basic operations...")
        tools = await client.get_available_tools()
        print(f"Available tools: {len(tools)}")
        
        await client.disconnect()
    else:
        print("❌ MCP connection failed")

async def main():
    print("=== Connection Diagnostics ===")
    await test_basic_connection()
    await test_mcp_client()

if __name__ == "__main__":
    asyncio.run(main())