#!/usr/bin/env python3
"""
Demo script showing the agentic trading bot functionality.
This script demonstrates the MCP client and OpenRouter integration
without requiring external connections.
"""

import asyncio
import logging
import os
from typing import Dict, Any
from unittest.mock import AsyncMock, MagicMock

# Mock the external dependencies for demo purposes
class MockZerodhaMCPClient:
    """Mock MCP client for demonstration purposes"""
    
    def __init__(self, server_url: str = "https://mcp.kite.trade/mcp"):
        self.server_url = server_url
        self.logger = logging.getLogger(__name__)
        self._connected = False
        
    async def connect(self, timeout_seconds: float = 30.0) -> bool:
        """Mock connection that simulates successful connection"""
        self.logger.info(f"🔌 Connecting to {self.server_url}...")
        await asyncio.sleep(0.5)  # Simulate connection time
        self._connected = True
        self.logger.info("✅ Connected to Zerodha MCP Server (Mock)")
        return True
    
    async def disconnect(self):
        """Mock disconnection"""
        self._connected = False
        self.logger.info("🔌 Disconnected from Zerodha MCP Server (Mock)")
    
    async def get_available_tools(self):
        """Return mock trading tools"""
        return [
            {
                "name": "login",
                "description": "Authenticate with Zerodha using OAuth",
                "schema": {"type": "object", "properties": {}}
            },
            {
                "name": "get_profile", 
                "description": "Get user profile information",
                "schema": {"type": "object", "properties": {}}
            },
            {
                "name": "get_holdings",
                "description": "Get portfolio holdings",
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
                        "tradingsymbol": {"type": "string"},
                        "exchange": {"type": "string"}, 
                        "transaction_type": {"type": "string"},
                        "quantity": {"type": "integer"},
                        "order_type": {"type": "string"}
                    }
                }
            },
            {
                "name": "get_quotes",
                "description": "Get real-time market quotes",
                "schema": {
                    "type": "object",
                    "properties": {
                        "instruments": {"type": "array", "items": {"type": "string"}}
                    }
                }
            }
        ]
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Mock tool execution with realistic responses"""
        await asyncio.sleep(0.3)  # Simulate API call time
        
        if tool_name == "login":
            return {
                "success": True,
                "text": "Please visit the following URL to authenticate with Zerodha:\n\nhttps://kite.zerodha.com/connect/login?api_key=kitemcp&v=3&redirect_params=session_id%3Ddemo-session-123\n\nAfter authentication, you'll be redirected back and can use other trading tools.",
                "structured": {
                    "oauth_url": "https://kite.zerodha.com/connect/login?api_key=kitemcp&v=3&redirect_params=session_id%3Ddemo-session-123",
                    "session_id": "demo-session-123"
                },
                "error": None
            }
        
        elif tool_name == "get_profile":
            return {
                "success": True,
                "text": "User Profile:\nUser ID: DEMO123\nUser Name: Demo User\nEmail: demo@example.com\nBroker: ZERODHA\nExchanges: ['NSE', 'BSE', 'MCX']\nSegments: ['equity', 'commodity']",
                "structured": {
                    "user_id": "DEMO123",
                    "user_name": "Demo User", 
                    "email": "demo@example.com",
                    "broker": "ZERODHA",
                    "exchanges": ["NSE", "BSE", "MCX"],
                    "segments": ["equity", "commodity"]
                },
                "error": None
            }
            
        elif tool_name == "get_holdings":
            return {
                "success": True,
                "text": "Portfolio Holdings:\n1. RELIANCE (NSE) - Qty: 10, Avg Price: ₹2,450, Current: ₹2,520, P&L: +₹700\n2. TCS (NSE) - Qty: 5, Avg Price: ₹3,200, Current: ₹3,180, P&L: -₹100\n3. INFY (NSE) - Qty: 8, Avg Price: ₹1,450, Current: ₹1,520, P&L: +₹560\n\nTotal Portfolio Value: ₹22,140\nTotal P&L: +₹1,160",
                "structured": {
                    "holdings": [
                        {"symbol": "RELIANCE", "exchange": "NSE", "quantity": 10, "avg_price": 2450, "ltp": 2520, "pnl": 700},
                        {"symbol": "TCS", "exchange": "NSE", "quantity": 5, "avg_price": 3200, "ltp": 3180, "pnl": -100},
                        {"symbol": "INFY", "exchange": "NSE", "quantity": 8, "avg_price": 1450, "ltp": 1520, "pnl": 560}
                    ],
                    "total_value": 22140,
                    "total_pnl": 1160
                },
                "error": None
            }
            
        elif tool_name == "get_quotes":
            instruments = arguments.get("instruments", ["NSE:RELIANCE"])
            quotes_data = []
            for instrument in instruments:
                quotes_data.append({
                    "instrument": instrument,
                    "last_price": 2520.50,
                    "change": 15.30,
                    "change_percent": 0.61,
                    "volume": 1250000
                })
            
            return {
                "success": True,
                "text": f"Market Quotes for {', '.join(instruments)}:\nLast Price: ₹2,520.50 (+15.30, +0.61%)\nVolume: 12,50,000",
                "structured": {"quotes": quotes_data},
                "error": None
            }
            
        else:
            return {
                "success": True,
                "text": f"Mock execution of {tool_name} with arguments: {arguments}",
                "structured": {"tool": tool_name, "args": arguments, "status": "executed"},
                "error": None
            }
    
    async def health_check(self) -> bool:
        """Mock health check"""
        return self._connected

# Mock OpenRouter response
def mock_litellm_completion(*args, **kwargs):
    """Mock LiteLLM completion for demo"""
    messages = kwargs.get('messages', [])
    tools = kwargs.get('tools', [])
    
    # Simulate AI response based on last user message
    last_message = messages[-1]['content'] if messages else ""
    
    if "authenticate" in last_message.lower() or "login" in last_message.lower():
        # Mock tool call for authentication
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message = MagicMock()
        mock_response.choices[0].message.content = "I'll help you authenticate with Zerodha. Let me generate a login URL for you."
        
        # Mock tool call
        mock_tool_call = MagicMock()
        mock_tool_call.id = "call_123"
        mock_tool_call.function.name = "login"
        mock_tool_call.function.arguments = "{}"
        mock_response.choices[0].message.tool_calls = [mock_tool_call]
        
        return mock_response
    
    elif "portfolio" in last_message.lower() or "holdings" in last_message.lower():
        # Mock response for portfolio inquiry
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message = MagicMock()
        mock_response.choices[0].message.content = "Let me fetch your current portfolio holdings."
        
        mock_tool_call = MagicMock()
        mock_tool_call.id = "call_456"
        mock_tool_call.function.name = "get_holdings"
        mock_tool_call.function.arguments = "{}"
        mock_response.choices[0].message.tool_calls = [mock_tool_call]
        
        return mock_response
    
    else:
        # Regular AI response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message = MagicMock()
        mock_response.choices[0].message.content = f"I understand you're asking about: {last_message}. I'm a trading assistant with access to Zerodha tools. How can I help you with your trading needs?"
        mock_response.choices[0].message.tool_calls = None
        
        return mock_response

async def demo_mcp_client():
    """Demonstrate the MCP client functionality"""
    print("🚀 Zerodha MCP Client Demo")
    print("=" * 50)
    
    # Setup logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    client = MockZerodhaMCPClient()
    
    print("🔌 Testing MCP Client Connection...")
    connected = await client.connect()
    
    if connected:
        print("✅ Connected successfully!")
        
        # Get available tools
        print("\n🛠 Available Trading Tools:")
        tools = await client.get_available_tools()
        for i, tool in enumerate(tools, 1):
            print(f"  {i}. {tool['name']}: {tool['description']}")
        
        # Demonstrate OAuth authentication
        print("\n🔐 Testing OAuth Authentication...")
        auth_result = await client.call_tool("login", {})
        print(f"OAuth URL: {auth_result['text'][:100]}...")
        
        # Demonstrate portfolio access
        print("\n📊 Testing Portfolio Access...")
        holdings_result = await client.call_tool("get_holdings", {})
        print(f"Portfolio: {holdings_result['text'][:100]}...")
        
        # Demonstrate market data
        print("\n📈 Testing Market Data...")
        quotes_result = await client.call_tool("get_quotes", {"instruments": ["NSE:RELIANCE"]})
        print(f"Market Data: {quotes_result['text']}")
        
        await client.disconnect()
    
    print("\n" + "=" * 50)

async def demo_openrouter_bridge():
    """Demonstrate the OpenRouter bridge functionality"""
    print("\n🤖 OpenRouter Bridge Demo")
    print("=" * 50)
    
    # Mock the litellm module
    import sys
    from unittest.mock import MagicMock
    
    # Create mock modules
    mock_litellm = MagicMock()
    mock_litellm.completion = mock_litellm_completion
    sys.modules['litellm'] = mock_litellm
    
    # Now we can import our bridge
    from openrouter_bridge import MCPLiteLLMBridge
    
    # Replace the real client with our mock
    bridge = MCPLiteLLMBridge()
    bridge.mcp_client = MockZerodhaMCPClient()
    
    print("🔌 Initializing Bridge...")
    if await bridge.initialize():
        print(f"✅ Bridge initialized with {len(bridge.tools)} tools")
        
        # Test authentication flow
        print("\n🔐 Testing Authentication Flow...")
        auth_response = await bridge.chat("Help me authenticate with Zerodha")
        print(f"AI Response: {auth_response}")
        
        # Test portfolio inquiry
        print("\n📊 Testing Portfolio Inquiry...")
        portfolio_response = await bridge.chat("Show me my portfolio holdings")
        print(f"AI Response: {portfolio_response}")
        
        await bridge.cleanup()
    
    print("\n" + "=" * 50)

async def main():
    """Run the complete demo"""
    print("🎯 Agentic Trading Bot - Complete Demo")
    print("🔗 GitHub: https://github.com/utkarshkingh/agentic-trading-bot")
    print("=" * 60)
    
    # Demo the MCP client
    await demo_mcp_client()
    
    # Demo the OpenRouter bridge  
    await demo_openrouter_bridge()
    
    print("\n🏁 Demo completed successfully!")
    print("\n📝 Next Steps:")
    print("  1. Set up your OpenRouter API key in .env")
    print("  2. Run: python openrouter_bridge.py")
    print("  3. Use /auth command to start Zerodha authentication")
    print("  4. Start trading with AI assistance!")

if __name__ == "__main__":
    asyncio.run(main())