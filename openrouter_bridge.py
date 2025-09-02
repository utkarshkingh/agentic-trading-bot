import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional, AsyncGenerator
import litellm
from dotenv import load_dotenv
from zerodha_mcp_client import ZerodhaMCPClient
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
import uvicorn

load_dotenv()

# Ensure OPENROUTER_API_KEY is available to LiteLLM
openrouter_key = os.getenv("OPENROUTER_API_KEY")
if openrouter_key:
    os.environ["OPENROUTER_API_KEY"] = openrouter_key

class MCPLiteLLMBridge:
    """
    Remote MCP + OpenRouter bridge with OAuth-first guidance and
    per-session event streaming suitable for a web UI.
    """
    def __init__(self, server_url: Optional[str] = None):
        self.logger = logging.getLogger(__name__)
        remote_url = server_url or os.getenv("MCP_SERVER_URL", "https://mcp.kite.trade/mcp")
        self.mcp_client = ZerodhaMCPClient(remote_url)
        self.tools: List[Dict[str, Any]] = []
        self._initialized = False
        self.system_message = {
            "role": "system",
            "content": (
                "You are a professional trading assistant with access to Zerodha Kite trading tools.\n\n"
                "IMPORTANT OAUTH AUTHENTICATION FLOW:\n"
                "- When users want to access their trading data, use the 'login' tool first\n"
                "- The login tool will generate a Zerodha OAuth URL\n"
                "- Tell the user to visit that URL to authenticate manually\n"
                "- After authentication, they can use other trading tools\n\n"
                "Available capabilities:\n"
                "- Portfolio management (view holdings, positions, margins)\n"
                "- Order management (place, modify, cancel orders)\n"
                "- Market data access (quotes, historical data)\n"
                "- Authentication via OAuth flow\n"
                "- Data analysis with json_dataframe tool for converting trading JSON to DataFrame\n\n"
                "Always prioritize user security and explain the authentication process clearly."
            )
        }
        # Back-compat single-session history for chat()
        self.messages: List[Dict[str, Any]] = [self.system_message]

    def _get_message_from_response(self, response):
        """Safely extract message from LiteLLM response regardless of format"""
        try:
            # Try list format first (most common in FastAPI)
            return response.choices[0].message
        except (AttributeError, IndexError, TypeError):
            try:
                # Try direct access format (terminal)
                return response.choices.message
            except AttributeError:
                # Fallback
                return response.choices[0] if hasattr(response.choices, '__getitem__') else response.choices

    def _add_json_dataframe_tool(self):
        """Add the local json_dataframe tool for data analysis"""
        self.tools.append({
            "type": "function",
            "function": {
                "name": "json_dataframe",
                "description": "Converts trading JSON (from get_historical_data) to DataFrame for analysis.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "json_string": {"type": "string", "description": "JSON string from get_historical_data."},
                        "set_date_index": {"type": "boolean", "description": "Set 'date' column as DataFrame index.", "default": False},
                        "return_format": {"type": "string", "enum": ["records", "summary", "csv_string"], "description": "Output format.", "default": "records"}
                    },
                    "required": ["json_string"]
                }
            }
        })

    async def _execute_json_dataframe(self, arguments):
        """Execute the json_dataframe tool locally"""
        import json
        import pandas as pd
        try:
            json_str = arguments.get('json_string')
            set_date_index = arguments.get('set_date_index', False)
            return_format = arguments.get('return_format', 'records')
            
            data = json.loads(json_str)
            df = pd.DataFrame(data)
            
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'])
            
            if set_date_index and 'date' in df.columns:
                df.set_index('date', inplace=True)
            
            if return_format == 'summary':
                summary = {
                    'shape': df.shape,
                    'columns': df.columns.tolist(),
                    'date_range': {
                        'start': df['date'].min().isoformat() if 'date' in df.columns and not set_date_index else None,
                        'end': df['date'].max().isoformat() if 'date' in df.columns and not set_date_index else None
                    },
                    'stats': df.describe().to_dict()
                }
                return {'success': True, 'text': 'Summary generated.', 'structured': summary}
            elif return_format == 'csv_string':
                csv_str = df.to_csv(index=set_date_index)
                return {'success': True, 'text': csv_str, 'structured': {'format': 'csv', 'rows': df.shape[0], 'cols': df.shape[1]}}
            else:
                if 'date' in df.columns and not set_date_index:
                    df['date'] = df['date'].dt.strftime('%Y-%m-%dT%H:%M:%S')
                records = df.to_dict(orient='records')
                return {'success': True, 'text': 'Converted to records.', 'structured': {'data': records, 'rows': df.shape[0], 'cols': df.shape[1]}}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    async def initialize(self) -> bool:
        """Lazy initialize MCP connection and tool schemas."""
        if self._initialized:
            return True
        try:
            self.logger.info("Initializing MCP-LiteLLM Bridge...")
            if not await self.mcp_client.connect(timeout_seconds=30.0):
                self.logger.error("Failed to connect to MCP server")
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
            
            # Add the local json_dataframe tool
            self._add_json_dataframe_tool()
            
            self._initialized = True
            tool_names = [t["function"]["name"] for t in self.tools]
            self.logger.info(f"Loaded {len(self.tools)} tools: {', '.join(tool_names)}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize: {e}")
            return False

    async def health_check(self) -> bool:
        try:
            return await self.mcp_client.health_check()
        except Exception:
            return False

    # Backward-compatible API (no event streaming)
    async def chat(self, user_message: str, model: str = "openrouter/qwen/qwen3-coder") -> str:
        if not self._initialized:
            if not await self.initialize():
                return "Failed to initialize MCP bridge. Please check connection to Zerodha MCP server."

        if not await self.mcp_client.health_check():
            self.logger.warning("MCP connection unhealthy, attempting to reconnect...")
            if not await self.mcp_client.connect():
                return "Lost connection to Zerodha MCP server. Please try again later."

        self.messages.append({"role": "user", "content": user_message})

        try:
            if not os.getenv("OPENROUTER_API_KEY"):
                return "OpenRouter API key not configured. Please set OPENROUTER_API_KEY environment variable."

            self.logger.info(f"Sending request to {model}")
            response = litellm.completion(
                model=model,
                messages=self.messages,
                tools=self.tools,
                timeout=120
            )

            # Fixed: Use helper method for safe message extraction
            assistant_message = self._get_message_from_response(response)
            tool_calls = getattr(assistant_message, 'tool_calls', None)

            if tool_calls:
                self.messages.append(assistant_message)
                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    try:
                        arguments = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}
                    except json.JSONDecodeError:
                        arguments = {}

                    try:
                        # Handle local json_dataframe tool or remote MCP tools
                        if function_name == "json_dataframe":
                            result = await self._execute_json_dataframe(arguments)
                        else:
                            result = await self.mcp_client.call_tool(function_name, arguments)
                        
                        if result["success"]:
                            text_content = result.get("text")
                            structured_content = result.get("structured")
                            if structured_content:
                                content = json.dumps(structured_content, indent=2)
                            elif text_content:
                                content = text_content
                            else:
                                content = "Tool executed successfully but returned no data."
                        else:
                            content = f"Error: {result['error']}"
                    except Exception as e:
                        content = f"Tool execution failed: {str(e)}"

                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": content
                    })

                final_response = litellm.completion(
                    model=model,
                    messages=self.messages,
                    timeout=60
                )
                # Fixed: Use helper method for safe message extraction
                final_message = self._get_message_from_response(final_response)
                final_content = final_message.content or ""
                self.messages.append({"role": "assistant", "content": final_content})
                return final_content
            else:
                assistant_content = assistant_message.content or ""
                self.messages.append({"role": "assistant", "content": assistant_content})
                return assistant_content

        except Exception as e:
            self.logger.error(f"Chat error: {e}")
            return f"Error: {str(e)}"

    def new_session(self) -> "TradingChatSession":
        return TradingChatSession(self)

