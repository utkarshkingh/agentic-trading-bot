# Agentic Trading Bot

LLM powered Agentic trading bot using MCP server and Zerodha Kite Connect APIs

## Overview

This project provides a robust Model Context Protocol (MCP) client for connecting to the Zerodha Kite MCP server and integrating it with OpenRouter LLMs for AI-powered trading operations. The implementation follows networking best practices and handles OAuth authentication flows properly.

## Features

### 🔐 OAuth Authentication
- Seamless integration with Zerodha's OAuth flow
- Manual authentication on the MCP server provider website
- Session management and connection persistence

### 🤖 LLM Integration
- Support for multiple OpenRouter models
- Tool calling capabilities for trading operations
- Structured responses with error handling

### 🛠 Trading Operations
- Portfolio management (holdings, positions, margins)
- Order management (place, modify, cancel orders)
- Market data access (quotes, historical data, OHLC)
- Real-time trading assistant

### 🌐 Networking Best Practices
- Connection pooling and retry logic
- Proper timeout handling
- Health checks and reconnection
- Comprehensive error handling

## Installation

### Prerequisites

- Python 3.11 or higher
- OpenRouter API key (get from [openrouter.ai](https://openrouter.ai/))
- Internet connection to access Zerodha MCP server

### Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/utkarshkingh/agentic-trading-bot.git
   cd agentic-trading-bot
   ```

2. **Install dependencies:**
   ```bash
   pip install -e .
   ```

3. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your OpenRouter API key
   ```

## Usage

### Basic Usage

#### 1. Test MCP Client Connection

```bash
python zerodha_mcp_client.py
```

This will test the connection to the Zerodha MCP server and display available tools.

#### 2. Start the Trading Assistant

```bash
python openrouter_bridge.py
```

This starts an interactive trading assistant that combines OpenRouter LLMs with Zerodha trading tools.

### OAuth Authentication Flow

1. **Start Authentication:**
   ```
   /auth
   ```
   Or ask: "Help me authenticate with Zerodha"

2. **Visit the Generated URL:**
   The assistant will provide a Zerodha OAuth URL. Visit this URL in your browser.

3. **Complete Authentication:**
   Login with your Zerodha credentials and complete the OAuth flow.

4. **Start Trading:**
   Once authenticated, you can ask for portfolio information, place orders, etc.

### Available Commands

- `/model <model_name>` - Switch between OpenRouter models
- `/models` - List available models
- `/auth` - Start Zerodha authentication
- `/status` - Check connection and system status
- `quit` - Exit the application

### Example Interactions

```
👤 You: Help me check my portfolio

🤖 Assistant: I'll help you check your portfolio. First, let me authenticate 
with Zerodha to access your account information.

[The assistant will use the login tool to generate an OAuth URL]

👤 You: Show me my current holdings

🤖 Assistant: [After authentication, displays portfolio holdings with 
current values, P&L, and other relevant information]
```

## Architecture

### Components

1. **ZerodhaMCPClient** (`zerodha_mcp_client.py`)
   - Robust MCP client with connection management
   - Streamable HTTP transport for production use
   - Comprehensive error handling and retry logic
   - Health checks and automatic reconnection

2. **MCPLiteLLMBridge** (`openrouter_bridge.py`)
   - Bridge between MCP server and OpenRouter LLMs
   - Tool calling integration
   - Session management and state handling

3. **Trading Tools Integration**
   - OAuth authentication flow
   - Portfolio and order management
   - Market data access
   - Real-time notifications

### Network Architecture

```
[OpenRouter LLMs] <--> [MCPLiteLLMBridge] <--> [ZerodhaMCPClient] <--> [Zerodha MCP Server]
                                                       |
                                               [OAuth Flow with Zerodha]
```

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `OPENROUTER_API_KEY` | OpenRouter API key for LLM access | Yes |
| `MCP_SERVER_URL` | Zerodha MCP server URL | No (defaults to hosted version) |
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | No (defaults to INFO) |

### Supported OpenRouter Models

- `openrouter/google/gemini-2.0-flash-exp` (Default)
- `openrouter/openai/gpt-4o`
- `openrouter/openai/gpt-3.5-turbo`
- `openrouter/anthropic/claude-3-sonnet`
- `openrouter/anthropic/claude-3-haiku`
- `openrouter/meta-llama/llama-3.1-8b-instruct`
- `openrouter/meta-llama/llama-3.1-70b-instruct`
- `openrouter/google/gemini-pro`
- `openrouter/mistralai/mistral-7b-instruct`

## API Reference

### ZerodhaMCPClient

```python
from zerodha_mcp_client import ZerodhaMCPClient

client = ZerodhaMCPClient("https://mcp.kite.trade/mcp")

# Connect with timeout
connected = await client.connect(timeout_seconds=30.0)

# Get available tools
tools = await client.get_available_tools()

# Call a tool (e.g., OAuth login)
result = await client.call_tool("login", {})

# Call trading tools
profile = await client.call_tool("get_profile", {})
holdings = await client.call_tool("get_holdings", {})

# Cleanup
await client.disconnect()
```

### MCPLiteLLMBridge

```python
from openrouter_bridge import MCPLiteLLMBridge

bridge = MCPLiteLLMBridge()

# Initialize
await bridge.initialize()

# Chat with AI assistant
response = await bridge.chat(
    "Show me my portfolio", 
    model="openrouter/google/gemini-2.0-flash-exp"
)

# Cleanup
await bridge.cleanup()
```

## Troubleshooting

### Connection Issues

1. **DNS Resolution Error:**
   ```
   [Errno -5] No address associated with hostname
   ```
   - Check internet connectivity
   - Verify DNS settings
   - Try from a different network

2. **Timeout Errors:**
   - Increase timeout in `client.connect(timeout_seconds=60.0)`
   - Check for firewall blocking connections
   - Verify server status

3. **Authentication Failures:**
   - Ensure you complete the OAuth flow in the browser
   - Check that the generated URL is valid
   - Verify Zerodha credentials

### Common Solutions

- **"Failed to initialize MCP bridge"**: Check internet connection and MCP server accessibility
- **"OpenRouter API key not configured"**: Set the `OPENROUTER_API_KEY` environment variable
- **"Tool execution failed"**: Usually requires authentication - use the `/auth` command first

## Security

### Authentication Security
- OAuth flow happens on Zerodha's secure servers
- No credentials stored locally
- Session tokens managed securely

### Network Security
- HTTPS connections only
- Proper timeout and retry handling
- Connection validation and health checks

### Best Practices
- Keep API keys secure and never commit them to version control
- Use environment variables for sensitive configuration
- Regularly check connection health
- Monitor for unusual trading activity

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes with proper error handling
4. Add tests for new functionality
5. Ensure all tests pass
6. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- [Zerodha](https://zerodha.com/) for providing the MCP server and trading APIs
- [Model Context Protocol](https://modelcontextprotocol.io/) for the excellent MCP specification
- [OpenRouter](https://openrouter.ai/) for LLM access
- [LiteLLM](https://github.com/BerriAI/litellm) for unified LLM interface

## Support

For issues and questions:
1. Check the troubleshooting section above
2. Review [Zerodha MCP server issues](https://github.com/zerodha/kite-mcp-server/issues)
3. Open an issue in this repository
