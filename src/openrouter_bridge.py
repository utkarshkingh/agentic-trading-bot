import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional, AsyncGenerator

import litellm
from dotenv import load_dotenv
from src.zerodha_mcp_client import ZerodhaMCPClient
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
        self.dataframes: Dict[str, Any] = {}
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
        self.messages: List[Dict[str, Any]] = [self.system_message]

    # ----------------------------------------------------------------------
    # Helper utilities
    # ----------------------------------------------------------------------
    def _get_message_from_response(self, response):
        """Safely extract message from LiteLLM response regardless of format"""
        try:
            return response.choices[0].message
        except (AttributeError, IndexError, TypeError):
            try:
                return response.choices.message
            except AttributeError:
                return response.choices[0] if hasattr(response.choices, '__getitem__') else response.choices

    def _add_json_dataframe_tool(self):
        """Add the local json_dataframe tool for data analysis with memory storage and CSV download"""
        self.tools.append({
            "type": "function",
            "function": {
                "name": "json_dataframe",
                "description": "Converts trading JSON (from get_historical_data) to DataFrame for analysis. Can save to memory and provide CSV download.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "json_string": {
                            "type": "string",
                            "description": "JSON string from get_historical_data."
                        },
                        "set_date_index": {
                            "type": "boolean",
                            "description": "Set 'date' column as DataFrame index.",
                            "default": False
                        },
                        "return_format": {
                            "type": "string",
                            "enum": ["records", "summary", "csv_string"],
                            "description": "Output format.",
                            "default": "records"
                        },
                        "save_name": {
                            "type": "string",
                            "description": "If provided, save the dataframe in memory under this name."
                        },
                        "download_csv": {
                            "type": "boolean",
                            "description": "If true, return CSV string for download.",
                            "default": False
                        }
                    },
                    "required": ["json_string"]
                }
            }
        })


    async def _execute_json_dataframe(self, arguments):
        """Execute the json_dataframe tool locally"""
        import pandas as pd
        try:
            data = json.loads(arguments.get("json_string", "[]"))
            df = pd.DataFrame(data)

            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"])

            if arguments.get("set_date_index") and "date" in df.columns:
                df.set_index("date", inplace=True)

            fmt = arguments.get("return_format", "records")
            if fmt == "summary":
                summary = {
                    "shape": df.shape,
                    "columns": df.columns.tolist(),
                    "date_range": {
                        "start": df["date"].min().isoformat() if "date" in df.columns else None,
                        "end": df["date"].max().isoformat() if "date" in df.columns else None,
                    },
                    "stats": df.describe().to_dict(),
                }
                return {"success": True, "text": "Summary generated.", "structured": summary}

            if fmt == "csv_string":
                csv_str = df.to_csv(index=arguments.get("set_date_index", False))
                return {
                    "success": True,
                    "text": csv_str,
                    "structured": {"format": "csv", "rows": df.shape[0], "cols": df.shape[1]},
                }

            # default records
            if "date" in df.columns and not arguments.get("set_date_index"):
                df["date"] = df["date"].dt.strftime("%Y-%m-%dT%H:%M:%S")
            records = df.to_dict(orient="records")
            return {
                "success": True,
                "text": "Converted to records.",
                "structured": {"data": records, "rows": df.shape[0], "cols": df.shape[1]},
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    # ----------------------------------------------------------------------
    # Initialization & health
    # ----------------------------------------------------------------------
    async def initialize(self) -> bool:
        if self._initialized:
            return True
        try:
            self.logger.info("Initializing MCP-LiteLLM Bridge…")
            if not await self.mcp_client.connect(timeout_seconds=30.0):
                self.logger.error("Failed to connect to MCP server")
                return False

            self.tools = []
            for tool in await self.mcp_client.get_available_tools():
                self.tools.append({
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool["description"],
                        "parameters": tool.get("schema", {"type": "object", "properties": {}})
                    }
                })

            self._add_json_dataframe_tool()
            self._initialized = True
            self.logger.info("Loaded %s tools", len(self.tools))
            return True
        except Exception as e:
            self.logger.error("Initialize failed: %s", e)
            return False

    async def health_check(self) -> bool:
        try:
            return await self.mcp_client.health_check()
        except Exception:
            return False

    # ----------------------------------------------------------------------
    # Synchronous chat helper
    # ----------------------------------------------------------------------
    async def chat(self, user_message: str, model: str = "openrouter/qwen/qwen3-coder") -> str:
        if not self._initialized and not await self.initialize():
            return "Failed to initialize MCP bridge. Please check connection to Zerodha MCP server."

        if not await self.mcp_client.health_check() and not await self.mcp_client.connect():
            return "Lost connection to Zerodha MCP server. Please try again later."

        self.messages.append({"role": "user", "content": user_message})

        try:
            if not os.getenv("OPENROUTER_API_KEY"):
                return "OpenRouter API key not configured. Please set OPENROUTER_API_KEY."

            response = litellm.completion(
                model=model,
                messages=self.messages,
                tools=self.tools,
                timeout=120,
            )

            assistant_message = self._get_message_from_response(response)
            tool_calls = getattr(assistant_message, "tool_calls", None)

            if tool_calls:
                self.messages.append(assistant_message)
                for call in tool_calls:
                    fn, args = call.function.name, json.loads(call.function.arguments or "{}")
                    try:
                        result = (
                            await self._execute_json_dataframe(args)
                            if fn == "json_dataframe"
                            else await self.mcp_client.call_tool(fn, args)
                        )
                        content = (
                            json.dumps(result.get("structured"), indent=2)
                            if result["success"] and result.get("structured")
                            else result.get("text", "Tool executed successfully but returned no data.")
                            if result["success"]
                            else f"Error: {result.get('error')}"
                        )
                    except Exception as e:
                        content = f"Tool execution failed: {e}"

                    self.messages.append({"role": "tool", "tool_call_id": call.id, "content": content})

                final = litellm.completion(model=model, messages=self.messages, timeout=60)
                final_text = self._get_message_from_response(final).content or ""
                self.messages.append({"role": "assistant", "content": final_text})
                return final_text

            # no tool-call path
            assistant_text = assistant_message.content or ""
            self.messages.append({"role": "assistant", "content": assistant_text})
            return assistant_text
        except Exception as exc:
            self.logger.error("Chat error: %s", exc)
            return f"Error: {exc}"

    # ----------------------------------------------------------------------
    # Session factory
    # ----------------------------------------------------------------------
    def new_session(self) -> "TradingChatSession":
        return TradingChatSession(self)