class TradingChatSession:
    """
    Event-streaming session:
      - assistant_message
      - tool_call
      - tool_result
      - assistant_final
    """
    def __init__(self, bridge: MCPLiteLLMBridge):
        self.bridge = bridge
        self.messages: List[Dict[str, Any]] = [bridge.system_message]

    async def chat_events(
        self,
        user_message: str,
        model: str = "openrouter/qwen/qwen3-coder"
    ) -> AsyncGenerator[Dict[str, Any], None]:
        # Lazy initialize here so UI starts even if remote MCP is down
        if not self.bridge._initialized:
            ok = await self.bridge.initialize()
            if not ok:
                yield {"type": "error", "text": "Failed to initialize MCP bridge."}
                return

        if not os.getenv("OPENROUTER_API_KEY"):
            yield {"type": "error", "text": "OpenRouter API key not configured. Set OPENROUTER_API_KEY."}
            return

        if not await self.bridge.mcp_client.health_check():
            re_ok = await self.bridge.mcp_client.connect()
            if not re_ok:
                yield {"type": "error", "text": "Lost connection to remote MCP server. Try again later."}
                return

        self.messages.append({"role": "user", "content": user_message})

        try:
            response = litellm.completion(
                model=model,
                messages=self.messages,
                tools=self.bridge.tools,
                timeout=120
            )

            # Fixed: Use helper method for safe message extraction
            assistant_message = self.bridge._get_message_from_response(response)
            if assistant_message.content:
                yield {"type": "assistant_message", "text": assistant_message.content}

            tool_calls = getattr(assistant_message, 'tool_calls', None)
            if tool_calls:
                self.messages.append(assistant_message)
                for tc in tool_calls:
                    fname = tc.function.name
                    try:
                        args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                    except json.JSONDecodeError:
                        args = {}

                    yield {"type": "tool_call", "name": fname, "arguments": args}

                    try:
                        # Handle local json_dataframe tool or remote MCP tools
                        if fname == "json_dataframe":
                            result = await self.bridge._execute_json_dataframe(args)
                        else:
                            result = await self.bridge.mcp_client.call_tool(fname, args)
                        
                        ok = result.get("success", False)
                        text = result.get("text") or ""
                        structured = result.get("structured")
                        self.messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": text if text else (json.dumps(structured, indent=2) if structured else "OK")
                        })
                        yield {"type": "tool_result", "name": fname, "ok": ok, "text": text, "structured": structured}
                    except Exception as e:
                        err_msg = f"Tool execution failed: {str(e)}"
                        self.messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": err_msg
                        })
                        yield {"type": "tool_result", "name": fname, "ok": False, "text": err_msg, "structured": None}

                final_resp = litellm.completion(
                    model=model,
                    messages=self.messages,
                    timeout=60
                )
                # Fixed: Use helper method for safe message extraction
                final_message = self.bridge._get_message_from_response(final_resp)
                final_text = final_message.content or ""
                self.messages.append({"role": "assistant", "content": final_text})
                yield {"type": "assistant_final", "text": final_text}
                return

            final_text = assistant_message.content or ""
            self.messages.append({"role": "assistant", "content": final_text})
            yield {"type": "assistant_final", "text": final_text}

        except Exception as e:
            yield {"type": "error", "text": f"Chat error: {str(e)}"}

