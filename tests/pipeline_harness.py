"""Shared primitives for tests that cross process and filesystem boundaries.

Copy fixtures before mutation, preserve executable modes, keep byte protocols
as bytes, isolate HOME, own process groups, and make teardown unconditional.
"""
from __future__ import annotations

import contextlib
import os
import pty
import shutil
import signal
import subprocess
import tempfile
from pathlib import Path
from typing import Iterator, Sequence


def fixture_copy(source: Path, root: Path, *, mode: int | None = None) -> Path:
    destination = root / source.name
    if source.is_dir():
        shutil.copytree(source, destination, copy_function=shutil.copy2)
    else:
        shutil.copy2(source, destination)
    if mode is not None:
        destination.chmod(mode)
    return destination


@contextlib.contextmanager
def isolated_home() -> Iterator[Path]:
    with tempfile.TemporaryDirectory(prefix="pipeline-home-") as name:
        old = os.environ.get("HOME")
        os.environ["HOME"] = name
        try:
            yield Path(name)
        finally:
            if old is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = old


def run_bytes(argv: Sequence[str], payload: bytes = b"", **kwargs) -> subprocess.CompletedProcess[bytes]:
    if kwargs.get("text") or kwargs.get("encoding"):
        raise ValueError("run_bytes does not accept text/encoding")
    return subprocess.run(
        list(argv), input=payload, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        check=False, **kwargs,
    )


def run_pty(argv: Sequence[str], *, timeout: float = 30) -> tuple[int, bytes]:
    master, slave = pty.openpty()
    proc = subprocess.Popen(
        list(argv), stdin=slave, stdout=slave, stderr=slave,
        start_new_session=True, close_fds=True,
    )
    os.close(slave)
    output = bytearray()
    try:
        while proc.poll() is None:
            ready, _, _ = __import__("select").select([master], [], [], min(timeout, 0.1))
            if ready:
                try:
                    output.extend(os.read(master, 65536))
                except OSError:
                    break
            timeout -= 0.1
            if timeout <= 0:
                raise subprocess.TimeoutExpired(argv, timeout)
        try:
            while chunk := os.read(master, 65536):
                output.extend(chunk)
        except OSError:
            pass
        return int(proc.returncode or 0), bytes(output)
    finally:
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
        os.close(master)


@contextlib.contextmanager
def managed_process(argv: Sequence[str], **kwargs) -> Iterator[subprocess.Popen]:
    proc = subprocess.Popen(list(argv), start_new_session=True, **kwargs)
    try:
        yield proc
    finally:
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()


def sandbox_argv(argv: Sequence[str], writable: Path) -> list[str]:
    """Return a fail-closed bwrap command; skip explicitly when unavailable."""
    bwrap = shutil.which("bwrap")
    if not bwrap:
        raise RuntimeError("bubblewrap is required for this isolation test")
    return [
        bwrap, "--die-with-parent", "--unshare-all", "--share-net",
        "--ro-bind", "/", "/", "--bind", str(writable), str(writable),
        "--chdir", str(writable), "--", *argv,
    ]
