from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "dashboard"
LOG_DIR.mkdir(exist_ok=True)

stdout = (LOG_DIR / "uvicorn.live.log").open("ab")
stderr = (LOG_DIR / "uvicorn.err.log").open("ab")

creationflags = 0
if sys.platform.startswith("win"):
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS

process = subprocess.Popen(
    [
        str(ROOT / ".venv" / "Scripts" / "python.exe"),
        "-m",
        "uvicorn",
        "src.dashboard:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8765",
    ],
    cwd=ROOT,
    stdin=subprocess.DEVNULL,
    stdout=stdout,
    stderr=stderr,
    close_fds=True,
    creationflags=creationflags,
)

print(process.pid)
