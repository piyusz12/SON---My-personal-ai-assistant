# tests/execution/test_tier1_system.py — Tests for Tier 1 System Telemetry & Controls
import time
import pytest
from core.execution.tier1_native.system import NativeSystemManager


@pytest.fixture
def sys_mgr():
    return NativeSystemManager(cache_ttl_seconds=1.0)


def test_get_system_telemetry(sys_mgr):
    telemetry = sys_mgr.get_system_telemetry(force_refresh=True)
    assert "cpu" in telemetry
    assert "memory" in telemetry
    assert "gpu" in telemetry
    assert "disk" in telemetry
    assert "battery" in telemetry
    assert "network" in telemetry

    # Verify memory
    assert telemetry["memory"]["total_gb"] > 0
    assert 0 <= telemetry["memory"]["percent"] <= 100


def test_telemetry_caching(sys_mgr):
    t1 = sys_mgr.get_system_telemetry(force_refresh=True)
    t2 = sys_mgr.get_system_telemetry(force_refresh=False)
    assert t1["timestamp"] == t2["timestamp"]

    # Sleep past cache TTL
    time.sleep(1.1)
    t3 = sys_mgr.get_system_telemetry(force_refresh=False)
    assert t3["timestamp"] > t1["timestamp"]


def test_get_cpu_info(sys_mgr):
    info = sys_mgr.get_cpu_info()
    assert "utilization_percent" in info
    assert "cores_logical" in info
    assert info["cores_logical"] > 0


def test_get_battery_info(sys_mgr):
    bat = sys_mgr.get_battery_info()
    assert "has_battery" in bat
    assert isinstance(bat["has_battery"], bool)


def test_get_disk_info(sys_mgr):
    disk = sys_mgr.get_disk_info("C:\\")
    assert disk["total_gb"] > 0
    assert 0 <= disk["percent"] <= 100
