# Agentic Trading Bot

AI trading analyst built on a **LangGraph** agent and the **AG-UI / A2UI**
protocol. It runs technical, fundamental, sentiment, and risk analysis over
Indian (NSE/BSE) and global markets, streaming rich generative UI to the
frontend. Ships as a **Windows desktop app** and an **Android app** from a
single codebase via [Tauri 2](https://v2.tauri.app/).

## Stack

- **Backend** — FastAPI + LangGraph ReAct agent, multi-provider LLMs via
  LiteLLM, tools for market data (yfinance), technical analysis (pandas-ta,
  5-strategy ensemble), fundamentals, news sentiment, and risk (VaR, Sharpe,
  drawdown). Optional Zerodha Kite MCP for live portfolio data.
- **Frontend** — Next.js (static export) + CopilotKit v2 + A2UI renderer,
  connected directly to the backend over AG-UI.
- **Shell** — Tauri 2 wraps the static frontend; the backend ships as a
  bundled sidecar on desktop.

## Quick start

```bash
npm run setup     # install frontend + backend deps (once)
npm run dev       # backend + frontend together → http://localhost:3000
```

Set your model and API key from the **Model** panel in the app sidebar — paste
any vendor's key (OpenAI, Anthropic, OpenRouter, Gemini, Groq, Ollama, …) and
LiteLLM routes it automatically. The choice persists on the backend, so this
works the same in the desktop and Android apps. (Alternatively, seed defaults
via `backend/.env` — see `backend/.env.example`.)

Run it as a native desktop window (needs the Rust toolchain):

```bash
npm run app
```

## Packaging (Windows + Android)

See **[PACKAGING.md](./PACKAGING.md)** for prerequisites and build commands for
the Windows installer and the Android APK.

## Disclaimer

For informational and personal use only. Not financial advice.
