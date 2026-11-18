# tests/execution/test_tier1_windows.py — Tests for Tier 1 Window Management
import pytest
from core.execution.tier1_native.windows import NativeWindowManager


@pytest.fixture
def win_mgr():
    return NativeWindowManager()


def test_list_windows(win_mgr):
    res = win_mgr.list_windows()
    assert res["success"] is True
    assert "count" in res
    assert isinstance(res["windows"], list)
    if res["windows"]:
        w = res["windows"][0]
        assert "title" in w
        assert "hwnd" in w
        assert "pid" in w


def test_get_active_window(win_mgr):
    res = win_mgr.get_active_window()
    assert "success" in res
    if res["success"]:
        assert "hwnd" in res
        assert res["hwnd"] != 0


def test_find_window_nonexistent(win_mgr):
    hwnd = win_mgr.find_window("NonExistentWindow_TotallyFake_99999")
    assert hwnd is None


def test_snap_window_invalid_position(win_mgr):
    active = win_mgr.get_active_window()
    if active["success"]:
        res = win_mgr.snap_window(active["hwnd"], position="diagonal_skew")
        assert res["success"] is False
        assert "Unsupported snap position" in res["error"]


def test_window_exists_check(win_mgr):
    assert win_mgr.window_exists("Def_Not_Existing_999") is False