class TradingChatSession:
    """
    Event-streaming session:
      assistant_message → tool_call → tool_result → assistant_final
    """
    def __init__(self, bridge: MCPLiteLLMBridge):
        self.bridge = bridge
        self.messages: List[Dict[str, Any]] = [bridge.system_message]

    async def chat_events(
        self,
        user_message: str,
        model: str = "openrouter/qwen/qwen3-coder",
    ) -> AsyncGenerator[Dict[str, Any], None]:

        if not self.bridge._initialized and not await self.bridge.initialize():
            yield {"type": "error", "text": "Failed to initialize MCP bridge."}
            return

        if not os.getenv("OPENROUTER_API_KEY"):
            yield {"type": "error", "text": "OpenRouter API key not configured. Set OPENROUTER_API_KEY."}
            return

        if not await self.bridge.mcp_client.health_check() and not await self.bridge.mcp_client.connect():
            yield {"type": "error", "text": "Lost connection to remote MCP server. Try again later."}
            return

        self.messages.append({"role": "user", "content": user_message})

        try:
            response = litellm.completion(
                model=model, messages=self.messages, tools=self.bridge.tools, timeout=120
            )
            assistant = self.bridge._get_message_from_response(response)

            if assistant.content:
                yield {"type": "assistant_message", "text": assistant.content}

            tool_calls = getattr(assistant, "tool_calls", None)
            if tool_calls:
                self.messages.append(assistant)
                for tc in tool_calls:
                    fname, args = tc.function.name, json.loads(tc.function.arguments or "{}")
                    yield {"type": "tool_call", "name": fname, "arguments": args}

                    try:
                        result = (
                            await self.bridge._execute_json_dataframe(args)
                            if fname == "json_dataframe"
                            else await self.bridge.mcp_client.call_tool(fname, args)
                        )
                        ok = result.get("success", False)
                        text = result.get("text") or ""
                        structured = result.get("structured")

                        self.messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": text if text else json.dumps(structured, indent=2) if structured else "OK",
                        })

                        yield {"type": "tool_result", "name": fname, "ok": ok, "text": text, "structured": structured}
                    except Exception as e:
                        err = f"Tool execution failed: {e}"
                        self.messages.append({"role": "tool", "tool_call_id": tc.id, "content": err})
                        yield {"type": "tool_result", "name": fname, "ok": False, "text": err, "structured": None}

                final = litellm.completion(model=model, messages=self.messages, timeout=60)
                final_text = self.bridge._get_message_from_response(final).content or ""
                self.messages.append({"role": "assistant", "content": final_text})
                yield {"type": "assistant_final", "text": final_text}
                return

            final_text = assistant.content or ""
            self.messages.append({"role": "assistant", "content": final_text})
            yield {"type": "assistant_final", "text": final_text}
        except Exception as e:
            yield {"type": "error", "text": f"Chat error: {e}"}


