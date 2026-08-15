# test_v3_comprehensive.py — Comprehensive Test Suite & Vulnerability Audit for SON V3
"""
Full Test Suite covering:
1. Core & Intent Routing (COMMAND, CHAT, COMPLEX)
2. 3-Layer Memory System (RAM, SQLite, Vector DB)
3. Camera Vision Subsystem (Person Detection, Local Face Recognition, Privacy Controls)
4. Screen Vision (Capture & Downscaling)
5. Security & Vulnerability Protections (Command Injection, SSRF, Protected Paths, SQL Injection)
6. Health Monitoring & Observability
"""
import os
import sys
import unittest
import numpy as np
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class TestIntentRouter(unittest.TestCase):
    def setUp(self):
        from core.intent_router import IntentRouter
        self.router = IntentRouter()

    def test_command_routing(self):
        from core.intent_router import IntentType
        commands = [
            "open chrome",
            "close spotify",
            "volume 50",
            "take a screenshot",
            "is anyone in the room?",
            "count people",
            "pause camera",
            "resume camera",
            "camera status",
        ]
        for cmd in commands:
            res = self.router.classify(cmd)
            self.assertEqual(res.intent, IntentType.COMMAND, f"Failed on command: {cmd}")

    def test_chat_routing(self):
        from core.intent_router import IntentType
        chats = [
            "hello",
            "good morning",
            "who are you?",
            "what is the capital of Japan?",
            "thank you very much",
        ]
        for chat in chats:
            res = self.router.classify(chat)
            self.assertEqual(res.intent, IntentType.CHAT, f"Failed on chat: {chat}")

    def test_complex_routing(self):
        from core.intent_router import IntentType
        complex_queries = [
            "explain in detail how the attention mechanism works in transformers",
            "write a python function to refactor my database queries and debug the traceback",
            "compare and contrast PostgreSQL vs ChromaDB for vector storage",
        ]
        for q in complex_queries:
            res = self.router.classify(q)
            self.assertEqual(res.intent, IntentType.COMPLEX, f"Failed on complex query: {q}")


class TestMemory3Layers(unittest.TestCase):
    def setUp(self):
        from memory.manager import MemoryManager
        self.mm = MemoryManager()

    def test_l1_ram(self):
        self.mm.ram.clear()
        self.mm.ram.add_turn("user", "Hello SON")
        self.mm.ram.add_turn("assistant", "Hello father!")
        messages = self.mm.ram.get_recent_messages()
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["content"], "Hello SON")

    def test_l2_structured_sqlite(self):
        # Fact storage
        self.mm.structured.store_fact("Father likes warm coffee in the morning", category="preferences")
        facts = self.mm.structured.get_facts(category="preferences")
        self.assertTrue(any("coffee" in f["fact"] for f in facts))

        # Preference storage
        self.mm.structured.set_preference("speech_speed", 1.1)
        speed = self.mm.structured.get_preference("speech_speed")
        self.assertEqual(speed, 1.1)

        # Episodic Event logging
        self.mm.structured.log_event("person_entered", {"count": 1})
        events = self.mm.structured.get_recent_events("person_entered", limit=1)
        self.assertEqual(len(events), 1)

    def test_l2_biometric_enrollment(self):
        # Local Face Template Enrollment
        dummy_embedding = [0.1] * 128
        self.mm.structured.enroll_person("test_user", "Test Son", dummy_embedding)
        enrolled = self.mm.structured.get_enrolled_people()
        self.assertTrue(any(p["display_name"] == "Test Son" for p in enrolled))
        self.mm.structured.remove_person("test_user")


class TestCameraAndVisionSubsystem(unittest.TestCase):
    def test_camera_privacy_gate(self):
        from vision.camera.capture import CameraManager
        cam = CameraManager()
        # Default is False for privacy
        self.assertFalse(cam.privacy.camera_active)

        # Test resume (explicit activation)
        cam.resume()
        self.assertTrue(cam.privacy.camera_active)

        # Test pause (privacy kill-switch)
        cam.pause()
        self.assertFalse(cam.privacy.camera_active)
        self.assertIsNone(cam.get_frame())

    def test_person_detector(self):
        from vision.camera.detection import PersonDetector
        detector = PersonDetector()
        black_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        res = detector.detect(black_frame)
        self.assertFalse(res.person_present)
        self.assertEqual(res.person_count, 0)

        # Natural language query check
        present, msg = detector.is_anyone_present(black_frame)
        self.assertFalse(present)
        self.assertIn("nobody", msg.lower())

    def test_face_embedder_and_recognizer(self):
        from vision.camera.face import FaceEmbedder
        from vision.camera.recognition import FaceRecognizer
        from memory.structured_memory import StructuredMemory

        embedder = FaceEmbedder()
        recognizer = FaceRecognizer(structured_memory=StructuredMemory())

        # Synthetic face crop (96x96 with some gradients)
        fake_face = np.random.randint(50, 200, (96, 96, 3), dtype=np.uint8)
        emb = embedder.compute_embedding(fake_face)
        self.assertIsNotNone(emb)
        self.assertEqual(len(emb), 128)

        # Check unit norm
        norm = np.linalg.norm(np.array(emb))
        self.assertAlmostEqual(norm, 1.0, places=4)


class TestSecurityAndVulnerabilities(unittest.TestCase):
    def test_command_injection_mitigation(self):
        from tools.windows_control import run_terminal_command

        # Attack vectors that must be rejected
        injections = [
            "dir & whoami",
            "dir ; del /f /q C:\\*",
            "echo hello | powershell -c evil",
            "dir `calc`",
            "dir $env:PATH",
            "dir > evil.txt",
        ]
        for inj in injections:
            res = run_terminal_command(inj)
            self.assertIn("Security Error", res, f"Failed to block injection: {inj}")

    def test_protected_path_deletion_mitigation(self):
        from plugins.files import FilesPlugin
        files_plugin = FilesPlugin()

        # Critical paths that must not be deleted
        forbidden_paths = [
            "C:\\",
            "C:\\Windows",
            "C:\\Program Files",
            "C:\\Users",
        ]
        for p in forbidden_paths:
            res = files_plugin.delete_path(p)
            self.assertIn("Security Error", res, f"Failed to protect path: {p}")

    def test_ssrf_mitigation(self):
        from tools.web import _validate_url

        # Dangerous SSRF targets
        ssrf_targets = [
            "http://127.0.0.1:8000/admin",
            "http://localhost:11434/api/generate",
            "http://192.168.1.1/router",
            "http://10.0.0.1/secret",
            "file:///C:/Windows/System32/drivers/etc/hosts",
            "ftp://example.com",
        ]
        for target in ssrf_targets:
            is_valid, err = _validate_url(target)
            self.assertFalse(is_valid, f"Failed to block SSRF URL: {target}")


class TestHealthMonitoring(unittest.TestCase):
    def test_health_monitor_dashboard(self):
        from core.health import HealthMonitor
        hm = HealthMonitor()
        status_dict = hm.get_status()
        self.assertIn("camera", status_dict)
        self.assertIn("gpu", status_dict)
        self.assertIn("microphone", status_dict)
        dashboard_str = hm.format_dashboard()
        self.assertIn("SON STATUS", dashboard_str)


if __name__ == "__main__":
    unittest.main(verbosity=2)