# ---------------------------
# Minimal FastAPI web server
# ---------------------------

# Use FastAPI lifespan instead of deprecated on_event to avoid startup failures
@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    # No eager MCP connection here; keep startup resilient
    yield
    try:
        await bridge.mcp_client.disconnect()
    except Exception:
        pass

app = FastAPI(lifespan=lifespan)
bridge = MCPLiteLLMBridge(server_url=os.getenv("MCP_SERVER_URL"))
_sessions: Dict[str, TradingChatSession] = {}

@app.get("/", response_class=HTMLResponse)
async def index():
    html = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Remote MCP Chat</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    * { box-sizing: border-box; }
    body { margin: 0; font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; color: #111; background: #f7f7f7; }
    header { background: #0b5fff; color: #fff; padding: 12px 16px; display: flex; align-items: center; justify-content: space-between; }
    header h1 { margin: 0; font-size: 18px; }
    .controls { display: flex; gap: 8px; }
    main#chat { padding: 16px; height: calc(100vh - 160px); overflow-y: auto; background: #fff; }
    .msg { margin-bottom: 12px; padding: 10px 12px; border-radius: 8px; max-width: 900px; white-space: pre-wrap; word-break: break-word; border: 1px solid #e5e5e5; }
    .msg.user { background: #eef4ff; border-color: #cddcff; }
    .msg.assistant { background: #f6f6f6; }
    .msg.system { background: #fff8e6; border-color: #ffe4a3; }
    .msg.toolcall { background: #f0fff4; border-color: #c2f0cf; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
    .msg.toolresult { background: #f8fffa; border-color: #cfeedd; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
    footer { position: fixed; bottom: 0; left: 0; right: 0; padding: 8px; background: #fff; border-top: 1px solid #eee; }
    #msg-form { display: flex; gap: 8px; }
    #msg-input { flex: 1; padding: 10px 12px; border: 1px solid #ddd; border-radius: 8px; }
    button { padding: 10px 12px; border: 1px solid #0b5fff; background: #0b5fff; color: #fff; border-radius: 8px; cursor: pointer; }
    select { padding: 8px; border-radius: 8px; border: 1px solid #cddcff; }
  </style>
</head>
<body>
  <header>
    <h1>Remote MCP Chat</h1>
    <div class="controls">
      <select id="model">
        <option value="openrouter/qwen/qwen3-235b-a22b-thinking-2507">qwen3-235b-a22b-thinking-2507</option>
        <option value="openrouter/qwen/qwen3-coder">qwen3-coder</option>
        <option value="openrouter/anthropic/claude-sonnet-4">claude-sonnet-4</option>
        <option value="openrouter/openai/gpt-5">gpt-5</option>
        <option value="openrouter/openai/gpt-4.1">gpt-4.1</option>
        <option value="openrouter/google/gemini-2.5-pro">gemini-2.5-pro</option>
        <option value="openrouter/x-ai/grok-4">grok-4</option>
        <option value="openrouter/x-ai/grok-code-fast-1">grok-code-fast-1</option>
        <option value="openrouter/deepseek/deepseek-chat-v3.1">deepseek-chat-v3.1</option>
      </select>
      <button id="btn-status">Check Status</button>
      <button id="btn-auth">Start OAuth</button>
    </div>
  </header>
  <main id="chat"></main>
  <footer>
    <form id="msg-form">
      <input id="msg-input" type="text" placeholder="Type a message..." autocomplete="off" />
      <button type="submit">Send</button>
    </form>
  </footer>
  <script>
    const chat = document.getElementById("chat");
    const form = document.getElementById("msg-form");
    const input = document.getElementById("msg-input");
    const btnStatus = document.getElementById("btn-status");
    const btnAuth = document.getElementById("btn-auth");
    const modelSelect = document.getElementById("model");
    let ws;
    function addMsg(text, cls = "assistant") {
      const div = document.createElement("div");
      div.className = "msg " + cls;
      div.textContent = text;
      chat.appendChild(div);
      chat.scrollTop = chat.scrollHeight;
    }
    function addToolCall(name, args) {
      const div = document.createElement("div");
      div.className = "msg toolcall";
      div.textContent = "[tool_call] " + name + " " + JSON.stringify(args);
      chat.appendChild(div);
      chat.scrollTop = chat.scrollHeight;
    }
    function addToolResult(name, ok, text, structured) {
      const div = document.createElement("div");
      div.className = "msg toolresult";
      const body = { ok: !!ok, text: text || "", structured: structured || null };
      div.textContent = "[tool_result] " + name + " " + JSON.stringify(body, null, 2);
      chat.appendChild(div);
      chat.scrollTop = chat.scrollHeight;
    }
    function connect() {
      const proto = location.protocol === "https:" ? "wss" : "ws";
      ws = new WebSocket(proto + "://" + location.host + "/ws");
      ws.onopen = () => addMsg("Connected to server", "system");
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          switch (msg.type) {
            case "status":
              addMsg("Status: " + msg.text, "system");
              break;
            case "assistant_message":
              addMsg(msg.text || "", "assistant");
              break;
            case "tool_call":
              addToolCall(msg.name, msg.arguments || {});
              break;
            case "tool_result":
              addToolResult(msg.name, !!msg.ok, msg.text, msg.structured);
              break;
            case "assistant_final":
              addMsg(msg.text || "", "assistant");
              break;
            case "error":
              addMsg("Error: " + msg.text, "system");
              break;
            default:
              addMsg("Event: " + ev.data, "system");
          }
        } catch (e) {
          addMsg("Invalid message: " + ev.data, "system");
        }
      };
      ws.onclose = () => addMsg("Disconnected", "system");
    }
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const text = input.value.trim();
      if (!text || !ws || ws.readyState !== WebSocket.OPEN) return;
      addMsg(text, "user");
      ws.send(JSON.stringify({ type: "user_message", text, model: modelSelect.value }));
      input.value = "";
    });
    btnStatus.addEventListener("click", () => {
      if (!ws || ws.readyState !== WebSocket.OPEN) return;
      ws.send(JSON.stringify({ type: "status" }));
    });
    btnAuth.addEventListener("click", () => {
      if (!ws || ws.readyState !== WebSocket.OPEN) return;
      const text = "Please help me authenticate with Zerodha.";
      addMsg(text, "user");
      ws.send(JSON.stringify({ type: "user_message", text, model: modelSelect.value }));
    });
    connect();
  </script>
</body>
</html>
    """.strip()
    return HTMLResponse(html)

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    ws_id = str(id(ws))
    _sessions[ws_id] = bridge.new_session()
    await ws.send_text(json.dumps({"type": "status", "text": "connected"}))
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_text(json.dumps({"type": "error", "text": "Invalid JSON"}))
                continue

            mtype = msg.get("type")
            if mtype == "user_message":
                text = msg.get("text", "")
                model = msg.get("model", "openrouter/qwen/qwen3-coder")
                async for event in _sessions[ws_id].chat_events(text, model=model):
                    await ws.send_text(json.dumps(event))
            elif mtype == "status":
                ok = await bridge.health_check()
                await ws.send_text(json.dumps({"type": "status", "text": "healthy" if ok else "unhealthy"}))
            else:
                await ws.send_text(json.dumps({"type": "error", "text": f"Unknown message type: {mtype}"}))
    except WebSocketDisconnect:
        pass
    finally:
        _sessions.pop(ws_id, None)

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    
    print(f"\n Starting MCP Trading Assistant")
    print(f" Web Interface: http://localhost:{port}")
    print(f"\nPress Ctrl+C to stop\n")
    
    uvicorn.run("openrouter_bridge:app", host="localhost", port=port, reload=False)
