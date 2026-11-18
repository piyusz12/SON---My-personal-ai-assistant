# tests/test_websocket_server.py — Automated Test Suite for SON WebSocket Gateway
import json
import time
import asyncio
import pytest
import websockets

from core.event_bus import event_bus, EventType
from services.ipc.websocket_server import WebSocketGateway

TEST_PORT = 8788


@pytest.fixture
def ws_server():
    gateway = WebSocketGateway(host="127.0.0.1", port=TEST_PORT)
    gateway.start(blocking=False)
    # Give server brief moment to bind
    time.sleep(0.3)
    yield gateway
    gateway.stop()
    time.sleep(0.2)


@pytest.mark.asyncio
async def test_websocket_welcome_and_ping(ws_server):
    uri = f"ws://127.0.0.1:{TEST_PORT}"
    async with websockets.connect(uri) as ws:
        # 1. Expect welcome message
        welcome_raw = await asyncio.wait_for(ws.recv(), timeout=3.0)
        welcome = json.loads(welcome_raw)
        assert welcome.get("type") == "welcome"
        assert welcome.get("status") == "CONNECTED"
        assert "client_id" in welcome

        # 2. Send ping action
        ping_req = {
            "action": "ping",
            "request_id": "test_req_ping",
            "payload": {},
        }
        await ws.send(json.dumps(ping_req))
        resp_raw = await asyncio.wait_for(ws.recv(), timeout=3.0)
        resp = json.loads(resp_raw)
        assert resp.get("type") == "response"
        assert resp.get("action") == "ping"
        assert resp.get("payload", {}).get("status") == "PONG"


@pytest.mark.asyncio
async def test_websocket_handshake(ws_server):
    uri = f"ws://127.0.0.1:{TEST_PORT}"
    async with websockets.connect(uri) as ws:
        await ws.recv()  # Consume welcome

        handshake_req = {
            "action": "handshake",
            "payload": {
                "client_version": "3.0.0",
                "client_type": "desktop_mini",
                "requested_user_id": "usr_primary",
            },
        }
        await ws.send(json.dumps(handshake_req))
        resp_raw = await asyncio.wait_for(ws.recv(), timeout=3.0)
        resp = json.loads(resp_raw)
        assert resp.get("type") == "response"
        assert resp.get("action") == "handshake"
        assert resp.get("payload", {}).get("status") == "AUTHENTICATED"
        assert resp.get("payload", {}).get("user_id") == "usr_primary"


@pytest.mark.asyncio
async def test_websocket_event_broadcasting(ws_server):
    uri = f"ws://127.0.0.1:{TEST_PORT}"
    async with websockets.connect(uri) as ws:
        await ws.recv()  # Consume welcome

        # Publish an event on event_bus
        event_bus.publish(
            EventType.LISTENING,
            payload={"audio_energy": 0.75, "active": True},
            source="audio_engine",
        )

        # Receive broadcasted event
        ev_raw = await asyncio.wait_for(ws.recv(), timeout=3.0)
        ev = json.loads(ev_raw)
        assert ev.get("type") == "event"
        assert ev.get("event_type") == "listening"
        assert ev.get("payload", {}).get("audio_energy") == 0.75
