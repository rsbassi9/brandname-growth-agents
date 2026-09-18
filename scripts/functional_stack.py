"""Disposable Linux network namespace + synthetic data, never the live app.

All verbs operate on a mode-0600 state file, not shell-sourced instructions.
No credentials are inherited; no source .env, data, memory or outputs are copied.
"""
from __future__ import annotations

import io
import json
import os
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".test-stack.env"
PYTHON = str(ROOT / ".venv/bin/python3")
PORT = "18761"  # isolated loopback only: never the host's port


def environment(root: Path) -> dict[str, str]:
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin:/usr/sbin"),
        "HOME": str(root / "home"), "LANG": "C.UTF-8",
        "DATA_DIR": str(root / "state"), "BRAND_DATA_DIR": str(root / "state"),
        "BRAND_DATABASE_URL": f"sqlite:///{root / 'state/app.db'}",
        "BRAND_NAME": "Synthetic Functional Brand",
        "LOCAL_ONLY_AGENT_RUNS": "true", "GOOGLE_DRIVE_ENABLED": "false",
        "SHOPIFY_WRITE_ENABLED": "false", "BRAND_BACKUP_ENABLED": "false",
        "OPENAI_API_KEY": "", "BRAND_OPENAI_API_KEY": "",
        "PLAYWRIGHT_BROWSERS_PATH": str(ROOT / ".cache/ms-playwright"),
    }


def validate_root(root: Path, marker: str) -> None:
    if (root.is_symlink() or root.parent != Path(tempfile.gettempdir()).resolve()
            or not root.name.startswith("ari-growth-stack-")
            or not (root / ".marker").is_file()
            or (root / ".marker").read_text() != marker):
        raise ValueError("Refusing non-owned functional-stack path")


def state() -> dict:
    data = json.loads(STATE.read_text())
    validate_root(Path(data["root"]), data["marker"])
    return data


def run(argv, **kwargs):
    return subprocess.run(argv, check=True, timeout=180, **kwargs)


def ticks(pid: int) -> str:
    return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19]


def write_state(data: dict) -> None:
    with STATE.open("w") as stream:
        os.fchmod(stream.fileno(), 0o600)
        json.dump(data, stream)


def stop(data: dict) -> None:
    pid = data.get("pid")
    if not pid or not Path(f"/proc/{pid}").exists():
        return
    if ticks(pid) != data["ticks"] or os.getpgid(pid) != pid:
        raise ValueError("Process identity changed; refusing to signal it")
    os.killpg(pid, signal.SIGTERM)
    for _ in range(70):
        if not Path(f"/proc/{pid}").exists():
            return
        # A completed child can remain a zombie until its controller reaps it.
        if Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0] == "Z":
            return
        time.sleep(0.1)
    if ticks(pid) == data["ticks"]:
        os.killpg(pid, signal.SIGKILL)


def check(verb: str) -> None:
    data = state()
    if ticks(data["pid"]) != data["ticks"]:
        raise ValueError("Functional instance is no longer running")
    run(["nsenter", "-t", str(data["pid"]), "-n", PYTHON, "-m", "coverage", "run", "--append",
         "--data-file", str(ROOT / ".coverage.functional-checks"),
         str(ROOT / "tests/functional/checks.py"), verb, f"http://127.0.0.1:{PORT}"],
        env=environment(Path(data["root"])), cwd=ROOT)


def start(data: dict) -> None:
    root = Path(data["root"])
    with (root / "server.log").open("ab") as log:
        process = subprocess.Popen(
            ["unshare", "--net", PYTHON, "-m", "coverage", "run", "--append",
             "--data-file", str(ROOT / ".coverage.functional-server"),
             str(Path(__file__).resolve()), "_serve", str(root)],
            stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True,
            env=environment(root), cwd=root,
        )
    data.update(pid=process.pid, ticks=ticks(process.pid))
    write_state(data)
    for _ in range(40):
        if process.poll() is not None:
            raise RuntimeError("Functional server failed; inspect its synthetic server.log")
        try:
            check("health")
            return
        except subprocess.CalledProcessError:
            time.sleep(0.25)
    raise RuntimeError("Functional server startup deadline exceeded")


def up() -> None:
    if sys.platform != "linux" or os.geteuid() != 0:
        raise RuntimeError("Requires Linux root for an isolated network namespace (CI uses sudo)")
    if STATE.exists() or STATE.is_symlink():
        raise RuntimeError("Stack already exists; inspect it and run down first")
    root = Path(tempfile.mkdtemp(prefix="ari-growth-stack-")).resolve()
    marker = uuid.uuid4().hex
    (root / ".marker").write_text(marker)
    for path in (root / "home", root / "state", root / "app"):
        path.mkdir()
    data = {"root": str(root), "marker": marker}
    write_state(data)
    try:
        archive = run(["git", "archive", "HEAD", "app", "src", "agent_instructions"],
                      cwd=ROOT, capture_output=True).stdout
        with tarfile.open(fileobj=io.BytesIO(archive)) as source:
            source.extractall(root / "app", filter="data")
        context = root / "app/brand_context"
        context.mkdir()
        (context / "brand_brief.md").write_text("Synthetic clothing brand. Use only synthetic fixtures. Drafts only.")
        start(data)
    except Exception:
        down()
        raise


def apply() -> None:
    data = state()
    root = Path(data["root"])
    # The same Vite/TypeScript build as Frontend Studio CI, not a fake index.
    run(["npm", "run", "build", "--prefix", "frontend"], cwd=ROOT, env=environment(root))
    destination = root / "app/frontend/dist"
    shutil.copytree(ROOT / "frontend/dist", destination, dirs_exist_ok=True)
    stop(data)
    start(data)  # same uvicorn app.main:app + init_db() startup mechanism
    check("smoke")


def down() -> None:
    if not STATE.exists():
        return
    data = state()
    stop(data)
    root = Path(data["root"])
    validate_root(root, data["marker"])
    shutil.rmtree(root)
    STATE.unlink()


def serve(root: Path) -> None:
    sys.path.insert(0, str(ROOT))
    from tests.pipeline_harness import managed_process

    def terminate(_signum, _frame):
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, terminate)
    run(["ip", "link", "set", "lo", "up"])
    with managed_process([PYTHON, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", PORT],
                         cwd=root / "app", env=environment(root)) as process:
        raise SystemExit(process.wait())


def main() -> None:
    verb = sys.argv[1] if len(sys.argv) > 1 else ""
    if verb == "_serve":
        serve(Path(sys.argv[2]))
    elif verb == "ci":
        try:
            up()
            apply()
            check("seed")
            check("integration")
            if "--no-e2e" not in sys.argv[2:]:
                check("e2e")
            print("functional cycle: PASS")
        finally:
            down()
    elif verb in {"up", "apply", "down"}:
        {"up": up, "apply": apply, "down": down}[verb]()
    elif verb in {"seed", "integration", "e2e", "smoke"}:
        check(verb)
    else:
        raise SystemExit("usage: test-stack.sh {up|apply|seed|integration|e2e|smoke|down|ci [--no-e2e]}")


if __name__ == "__main__":
    main()
