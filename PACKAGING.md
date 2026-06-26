# Packaging the Trading Bot

The app ships as a **Windows desktop app** and an **Android app** from one
codebase using [Tauri 2](https://v2.tauri.app/).

## Architecture

```
┌─────────────────────────────┐         ┌──────────────────────────┐
│ Tauri app (static Next.js)  │  HTTP   │ FastAPI AG-UI backend    │
│ CopilotKit → HttpAgent ─────┼────────▶│ LangGraph trading agent  │
└─────────────────────────────┘ AG-UI   └──────────────────────────┘
```

The frontend is a **static export** that talks to the backend directly over the
AG-UI protocol (no Node runtime tier). Where the backend runs differs by target:

| Target  | Backend location                                              |
|---------|--------------------------------------------------------------|
| Windows | Bundled **sidecar** — Tauri launches it on startup (one app) |
| Android | A backend on your **PC (LAN)** or a hosted server           |

Python can't realistically run a server on Android, so the Android app is a
thin client. Set its backend address from the in-app **Backend** settings.

## Prerequisites

**Everything (dev):**
- Node.js 20+ and npm
- [uv](https://docs.astral.sh/uv/) + Python (3.11 recommended for sidecar builds)

**Windows installer:**
- [Rust](https://www.rust-lang.org/tools/install) — then `rustup default stable`
- [Microsoft C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/) (Desktop development with C++)
- WebView2 (preinstalled on Windows 11)

**Android APK:**
- JDK 17 (`JAVA_HOME` set)
- Android Studio → SDK Platform, NDK, and Build Tools
- Env vars `ANDROID_HOME` and `NDK_HOME`
- Rust Android targets: `rustup target add aarch64-linux-android armv7-linux-androideabi i686-linux-android x86_64-linux-android`

## Development

```bash
npm run setup     # install frontend + backend deps (once)
npm run dev       # backend + frontend in the browser at http://localhost:3000
npm run app       # backend + native desktop window (needs Rust + MSVC)
```

## Build: Windows installer

```bash
# 1. Generate app icons once from a square PNG (≥512×512):
cd frontend && npm run tauri icon path/to/logo.png && cd ..

# 2. Build the Python sidecar, then the installer:
npm run build:windows
```

Outputs land in `frontend/src-tauri/target/release/bundle/`:
- `msi/*.msi` (WiX)
- `nsis/*-setup.exe` (NSIS)

> **PyInstaller tip:** build the sidecar in a Python 3.11 environment
> (`uv venv --python 3.11`) for the widest package compatibility. The spec in
> `backend/trading-backend.spec` collects the heavy scientific/agent packages;
> if a module is missing at runtime, add it to that spec's package list.

## Build: Android APK

```bash
# 1. One-time: generate the Android Gradle project
npm run android:init

# 2. Allow the app to reach an HTTP backend on your LAN.
#    Edit frontend/src-tauri/gen/android/app/src/main/AndroidManifest.xml
#    and add to the <application> tag:
#        android:usesCleartextTraffic="true"
#    (or serve the backend over HTTPS / a Tailscale tunnel and skip this)

# 3. On your PC, expose the backend on the LAN:
npm run serve:lan        # binds 0.0.0.0:8000 — allow it through the firewall

# 4. Build the APK:
npm run android:build
```

APK output: `frontend/src-tauri/gen/android/app/build/outputs/apk/`.

On the phone (same WiFi), open the app → **Backend** settings → set
`http://<your-pc-lan-ip>:8000` → Save. Find the IP with `ipconfig`.

### Always-on backend (optional)

If you don't want to keep your PC running, host the backend and point the app
at its URL. A `Dockerfile` for the backend lives in `backend/`. Any container
host works (Fly.io, Railway, Cloud Run, a VPS). Put your model API key in the
host's environment, not the app.
```
