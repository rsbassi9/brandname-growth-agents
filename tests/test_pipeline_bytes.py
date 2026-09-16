"""Regression coverage for the lint-only binary subprocess helper change."""

import sys

import pytest

from tests.pipeline_harness import run_bytes


def test_binary_streams_and_nonzero_exit_are_preserved():
    result = run_bytes(
        [sys.executable, "-c", "import sys; sys.stdout.buffer.write(sys.stdin.buffer.read()); "
         "sys.stderr.buffer.write(b'error\\x00\\xff'); sys.exit(3)"],
        b"payload\x00\xff",
    )
    assert result.returncode == 3
    assert result.stdout == b"payload\x00\xff"
    assert result.stderr == b"error\x00\xff"


@pytest.mark.parametrize("kwargs", [{"text": True}, {"encoding": "utf-8"}])
def test_text_mode_is_rejected(kwargs):
    with pytest.raises(ValueError, match="text/encoding"):
        run_bytes([sys.executable, "-c", "pass"], **kwargs)
