"""
Tests for SON V3 Code Review Remediation (Waves 1, 2, 3).
Validates fixes for findings CR-01 through CR-12.
"""
import os
import unittest
from unittest.mock import MagicMock, patch
import pytest

from core.config import SecurityLevel
from core.security.policy import RiskTier, classify_risk
from core.security.policy_engine import SecurityPolicyEngine
from core.security.tool_registry import create_default_defensive_registry
from core.security.approval_manager import ApprovalManager, ApprovalStatus
from core.security.context import SecurityContext
from core.orchestrator import SonOrchestrator
from memory.structured_memory import StructuredMemory
from plugins.weather import WeatherPlugin
from plugins.windows import WindowsPlugin


# ==============================================================================
# WAVE 1 TESTS (CR-01, CR-02, CR-03, CR-04, CR-07)
# ==============================================================================

class TestWave1Remediation(unittest.TestCase):
    """Regression tests for Wave 1 critical bugs and security findings."""

    def test_cr01_cr07_structured_memory_id_and_delete_by_id(self):
        """CR-01 & CR-07: get_facts must include 'id' and delete_fact_by_id must delete by PK."""
        import tempfile
        import sqlite3
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
            db_path = tf.name

        try:
            mem = StructuredMemory(db_path=db_path)
            mem.store_fact("User enjoys programming in Python", category="preferences", confidence=0.95)
            mem.store_fact("User prefers dark mode UI", category="preferences", confidence=0.88)

            facts = mem.get_facts(category="preferences")
            self.assertEqual(len(facts), 2)
            # CR-01: 'id' must be present in every fact dict and be an int > 0
            for f in facts:
                self.assertIn("id", f)
                self.assertIsInstance(f["id"], int)
                self.assertGreater(f["id"], 0)

            # CR-07: delete_fact_by_id must delete by primary key
            target_id = facts[0]["id"]
            self.assertTrue(mem.delete_fact_by_id(target_id))

            remaining = mem.get_facts()
            self.assertEqual(len(remaining), 1)
            self.assertNotEqual(remaining[0]["id"], target_id)

            # Deleting non-existent id should return False
            self.assertFalse(mem.delete_fact_by_id(999999))
        finally:
            if os.path.exists(db_path):
                os.remove(db_path)

    def test_cr07_protocol_dispatcher_memory_delete(self):
        """CR-07: ProtocolDispatcher.handle_memory_delete must use public delete_fact_by_id."""
        from services.ipc.protocol_dispatcher import ProtocolDispatcher
        mock_mem = MagicMock()
        mock_mem.delete_fact_by_id.return_value = True

        dispatcher = ProtocolDispatcher(structured_memory=mock_mem)
        res = dispatcher.handle_memory_delete({"id": 42}, "req_1")

        self.assertEqual(res["status"], "SUCCESS")
        mock_mem.delete_fact_by_id.assert_called_once_with(42)

        # Invalid ID should return ERROR
        res_invalid = dispatcher.handle_memory_delete({"id": "not_an_int"}, "req_2")
        self.assertEqual(res_invalid["status"], "ERROR")

    def test_cr02_weather_url_encoding(self):
        """CR-02: Weather API queries with spaces/special characters must be safely URL-encoded."""
        plugin = WeatherPlugin()
        plugin.initialize()

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b"Sunny +22C"
            mock_resp.__enter__.return_value = mock_resp
            mock_urlopen.return_value = mock_resp

            # City with spaces
            result = plugin.get_weather("New York")
            self.assertIn("Sunny", result)
            called_req = mock_urlopen.call_args[0][0]
            self.assertEqual(called_req.full_url, "https://wttr.in/New%20York?format=4")

            # Unicode city name
            plugin.get_weather("M\u00fcnchen")
            called_req_unicode = mock_urlopen.call_args[0][0]
            self.assertEqual(called_req_unicode.full_url, "https://wttr.in/M%C3%BCnchen?format=4")

            # Forecast test
            mock_resp.read.return_value = b'{"current_condition": [{"temp_C": "25", "FeelsLikeC": "26", "weatherDesc": [{"value": "Clear"}], "humidity": "45"}], "nearest_area": [{"areaName": [{"value": "San Francisco"}]}]}'
            forecast = plugin.get_forecast("San Francisco")
            self.assertIn("San Francisco", forecast)
            called_req_forecast = mock_urlopen.call_args[0][0]
            self.assertEqual(called_req_forecast.full_url, "https://wttr.in/San%20Francisco?format=j1")

    def test_cr03_discord_wildcard_resolution(self):
        """CR-03: Discord wildcard paths (app-*) must resolve safely via glob."""
        plugin = WindowsPlugin()
        plugin.initialize()

        fake_discord_path = "C:\\Users\\fakeuser\\AppData\\Local\\Discord\\app-1.0.9100\\Discord.exe"

        with patch("pathlib.Path.home") as mock_home, \
             patch("glob.glob") as mock_glob, \
             patch("subprocess.Popen") as mock_popen:

            mock_home.return_value.name = "fakeuser"
            mock_glob.return_value = [
                "C:\\Users\\fakeuser\\AppData\\Local\\Discord\\app-1.0.9099\\Discord.exe",
                fake_discord_path,
            ]

            res = plugin.open_application("discord")
            self.assertEqual(res, "Opened 'discord'.")
            mock_glob.assert_called_once()
            # Must launch the latest matched version
            mock_popen.assert_called_once_with([fake_discord_path], shell=False)

    def test_cr04_shutdown_restart_security_boundary(self):
        """
        CR-04: shutdown_pc and restart_pc must be classified HIGH risk,
        registered in defensive tool registry, and denied without cryptographic approval token.
        """
        # 1. Risk classification check
        self.assertEqual(classify_risk("shutdown_pc", {"delay_seconds": 30}), RiskTier.HIGH)
        self.assertEqual(classify_risk("restart_pc", {"delay_seconds": 30}), RiskTier.HIGH)

        # 2. Defensive Tool Registry check
        registry = create_default_defensive_registry()
        self.assertIsNotNone(registry.get_tool("shutdown_pc"))
        self.assertIsNotNone(registry.get_tool("restart_pc"))
        self.assertEqual(registry.get_tool("shutdown_pc").risk_tier, RiskTier.HIGH)
        self.assertEqual(registry.get_tool("restart_pc").risk_tier, RiskTier.HIGH)

        # 3. SecurityPolicyEngine evaluation without approval
        policy = SecurityPolicyEngine()
        decision_shut = policy.evaluate_action(
            tool_name="shutdown_pc",
            arguments={"delay_seconds": 30},
            user_id="usr_primary",
            session_id="ses_test",
        )
        self.assertFalse(decision_shut.allowed)
        self.assertTrue(decision_shut.requires_approval)
        self.assertIsNotNone(decision_shut.approval_id)

        decision_restart = policy.evaluate_action(
            tool_name="restart_pc",
            arguments={"delay_seconds": 30},
            user_id="usr_primary",
            session_id="ses_test",
        )
        self.assertFalse(decision_restart.allowed)
        self.assertTrue(decision_restart.requires_approval)
        self.assertIsNotNone(decision_restart.approval_id)

        # 4. Direct invocation via SonOrchestrator without approval token must fail closed
        orch = SonOrchestrator(policy_engine_instance=policy, tool_registry=registry)
        ctx = SecurityContext(user_id="usr_primary", session_id="ses_test", interface="desktop")
        act_res = orch.execute_action("shutdown_pc", {"delay_seconds": 30}, context=ctx)
        self.assertFalse(act_res.success)
        self.assertTrue(act_res.requires_approval)
        self.assertIn("requires approval", act_res.output)

        act_restart = orch.execute_action("restart_pc", {"delay_seconds": 30}, context=ctx)
        self.assertFalse(act_restart.success)
        self.assertTrue(act_restart.requires_approval)
        self.assertIn("requires approval", act_restart.output)


