# ipc/server.py — WebSocket IPC Server for Godot 3D Frontend
"""
Asynchronous WebSocket server connecting Python AI backend to Godot HUD frontend.
Runs on localhost:8765 with zero latency.
"""
import asyncio
import threading
import json
import logging
import psutil
from typing import Callable, Any
import websockets
from websockets.server import WebSocketServerProtocol

from ipc.protocol import IPCMessage, EventType, VisualState
from core.config import Config

logger = Config.get_logger(__name__)


class SONIPCServer:
    """
    WebSocket IPC Bridge connecting SON Python backend to Godot frontend.
    """

    _instance = None
    _singleton_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._singleton_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, host: str = "127.0.0.1", port: int = 8765):
        if getattr(self, "_initialized", False):
            return

        self.host = host
        self.port = port
        self._clients: set[WebSocketServerProtocol] = set()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._server = None
        self._thread: threading.Thread | None = None
        self._running = False
        self._inbound_handlers: dict[str, list[Callable[[dict[str, Any]], None]]] = {}
        self._initialized = True

    def register_handler(self, event_name: str, handler: Callable[[dict[str, Any]], None]):
        """Register a callback for messages coming from Godot frontend."""
        if event_name not in self._inbound_handlers:
            self._inbound_handlers[event_name] = []
        self._inbound_handlers[event_name].append(handler)

    def start(self):
        """Start the WebSocket server in a background event loop thread."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="son-ipc-server")
        self._thread.start()
        logger.info(f"SON IPC WebSocket Server started on ws://{self.host}:{self.port}")

    def stop(self):
        """Stop the WebSocket server."""
        self._running = False
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._main_server())

    async def _main_server(self):
        async with websockets.serve(self._ws_handler, self.host, self.port):
            # Start background telemetry broadcast task
            asyncio.create_task(self._telemetry_broadcast_loop())
            while self._running:
                await asyncio.sleep(0.5)

    async def _ws_handler(self, websocket: WebSocketServerProtocol):
        self._clients.add(websocket)
        logger.info(f"Godot Frontend connected: {websocket.remote_address}")

        # Send initial greeting state
        init_msg = IPCMessage(
            event=EventType.STATE_CHANGE.value,
            data={"state": VisualState.IDLE.value, "label": "SYSTEM ONLINE"}
        )
        await websocket.send(init_msg.to_json())

        try:
            async for raw_msg in websocket:
                try:
                    msg = IPCMessage.from_json(raw_msg)
                    handlers = self._inbound_handlers.get(msg.event, [])
                    for handler in handlers:
                        try:
                            handler(msg.data)
                        except Exception as ex:
                            logger.error(f"Error executing IPC handler for {msg.event}: {ex}")
                except Exception as e:
                    logger.error(f"Failed to parse inbound IPC message: {e}")
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self._clients.discard(websocket)
            logger.info("Godot Frontend disconnected.")

    def broadcast(self, event: str, data: dict[str, Any]):
        """Thread-safe event broadcast to all connected Godot frontends."""
        if not self._running or not self._loop or not self._loop.is_running():
            return

        msg = IPCMessage(event=event, data=data)
        payload = msg.to_json()

        def _send_all():
            for client in list(self._clients):
                asyncio.create_task(client.send(payload))

        self._loop.call_soon_threadsafe(_send_all)

    # ── High-Level Event Broadcasters ────────────────────────────

    def send_state_change(self, state: VisualState | str, label: str = "", intensity: float = 1.0):
        state_str = state.value if isinstance(state, VisualState) else str(state)
        self.broadcast(EventType.STATE_CHANGE.value, {
            "state": state_str,
            "label": label,
            "intensity": intensity,
        })

    def send_audio_level(self, amplitude: float, waveform: list[float] | None = None):
        self.broadcast(EventType.AUDIO_WAVEFORM.value, {
            "amplitude": amplitude,
            "waveform": waveform or [],
        })

    def send_thought_pipeline(self, stage: int, step_name: str, description: str):
        self.broadcast(EventType.THOUGHT_PIPELINE.value, {
            "stage": stage,
            "step_name": step_name,
            "description": description,
        })

    def send_subtitle(self, speaker: str, text: str):
        self.broadcast(EventType.SUBTITLE.value, {
            "speaker": speaker,
            "text": text,
        })

    def send_perception(self, camera_active: bool, person_count: int, face_name: str = "None", confidence: float = 0.0):
        self.broadcast(EventType.PERCEPTION_UPDATE.value, {
            "camera_active": camera_active,
            "person_count": person_count,
            "face_name": face_name,
            "confidence": confidence,
        })

    def send_sound_cue(self, cue_name: str):
        self.broadcast(EventType.SOUND_CUE.value, {
            "cue": cue_name
        })

    # ── Background Telemetry Broadcast ───────────────────────────

    async def _telemetry_broadcast_loop(self):
        """Periodically broadcast CPU, GPU, VRAM, and RAM metrics."""
        while self._running:
            if self._clients:
                try:
                    cpu = psutil.cpu_percent(interval=None)
                    ram = psutil.virtual_memory()
                    ram_gb = ram.used / (1024 ** 3)
                    gpu_util = 4.0
                    vram_gb = 4.5

                    try:
                        import pynvml
                        pynvml.nvmlInit()
                        h = pynvml.nvmlDeviceGetHandleByIndex(0)
                        gpu_util = float(pynvml.nvmlDeviceGetUtilizationRates(h).gpu)
                        vram_gb = float(pynvml.nvmlDeviceGetMemoryInfo(h).used / (1024 ** 3))
                    except Exception:
                        pass

                    telemetry_msg = IPCMessage(
                        event=EventType.SYSTEM_TELEMETRY.value,
                        data={
                            "cpu": cpu,
                            "gpu": gpu_util,
                            "vram_gb": vram_gb,
                            "vram_total": 8.0,
                            "ram_gb": ram_gb,
                            "ram_total": 16.0,
                        }
                    )
                    payload = telemetry_msg.to_json()
                    for c in list(self._clients):
                        await c.send(payload)
                except Exception:
                    pass
            await asyncio.sleep(1.0)
