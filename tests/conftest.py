"""pytest fixtures — unit mocks and integration (real aria2c daemon)."""

from __future__ import annotations

import asyncio
import re
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from aria2 import Aria2Client

# ── Integration test fixture ───────────────────────────────────


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    """Select asyncio for anyio-based helpers."""
    return "asyncio"


def _find_aria2c() -> Path | None:
    """Locate the aria2c binary (bundled or system)."""
    try:
        from aria2.bin import get_binary_path

        return get_binary_path()
    except FileNotFoundError, ImportError:
        return None


async def _start_aria2c(
    binary: Path,
    secret: str,
    download_dir: Path,
) -> tuple[asyncio.subprocess.Process, int]:
    """Start aria2c with RPC enabled and a random OS-assigned port.

    Returns (process, port).
    """
    args = [
        str(binary),
        "--enable-rpc",
        "--rpc-listen-port=0",
        f"--rpc-secret={secret}",
        f"--dir={download_dir}",
        "--console-log-level=error",
        "--allow-overwrite=true",
        "--auto-file-renaming=false",
    ]

    process = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    port = await _read_port_from_output(process)
    return process, port


_PORT_RE = re.compile(r"listening on TCP port (\d+)")


async def _read_port_from_output(process: asyncio.subprocess.Process) -> int:
    """Read stderr until we find the port aria2c is listening on."""
    assert process.stderr is not None

    while True:
        line_bytes = await process.stderr.readline()
        if not line_bytes:
            raise RuntimeError("aria2c exited before printing port")

        line = line_bytes.decode("utf-8", errors="replace").strip()
        match = _PORT_RE.search(line)
        if match:
            return int(match.group(1))


@pytest.fixture(scope="session")
def aria2c_binary() -> Path | None:
    """Path to aria2c binary, or None if unavailable."""
    return _find_aria2c()


@pytest.fixture
async def integration_client(
    aria2c_binary: Path | None,
) -> AsyncIterator[Aria2Client]:
    """Start a real aria2c daemon and yield a connected client.

    Requires a system-installed or bundled aria2c binary.
    Tests using this fixture are automatically skipped when the
    binary is not available.
    """
    if aria2c_binary is None:
        pytest.skip("aria2c binary not found — install system-wide or build package")

    with tempfile.TemporaryDirectory(prefix="aria2-test-") as tmpdir:
        download_dir = Path(tmpdir)
        secret = "testsecret"

        process, port = await _start_aria2c(aria2c_binary, secret, download_dir)
        client = Aria2Client(
            host="127.0.0.1",
            port=port,
            secret=secret,
            timeout=5.0,
        )

        try:
            await client.connect()
            yield client
        finally:
            await client.close()
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=5.0)
            except TimeoutError, ProcessLookupError:
                process.kill()
                await process.wait()
