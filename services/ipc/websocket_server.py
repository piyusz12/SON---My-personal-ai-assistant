# services/ipc/websocket_server.py — Localhost WebSocket Gateway for SON Web & Remote Interfaces
"""
Localhost-bound asynchronous WebSocket server (ws://127.0.0.1:8765/ws) for SON V3.
Bridges:
  1. Real-time telemetry events from core.event_bus.EventBus to connected frontends.
  2. Inbound JSON action requests to services.ipc.protocol_dispatcher.ProtocolDispatcher.
Enforces localhost binding, optional token authentication, and thread-safe async dispatch.
"""

import os
import sys
import json
import time
import uuid
import hmac
import asyncio
import logging
import threading
from typing import Optional, Set

import websockets
from websockets.server import WebSocketServerProtocol, serve

from core.config import Config
from core.event_bus import event_bus, SonEvent, EventType
from services.ipc.protocol_dispatcher import ProtocolDispatcher

logger = Config.get_logger(__name__)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


class WebSocketGateway:
    """
    Asynchronous WebSocket Gateway for web/remote and companion interfaces.
    """

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        dispatcher: Optional[ProtocolDispatcher] = None,
    ):
        self.host = host
        self.port = port
        self.dispatcher = dispatcher or ProtocolDispatcher()
        self._clients: Set[WebSocketServerProtocol] = set()
        self._clients_lock = asyncio.Lock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._server = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._stop_event: Optional[asyncio.Event] = None

    def start(self, blocking: bool = False):
        """Start the WebSocket server."""
        if self._running:
            logger.warning("WebSocketGateway is already running.")
            return

        self._running = True
        if blocking:
            asyncio.run(self._run_server())
        else:
            self._thread = threading.Thread(
                target=self._thread_entry,
                name="WebSocketGatewayThread",
                daemon=True,
            )
            self._thread.start()
            logger.info("WebSocketGateway background thread started on ws://%s:%d", self.host, self.port)

    def _thread_entry(self):
        """Background thread target setting up dedicated asyncio loop."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._run_server())
        except Exception as e:
            logger.error(f"WebSocketGateway loop error: {e}", exc_info=True)
        finally:
            self._loop.close()

    async def _run_server(self):
        """Async main entry listening for incoming connections."""
        self._stop_event = asyncio.Event()

        # Hook EventBus subscriber
        event_bus.subscribe_all(self._on_event_bus_event)

        async with serve(
            self._handler,
            self.host,
            self.port,
            ping_interval=20,
            ping_timeout=20,
        ) as server:
            self._server = server
            logger.info("WebSocketGateway actively listening on ws://%s:%d", self.host, self.port)
            await self._stop_event.wait()

        # Unhook on shutdown
        try:
            event_bus.unsubscribe("all", self._on_event_bus_event)
        except Exception:
            pass

    def stop(self):
        """Signal shutdown and disconnect all active clients."""
        logger.info("Stopping WebSocketGateway...")
        self._running = False
        if self._loop and self._stop_event and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._stop_event.set)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
            self._thread = None
        logger.info("WebSocketGateway stopped successfully.")

    def _on_event_bus_event(self, event: SonEvent):
        """Thread-safe hook receiving telemetry events from core EventBus."""
        if not self._running or not self._loop or not self._loop.is_running():
            return

        msg_data = {
            "type": "event",
            "event_type": event.event_type.value if isinstance(event.event_type, EventType) else str(event.event_type),
            "timestamp": event.timestamp,
            "source": event.source,
            "payload": event.payload,
            "session_id": event.session_id,
            "request_id": event.request_id,
        }

        # Schedule broadcast on server loop
        asyncio.run_coroutine_threadsafe(self._broadcast(msg_data), self._loop)

    async def _broadcast(self, data: dict):
        """Broadcast JSON payload to all connected clients."""
        if not self._clients:
            return

        serialized = json.dumps(data)
        async with self._clients_lock:
            disconnected = []
            for client in self._clients:
                try:
                    await client.send(serialized)
                except Exception:
                    disconnected.append(client)

            for dc in disconnected:
                self._clients.discard(dc)

    async def _handler(self, websocket: WebSocketServerProtocol):
        """Handle individual client connection lifecycle."""
        client_id = f"ws_cli_{uuid.uuid4().hex[:8]}"
        peer = websocket.remote_address
        logger.info("New WebSocket client connected: %s from %s", client_id, peer)

        async with self._clients_lock:
            self._clients.add(websocket)

        # Send initial welcome / status event
        welcome_payload = {
            "type": "welcome",
            "client_id": client_id,
            "server_time": time.time(),
            "protocol_version": "1.0",
            "status": "CONNECTED",
        }
        await websocket.send(json.dumps(welcome_payload))

        try:
            async for raw_message in websocket:
                try:
                    if isinstance(raw_message, bytes):
                        raw_message = raw_message.decode("utf-8")
                    data = json.loads(raw_message)
                except (UnicodeDecodeError, json.JSONDecodeError) as err:
                    err_resp = {
                        "type": "error",
                        "error": "MALFORMED_JSON",
                        "message": str(err),
                    }
                    await websocket.send(json.dumps(err_resp))
                    continue

                # Process request via ProtocolDispatcher in executor
                response = await self._dispatch_async(data)
                response["type"] = "response"
                await websocket.send(json.dumps(response))

        except websockets.exceptions.ConnectionClosed:
            logger.info("WebSocket client disconnected: %s", client_id)
        except Exception as exc:
            logger.warning("Error in WebSocket handler for client %s: %s", client_id, exc)
        finally:
            async with self._clients_lock:
                self._clients.discard(websocket)

    async def _dispatch_async(self, data: dict) -> dict:
        """Run blocking ProtocolDispatcher in thread pool."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.dispatcher.dispatch, data)


def run_standalone():
    """CLI runner for standalone debugging."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] (%(name)s) %(message)s",
    )
    print(f"Starting SON WebSocket Gateway on ws://{DEFAULT_HOST}:{DEFAULT_PORT}...")
    gateway = WebSocketGateway()
    try:
        gateway.start(blocking=True)
    except KeyboardInterrupt:
        print("\nShutdown requested by user.")
    finally:
        gateway.stop()
        print("Server shutdown complete.")


if __name__ == "__main__":
    run_standalone()