# ==============================================================================
# WAVE 2 TESTS (CR-05, CR-08, CR-09)
# ==============================================================================

class TestWave2Remediation(unittest.TestCase):
    """Regression tests for Wave 2 concurrency, error handling, and performance."""

    def test_cr05_desktop_operation_serialization(self):
        """CR-05: Window and input mutating operations must be in WINDOWS_DESKTOP_TOOLS."""
        from core.action_executor import WINDOWS_DESKTOP_TOOLS, ActionExecutor

        required_tools = {
            "open_application",
            "close_application",
            "set_volume",
            "set_brightness",
            "shutdown_pc",
            "restart_pc",
            "take_screenshot",
            "type_message",
            "minimize_window",
            "maximize_window",
            "snap_window",
        }
        for tool in required_tools:
            self.assertIn(tool, WINDOWS_DESKTOP_TOOLS, f"Tool '{tool}' must be in WINDOWS_DESKTOP_TOOLS")

        executor = ActionExecutor()
        self.assertTrue(hasattr(executor, "_windows_lock"))

    def test_cr08_nonblocking_cpu_sampling(self):
        """CR-08: CPU sampling in system info must use interval=None to prevent thread blocking."""
        import time
        from plugins.windows import WindowsPlugin
        from tools import windows_control

        plugin = WindowsPlugin()
        plugin.initialize()

        fake_gpu = {
            "gpu_name": "NVIDIA GeForce RTX 4060 Laptop GPU",
            "gpu_util": 10.0,
            "vram_used_mb": 1500.0,
            "vram_total_mb": 8188.0,
        }

        with patch("psutil.cpu_percent", return_value=12.5) as mock_cpu, \
             patch("core.gpu_manager.GPUManager") as mock_gm:
            mock_gm.return_value.get_metrics.return_value = fake_gpu
            t0 = time.perf_counter()
            info_plugin = plugin.get_system_info()
            elapsed_plugin = time.perf_counter() - t0

            mock_cpu.assert_called_with(interval=None)
            self.assertLess(elapsed_plugin, 0.2)
            self.assertIn("12.5%", info_plugin)

        with patch("psutil.cpu_percent", return_value=18.0) as mock_cpu_ctrl, \
             patch("core.gpu_manager.GPUManager") as mock_gm_ctrl:
            mock_gm_ctrl.return_value.get_metrics.return_value = fake_gpu
            t0 = time.perf_counter()
            info_ctrl = windows_control.get_system_info()
            elapsed_ctrl = time.perf_counter() - t0

            mock_cpu_ctrl.assert_called_with(interval=None)
            self.assertLess(elapsed_ctrl, 0.2)
            self.assertIn("18.0%", info_ctrl)

    def test_cr09_git_commit_robustness(self):
        """CR-09: git_commit_changes must validate message and check subprocess exit codes."""
        from plugins.vscode import VSCodePlugin
        import tempfile
        from pathlib import Path

        plugin = VSCodePlugin()

        # 1. Empty message rejection
        res_empty = plugin.git_commit_changes("some_path", "")
        self.assertIn("Git commit failed: Commit message cannot be empty", res_empty)

        res_spaces = plugin.git_commit_changes("some_path", "   ")
        self.assertIn("Git commit failed: Commit message cannot be empty", res_spaces)

        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)
            (p / ".git").mkdir()

            # 2. Non-zero exit code reporting
            with patch("subprocess.run") as mock_run:
                mock_add = MagicMock(returncode=0)
                mock_commit_fail = MagicMock(
                    returncode=1,
                    stdout="",
                    stderr="error: nothing to commit, working tree clean",
                )
                mock_run.side_effect = [mock_add, mock_commit_fail]

                res_fail = plugin.git_commit_changes(str(p), "fix bug")
                self.assertIn("Git commit failed:", res_fail)
                self.assertIn("nothing to commit", res_fail)

            # 3. Successful commit reporting
            with patch("subprocess.run") as mock_run:
                mock_add = MagicMock(returncode=0)
                mock_commit_ok = MagicMock(
                    returncode=0,
                    stdout="[main 1234abc] fix bug",
                    stderr="",
                )
                mock_run.side_effect = [mock_add, mock_commit_ok]

                res_ok = plugin.git_commit_changes(str(p), "fix bug")
                self.assertIn("Git commit completed:", res_ok)
                self.assertIn("1234abc", res_ok)