# ----------------------------------------------------------------------
# Minimal FastAPI web server
# ----------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
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
    # raw string eliminates invalid-escape warnings
    html = r"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Remote MCP Chat</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    * { box-sizing: border-box; }
    body { margin: 0; font-family: system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif; color: #111; background: #f7f7f7; }
    header { background:#0b5fff; color:#fff; padding:12px 16px; display:flex; align-items:center; justify-content:space-between; }
    header h1 { margin:0; font-size:18px; }
    .controls { display:flex; gap:8px; }
    main#chat { padding:16px; height:calc(100vh - 160px); overflow-y:auto; background:#fff; }
    .msg { margin-bottom:12px; padding:10px 12px; border-radius:8px; max-width:900px; white-space:pre-wrap; word-break:break-word; border:1px solid #e5e5e5; }
    .msg.user { background:#eef4ff; border-color:#cddcff; }
    .msg.assistant { background:#f6f6f6; }
    .msg.system { background:#fff8e6; border-color:#ffe4a3; }
    .msg.toolcall { background:#f0fff4; border-color:#c2f0cf; font-family:ui-monospace, SFMono-Regular,Menlo,Consolas,monospace; }
    .msg.toolresult { background:#f8fffa; border-color:#cfeedd; font-family:ui-monospace, SFMono-Regular,Menlo,Consolas,monospace; }
    .msg a { color:#0b5fff; text-decoration:underline; word-break:break-all; }
    .msg a:hover { color:#0040cc; }
    footer { position:fixed; bottom:0; left:0; right:0; padding:8px; background:#fff; border-top:1px solid #eee; }
    #msg-form { display:flex; gap:8px; }
    #msg-input { flex:1; padding:10px 12px; border:1px solid #ddd; border-radius:8px; }
    button { padding:10px 12px; border:1px solid #0b5fff; background:#0b5fff; color:#fff; border-radius:8px; cursor:pointer; }
    select { padding:8px; border-radius:8px; border:1px solid #cddcff; }
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

    // ------------------------------------------------------------------
    // Convert URLs in any text to clickable links
    // ------------------------------------------------------------------
    function linkifyText(text) {
      const urlRegex = /(https?:\/\/[^\s]+)/gi;    // robust, minimal
      return text.replace(urlRegex, '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>');
    }

    function addMsg(text, cls = "assistant") {
      const div = document.createElement("div");
      div.className = "msg " + cls;
      div.innerHTML = linkifyText(text);           // highlight links
      chat.appendChild(div);
      chat.scrollTop = chat.scrollHeight;
    }

    function addToolCall(name, args) {
      const div = document.createElement("div");
      div.className = "msg toolcall";
      div.innerHTML = linkifyText("[tool_call] " + name + " " + JSON.stringify(args));
      chat.appendChild(div);
      chat.scrollTop = chat.scrollHeight;
    }

    function addToolResult(name, ok, text, structured) {
      const div = document.createElement("div");
      div.className = "msg toolresult";
      const body = { ok: !!ok, text: text || "", structured: structured || null };
      div.innerHTML = linkifyText("[tool_result] " + name + " " + JSON.stringify(body, null, 2));
      chat.appendChild(div);
      chat.scrollTop = chat.scrollHeight;
    }

    function connect() {
      const proto = location.protocol === "https:" ? "wss" : "ws";
      ws = new WebSocket(proto + "://" + location.host + "/ws");
      ws.onopen = () => addMsg("Connected to server", "system");
      ws.onmessage = ev => {
        try {
          const msg = JSON.parse(ev.data);
          switch (msg.type) {
            case "status":          addMsg("Status: " + msg.text, "system"); break;
            case "assistant_message": addMsg(msg.text || "", "assistant"); break;
            case "tool_call":       addToolCall(msg.name, msg.arguments || {}); break;
            case "tool_result":     addToolResult(msg.name, !!msg.ok, msg.text, msg.structured); break;
            case "assistant_final": addMsg(msg.text || "", "assistant"); break;
            case "error":           addMsg("Error: " + msg.text, "system"); break;
            default:                addMsg("Event: " + ev.data, "system");
          }
        } catch (e) {
          addMsg("Invalid message: " + ev.data, "system");
        }
      };
      ws.onclose = () => addMsg("Disconnected", "system");
    }

    form.addEventListener("submit", e => {
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

            if msg.get("type") == "user_message":
                text = msg.get("text", "")
                model = msg.get("model", "openrouter/qwen/qwen3-coder")
                async for event in _sessions[ws_id].chat_events(text, model=model):
                    await ws.send_text(json.dumps(event))

            elif msg.get("type") == "status":
                ok = await bridge.health_check()
                await ws.send_text(json.dumps({"type": "status", "text": "healthy" if ok else "unhealthy"}))

            else:
                await ws.send_text(json.dumps({"type": "error", "text": f"Unknown message type: {msg.get('type')}"}))
    except WebSocketDisconnect:
        pass
    finally:
        _sessions.pop(ws_id, None)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    print("\n Starting MCP Trading Assistant")
    print(f" Web Interface: http://localhost:{port}")
    print("\nPress Ctrl+C to stop\n")
    uvicorn.run("openrouter_bridge:app", host="localhost", port=port, reload=False)
