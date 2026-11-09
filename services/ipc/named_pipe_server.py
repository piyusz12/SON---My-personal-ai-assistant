# services/ipc/named_pipe_server.py — Windows Named Pipe Server for SON Desktop
r"""
Windows Named Pipe Server for SON Desktop IPC.
Listens on `\\.\pipe\son_desktop_ipc`.
Enforces 4-byte big-endian length-prefixed framing with UTF-8 JSON payloads.
Runs on a background thread with clean shutdown and reconnection support.
"""

import os
import sys
import time
import json
import struct
import threading
import logging
from typing import Optional, Callable

from core.config import Config
from services.ipc.protocol_dispatcher import ProtocolDispatcher

logger = Config.get_logger(__name__)

PIPE_NAME = r"\\.\pipe\son_desktop_ipc"
BUFFER_SIZE = 65536


class NamedPipeServer:
    """
    Windows Named Pipe server providing high-performance local IPC
    to the C# WPF desktop frontend.
    """

    def __init__(
        self,
        pipe_name: str = PIPE_NAME,
        dispatcher: Optional[ProtocolDispatcher] = None,
    ):
        self.pipe_name = pipe_name
        self.dispatcher = dispatcher or ProtocolDispatcher()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._current_pipe_handle = None
        self._lock = threading.Lock()

    def start(self, blocking: bool = False):
        """Start the named pipe server."""
        if self._running:
            logger.warning("NamedPipeServer is already running.")
            return

        self._running = True
        if blocking:
            self._server_loop()
        else:
            self._thread = threading.Thread(target=self._server_loop, daemon=True, name="NamedPipeServerThread")
            self._thread.start()
            logger.info("NamedPipeServer started in background on %s", self.pipe_name)

    def _close_handle_safe(self, handle):
        """Safely disconnect and close a Windows named pipe handle."""
        if handle is None:
            return
        try:
            import win32pipe
            win32pipe.DisconnectNamedPipe(handle)
        except Exception:
            pass
        try:
            import win32file
            win32file.CloseHandle(handle)
        except Exception:
            pass

    def stop(self):
        """Signal the server to stop and close open handles."""
        logger.info("Stopping NamedPipeServer on %s...", self.pipe_name)
        self._running = False

        handle_to_close = None
        with self._lock:
            if self._current_pipe_handle is not None:
                handle_to_close = self._current_pipe_handle
                self._current_pipe_handle = None

        if handle_to_close is not None:
            self._close_handle_safe(handle_to_close)

        if self._thread and self._thread.is_alive():
            # Connect a dummy client to unblock ConnectNamedPipe if waiting
            try:
                self._wake_pipe()
            except Exception:
                pass
            self._thread.join(timeout=2.0)
            self._thread = None

        logger.info("NamedPipeServer stopped.")

    def _wake_pipe(self):
        """Briefly open pipe to unblock any pending ConnectNamedPipe call."""
        try:
            import win32file
            handle = win32file.CreateFile(
                self.pipe_name,
                win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                0,
                None,
                win32file.OPEN_EXISTING,
                0,
                None,
            )
            win32file.CloseHandle(handle)
        except Exception:
            pass

    def _read_exact(self, pipe_handle, n: int) -> bytes:
        """Read exactly n bytes from the pipe handle, handling chunking."""
        import win32file
        buf = bytearray()
        while len(buf) < n and self._running:
            remaining = n - len(buf)
            hr, chunk = win32file.ReadFile(pipe_handle, remaining)
            if not chunk:
                raise EOFError("Client closed connection")
            buf.extend(chunk)
        return bytes(buf)

    def _send_message(self, pipe_handle, data: dict):
        """Send a length-prefixed JSON message over the pipe."""
        import win32file
        payload_bytes = json.dumps(data).encode("utf-8")
        header = struct.pack(">I", len(payload_bytes))
        win32file.WriteFile(pipe_handle, header + payload_bytes)

    def _serve_client(self, pipe_handle):
        """Read and dispatch messages for a connected client session."""
        import pywintypes
        import winerror

        logger.info("Client connected to named pipe %s", self.pipe_name)
        while self._running:
            try:
                # 1. Read 4-byte length header
                header = self._read_exact(pipe_handle, 4)
                if len(header) < 4:
                    break

                (length,) = struct.unpack(">I", header)
                if length <= 0 or length > 10 * 1024 * 1024:  # 10MB safety cap
                    logger.error("Invalid message length received: %d bytes. Closing connection.", length)
                    break

                # 2. Read full payload
                payload_bytes = self._read_exact(pipe_handle, length)
                if len(payload_bytes) < length:
                    break

                # 3. Decode & Parse JSON
                try:
                    raw_msg = json.loads(payload_bytes.decode("utf-8"))
                except json.JSONDecodeError as jde:
                    logger.error("Failed to parse incoming JSON: %s", jde)
                    self._send_message(pipe_handle, {
                        "protocol_version": "1.0",
                        "message_type": "RESPONSE",
                        "error": "JSON parse error",
                        "payload": {"status": "ERROR", "message": "Malformed JSON"},
                    })
                    continue

                # 4. Dispatch to protocol dispatcher
                response = self.dispatcher.dispatch(raw_msg)

                # 5. Send length-prefixed response
                self._send_message(pipe_handle, response)

            except (EOFError, ConnectionResetError):
                logger.info("Client disconnected normally.")
                break
            except pywintypes.error as we:
                if we.winerror in (winerror.ERROR_BROKEN_PIPE, winerror.ERROR_NO_DATA, winerror.ERROR_PIPE_NOT_CONNECTED):
                    logger.info("Client disconnected (WinError %d).", we.winerror)
                else:
                    logger.warning("Pipe I/O error: %s", we)
                break
            except Exception as exc:
                logger.exception("Unexpected error in pipe server loop: %s", exc)
                break

    def _server_loop(self):
        """Main listening loop creating pipe instances and waiting for clients."""
        import win32pipe
        import win32file
        import pywintypes
        import winerror

        logger.info("NamedPipeServer listening on %s", self.pipe_name)

        while self._running:
            pipe_handle = None
            try:
                pipe_handle = win32pipe.CreateNamedPipe(
                    self.pipe_name,
                    win32pipe.PIPE_ACCESS_DUPLEX,
                    win32pipe.PIPE_TYPE_BYTE | win32pipe.PIPE_READMODE_BYTE | win32pipe.PIPE_WAIT,
                    win32pipe.PIPE_UNLIMITED_INSTANCES,
                    BUFFER_SIZE,
                    BUFFER_SIZE,
                    0,
                    None,
                )

                with self._lock:
                    self._current_pipe_handle = pipe_handle

                # Block until a client connects
                hr = win32pipe.ConnectNamedPipe(pipe_handle, None)
                if not self._running:
                    break

                # Handle connected client
                self._serve_client(pipe_handle)

            except pywintypes.error as we:
                if we.winerror == winerror.ERROR_PIPE_CONNECTED:
                    # Client connected before ConnectNamedPipe was called
                    self._serve_client(pipe_handle)
                elif not self._running:
                    break
                else:
                    logger.warning("Named pipe error in server loop: %s", we)
                    time.sleep(0.1)
            except Exception as e:
                if not self._running:
                    break
                logger.exception("Unexpected error in server loop: %s", e)
                time.sleep(0.1)
            finally:
                handle_to_close = None
                with self._lock:
                    if self._current_pipe_handle == pipe_handle:
                        handle_to_close = pipe_handle
                        self._current_pipe_handle = None

                # Only close if stop() hasn't already claimed and closed it
                if handle_to_close is not None:
                    self._close_handle_safe(handle_to_close)


def run_standalone():
    """Entry point for running the named pipe server as a standalone daemon."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] (%(name)s) %(message)s",
    )
    print(f"Starting SON Desktop Named Pipe Server on {PIPE_NAME}...")
    server = NamedPipeServer()
    try:
        server.start(blocking=True)
    except KeyboardInterrupt:
        print("\nShutdown requested by user.")
    finally:
        server.stop()
        print("Server shutdown complete.")


if __name__ == "__main__":
    run_standalone()