# ==============================================================================
# WAVE 3 TESTS (CR-06, CR-10)
# ==============================================================================

class TestWave3Remediation(unittest.TestCase):
    """Regression tests for Wave 3 IPC, telemetry, and reliability."""

    def test_cr06_hardware_telemetry_gpu_manager(self):
        """CR-06: Telemetry handler must query GPUManager and convert MB to bytes correctly."""
        from services.ipc.protocol_dispatcher import ProtocolDispatcher

        fake_metrics = {
            "gpu_name": "NVIDIA GeForce RTX 4060 Laptop GPU",
            "gpu_util": 27.5,
            "vram_used_mb": 2048.0,
            "vram_total_mb": 8188.0,
            "gpu_temp_c": 55.0,
        }

        with patch("core.gpu_manager.GPUManager.get_metrics", return_value=fake_metrics):
            dispatcher = ProtocolDispatcher()
            resp = dispatcher.handle_hardware_telemetry({}, "req_telem_1")

            self.assertEqual(resp["status"], "SUCCESS")
            self.assertEqual(resp["gpu_percent"], 27.5)
            # 2048 MB -> bytes
            self.assertEqual(resp["vram_used_bytes"], 2048 * 1024 * 1024)
            # 8188 MB -> bytes
            self.assertEqual(resp["vram_total_bytes"], 8188 * 1024 * 1024)

    def test_cr10_named_pipe_handle_atomic_single_close(self):
        """CR-10: Closing current pipe handle must be atomic with nullification, preventing double-close."""
        from services.ipc.named_pipe_server import NamedPipeServer

        server = NamedPipeServer(pipe_name="dummy_test_pipe")
        mock_handle = MagicMock()
        server._current_pipe_handle = mock_handle

        close_calls = []

        def fake_close(handle):
            close_calls.append(handle)

        server._close_handle_safe = fake_close

        # Call stop() which claims and closes the handle
        server.stop()
        self.assertEqual(len(close_calls), 1)
        self.assertEqual(close_calls[0], mock_handle)
        self.assertIsNone(server._current_pipe_handle)

        # A concurrent or subsequent stop() or finally block must see None and not close again
        server.stop()
        self.assertEqual(len(close_calls), 1, "Handle must not be closed a second time")


