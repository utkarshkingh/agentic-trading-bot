# PyInstaller spec — freezes the FastAPI backend into a single-file sidecar.
#
# The scientific / agent stack pulls in data files and dynamically imported
# submodules that PyInstaller can't detect automatically, so we collect them
# explicitly. Build with:  uv run pyinstaller trading-backend.spec --noconfirm
from PyInstaller.utils.hooks import collect_all, collect_submodules

datas, binaries, hiddenimports = [], [], []

# Packages that ship data files and/or import submodules at runtime.
for pkg in (
    "litellm",
    "langchain",
    "langchain_core",
    "langchain_litellm",
    "langgraph",
    "ag_ui",
    "ag_ui_langgraph",
    "pandas_ta",
    "yfinance",
    "scipy",
    "feedparser",
):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

hiddenimports += collect_submodules("uvicorn")
hiddenimports += collect_submodules("anyio")

a = Analysis(
    ["run_server.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="trading-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
)
