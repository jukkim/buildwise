"""Blender MCP TCP client with connection pooling.

Manages connections to one or more headless Blender instances running the
blender-mcp addon (TCP socket on port 9876).  Commands are JSON objects
sent over the socket; responses are JSON (no trailing newline guaranteed).
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 60.0


class BlenderError(Exception):
    """Raised when a Blender command returns an error status."""


class BlenderTimeoutError(BlenderError):
    """Raised when a Blender command times out."""


class BlenderConnectionError(BlenderError):
    """Raised when no Blender instance is reachable."""


@dataclass
class _Connection:
    host: str
    port: int
    reader: asyncio.StreamReader | None = None
    writer: asyncio.StreamWriter | None = None
    busy: bool = False

    async def connect(self) -> None:
        self.reader, self.writer = await asyncio.open_connection(self.host, self.port)

    async def close(self) -> None:
        if self.writer:
            self.writer.close()
            try:
                await self.writer.wait_closed()
            except Exception:
                pass
        self.reader = None
        self.writer = None

    @property
    def connected(self) -> bool:
        return self.writer is not None and not self.writer.is_closing()


@dataclass
class BlenderPool:
    """Async connection pool for Blender MCP instances.

    Args:
        hosts: list of (host, port) tuples for Blender containers.
        timeout: per-command timeout in seconds.
    """

    hosts: list[tuple[str, int]] = field(default_factory=lambda: [("localhost", 9876)])
    timeout: float = _DEFAULT_TIMEOUT
    _connections: list[_Connection] = field(default_factory=list, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    async def execute(self, command: dict) -> dict:
        """Send a command to an available Blender instance and return the response."""
        conn = await self._acquire()
        try:
            payload = json.dumps(command, ensure_ascii=False).encode() + b"\n"
            if conn.writer is None or conn.reader is None:
                raise BlenderConnectionError("Connection not established")
            conn.writer.write(payload)
            await conn.writer.drain()

            raw = await self._read_json_response(conn.reader)
            result = json.loads(raw)
            if result.get("status") == "error":
                raise BlenderError(result.get("message", "unknown error"))
            return result

        except TimeoutError:
            await conn.close()
            raise BlenderTimeoutError(f"Blender command timed out after {self.timeout}s")
        except (ConnectionError, OSError) as exc:
            await conn.close()
            raise BlenderConnectionError(str(exc)) from exc
        finally:
            conn.busy = False

    async def close_all(self) -> None:
        for conn in self._connections:
            await conn.close()
        self._connections.clear()

    # -- internal -----------------------------------------------------------

    async def _read_json_response(self, reader: asyncio.StreamReader) -> str:
        """Read until a complete JSON object is received.

        The blender-mcp addon sends JSON without a trailing newline,
        so we accumulate bytes and try to parse after each chunk.
        """
        buf = b""
        while True:
            chunk = await asyncio.wait_for(reader.read(8192), timeout=self.timeout)
            if not chunk:
                raise BlenderConnectionError("Blender closed the connection")
            buf += chunk
            try:
                json.loads(buf.decode())
                return buf.decode()
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue

    async def _acquire(self) -> _Connection:
        async with self._lock:
            # reuse an idle connected slot
            for conn in self._connections:
                if not conn.busy and conn.connected:
                    conn.busy = True
                    return conn

            # create a new connection to the first reachable host
            for host, port in self.hosts:
                conn = _Connection(host=host, port=port)
                try:
                    await asyncio.wait_for(conn.connect(), timeout=5.0)
                except (TimeoutError, OSError):
                    logger.debug("Blender at %s:%d unreachable", host, port)
                    continue
                conn.busy = True
                self._connections.append(conn)
                return conn

        raise BlenderConnectionError(f"No reachable Blender instances among {self.hosts}")
