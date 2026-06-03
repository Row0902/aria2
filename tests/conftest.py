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
        from aria2_bin import get_binary_path

        return get_binary_path()
    except FileNotFoundError, ImportError:
        return None


async def _start_aria2c(
    binary: Path,
    secret: str,
    download_dir: Path,
    port_read_timeout: float = 10.0,
) -> tuple[asyncio.subprocess.Process, int]:
    """Start aria2c with RPC enabled and a random OS-assigned port.

    Returns (process, port). Raises RuntimeError if aria2c fails to
    start or doesn't announce a listening port within *port_read_timeout*
    seconds.
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

    port = await _read_port_from_output(process, timeout=port_read_timeout)
    return process, port


_PORT_RE = re.compile(r"listening on TCP port (\d+)")


async def _read_port_from_output(
    process: asyncio.subprocess.Process,
    timeout: float = 10.0,
) -> int:
    """Read stderr until we find the port aria2c is listening on.

    Raises RuntimeError on timeout or if aria2c exits before
    printing the port.
    """
    stderr_stream = process.stderr
    assert stderr_stream is not None

    stderr_lines: list[str] = []

    async def _reader() -> int:
        while True:
            line_bytes = await stderr_stream.readline()
            if not line_bytes:
                msg = "aria2c exited before printing port"
                if stderr_lines:
                    msg += f". stderr: {' | '.join(stderr_lines[-5:])}"
                raise RuntimeError(msg)

            line = line_bytes.decode("utf-8", errors="replace").strip()
            stderr_lines.append(line)
            match = _PORT_RE.search(line)
            if match:
                return int(match.group(1))

    try:
        return await asyncio.wait_for(_reader(), timeout=timeout)
    except TimeoutError:
        msg = "aria2c did not announce a port within {timeout}s"
        if stderr_lines:
            msg += f". stderr: {' | '.join(stderr_lines[-5:])}"
        raise RuntimeError(msg) from None


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
    binary is not available or fails to start.
    """
    if aria2c_binary is None:
        pytest.skip("aria2c binary not found — install system-wide or build package")

    with tempfile.TemporaryDirectory(prefix="aria2-test-") as tmpdir:
        download_dir = Path(tmpdir)
        secret = "testsecret"

        try:
            process, port = await _start_aria2c(aria2c_binary, secret, download_dir)
        except RuntimeError:
            pytest.skip(
                "aria2c binary found but failed to start (wrong version or missing dependencies)"
            )

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
