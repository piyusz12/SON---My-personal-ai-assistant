# tests/test_gpu_cap.py — Unit Tests for 95% GPU Compute & VRAM Cap Enforcement
"""
Validates that SON enforces the strict 95% ceiling on GPU usage:
1. Max GPU compute utilization cap (95%)
2. Max GPU VRAM usage cap (95%)
3. can_allocate() rejects allocations exceeding 95% VRAM or when compute >= 95%
4. reserve_vram() prevents reservations exceeding 95%
5. is_over_cap() detection and throttle_if_over_cap() safety throttling
6. Health monitor status degradation on exceeding 95% cap
"""
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.gpu_manager import GPUManager
from core.health import HealthMonitor, ServiceStatus
import config


class TestGPUCap(unittest.TestCase):
    def setUp(self):
        self.gpu = GPUManager()

    def test_constants_configured_to_95_percent(self):
        """Verify the 95% cap constants in config and GPUManager."""
        self.assertEqual(config.GPU_MAX_UTIL_PERCENT, 95.0)
        self.assertEqual(config.GPU_MAX_VRAM_PERCENT, 95.0)
        self.assertEqual(self.gpu.MAX_GPU_UTIL_PERCENT, 95.0)
        self.assertEqual(self.gpu.MAX_VRAM_PERCENT, 95.0)
        self.assertAlmostEqual(
            self.gpu.max_allowed_vram_mb,
            self.gpu.TOTAL_VRAM_MB * 0.95,
            places=1
        )

    @patch.object(GPUManager, "get_metrics")
    def test_can_allocate_under_95_cap(self, mock_metrics):
        """Allow allocation when total VRAM and compute utilization remain under 95%."""
        mock_metrics.return_value = {
            "gpu_name": "NVIDIA RTX 4060",
            "gpu_util": 50.0,            # well under 95%
            "vram_used_mb": 4000.0,
            "vram_total_mb": 8188.0,     # 95% cap is 7778.6 MB
            "vram_free_mb": 4188.0,
            "gpu_temp_c": 50.0,
            "power_draw_w": 50.0,
        }
        # 4000 + 1000 = 5000 MB <= 7778.6 MB -> Allowed
        self.assertTrue(self.gpu.can_allocate(1000))

    @patch.object(GPUManager, "get_metrics")
    def test_can_allocate_rejects_exceeding_95_vram(self, mock_metrics):
        """Reject allocation when projected VRAM exceeds 95% cap."""
        mock_metrics.return_value = {
            "gpu_name": "NVIDIA RTX 4060",
            "gpu_util": 40.0,
            "vram_used_mb": 7000.0,
            "vram_total_mb": 8188.0,     # 95% cap is 7778.6 MB
            "vram_free_mb": 1188.0,
            "gpu_temp_c": 55.0,
            "power_draw_w": 60.0,
        }
        # 7000 + 1000 = 8000 MB > 7778.6 MB (95%) -> Must be rejected!
        self.assertFalse(self.gpu.can_allocate(1000))

    @patch.object(GPUManager, "get_metrics")
    def test_can_allocate_rejects_when_gpu_util_at_or_above_95(self, mock_metrics):
        """Reject allocation when GPU compute utilization is at or above 95%."""
        mock_metrics.return_value = {
            "gpu_name": "NVIDIA RTX 4060",
            "gpu_util": 96.0,            # Exceeds 95% compute cap!
            "vram_used_mb": 2000.0,
            "vram_total_mb": 8188.0,
            "vram_free_mb": 6188.0,
            "gpu_temp_c": 60.0,
            "power_draw_w": 90.0,
        }
        self.assertFalse(self.gpu.can_allocate(500))

    def test_reserve_vram_exceeding_95_cap_raises_error(self):
        """Attempting to reserve more than 95% of total VRAM must raise MemoryError."""
        max_allowed = self.gpu.TOTAL_VRAM_MB * 0.95
        # Attempt to reserve 8000 MB (> 95% of 8188 MB)
        with self.assertRaises(MemoryError) as ctx:
            with self.gpu.reserve_vram("oversized_model", int(max_allowed + 100)):
                pass
        self.assertIn("95", str(ctx.exception))

    @patch.object(GPUManager, "get_metrics")
    def test_is_over_cap_detection(self, mock_metrics):
        """Test detection of GPU compute or VRAM exceeding 95%."""
        # Case 1: Below 95%
        mock_metrics.return_value = {
            "gpu_util": 80.0,
            "vram_used_mb": 6000.0,
            "vram_total_mb": 8188.0,     # ~73% VRAM
        }
        self.assertFalse(self.gpu.is_over_cap())

        # Case 2: Compute util >= 95%
        mock_metrics.return_value = {
            "gpu_util": 95.5,
            "vram_used_mb": 2000.0,
            "vram_total_mb": 8188.0,
        }
        self.assertTrue(self.gpu.is_over_cap())

        # Case 3: VRAM >= 95%
        mock_metrics.return_value = {
            "gpu_util": 30.0,
            "vram_used_mb": 7800.0,      # > 95% (7778.6 MB)
            "vram_total_mb": 8188.0,
        }
        self.assertTrue(self.gpu.is_over_cap())

    @patch.object(GPUManager, "is_over_cap", side_effect=[True, False])
    def test_throttle_if_over_cap_recovers(self, mock_is_over):
        """Throttle loops until GPU falls below 95% and returns True."""
        result = self.gpu.throttle_if_over_cap(timeout=1.0, check_interval=0.01)
        self.assertTrue(result)
        self.assertEqual(mock_is_over.call_count, 2)

    @patch.object(GPUManager, "is_over_cap", return_value=True)
    def test_throttle_if_over_cap_times_out(self, mock_is_over):
        """Throttle times out if GPU continuously stays above 95%."""
        result = self.gpu.throttle_if_over_cap(timeout=0.1, check_interval=0.02)
        self.assertFalse(result)

    @patch.object(GPUManager, "get_metrics")
    def test_health_monitor_flags_degraded_when_over_95_cap(self, mock_metrics):
        """HealthMonitor reports DEGRADED when GPU utilization exceeds 95%."""
        mock_metrics.return_value = {
            "gpu_name": "NVIDIA RTX 4060",
            "gpu_util": 97.0,            # Over 95%
            "vram_used_mb": 3000.0,
            "vram_total_mb": 8188.0,
            "gpu_temp_c": 60.0,
        }
        hm = HealthMonitor()
        hm._check_gpu()
        gpu_svc = hm.get_status()["gpu"]
        self.assertEqual(gpu_svc["status"], ServiceStatus.DEGRADED.value)
        self.assertIn("95%", gpu_svc["details"])


if __name__ == "__main__":
    unittest.main()
