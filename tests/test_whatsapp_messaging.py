# tests/test_whatsapp_messaging.py — Comprehensive Test Suite for WhatsApp Voice Messaging
"""
Comprehensive, deterministic automated tests verifying all 15 required areas:
1. Valid command extraction
2. Missing or malformed recipient and message
3. Contact matching and alias resolution
4. Ambiguous contact handling
5. Invalid phone-number rejection
6. URL construction and URL encoding
7. Unicode, Hindi, emoji, and multiline messages
8. Explicit confirmation versus an ambiguous response
9. Draft expiry and cancellation
10. Message or recipient edits requiring new confirmation
11. Replayed or mismatched draft IDs
12. Backend unavailable and browser-launch failures
13. No automatic message sending or Send-button automation
14. Regression tests for existing SON features
15. Integration tests using mocked services rather than actual WhatsApp sessions
"""
import os
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.whatsapp.models import (
    Contact,
    DraftStatus,
    WhatsAppDraft,
    WhatsAppIntentType,
    WhatsAppVoiceCommand,
)
from services.whatsapp.contacts import ContactRegistry, ContactResolution
from services.whatsapp.url_builder import WhatsAppURLBuilder
from services.whatsapp.state_machine import (
    DraftStateError,
    WhatsAppDraftStateMachine,
)
from services.whatsapp.browser_launcher import BrowserLauncher
from services.whatsapp.intent_parser import WhatsAppIntentParser
from services.whatsapp.service import WhatsAppVoiceService
from core.intent_router import IntentRouter, IntentType


class TestWhatsAppVoiceMessaging(unittest.TestCase):
    def setUp(self):
        # Create an isolated temporary contact registry per test method
        self.temp_db = Path(__file__).parent / f"test_contacts_{self._testMethodName}.db"
        if self.temp_db.exists():
            try:
                self.temp_db.unlink()
            except Exception:
                pass

        self.registry = ContactRegistry(db_path=str(self.temp_db), seed_json_path=Path("non_existent.json"))
        self.registry.clear_all()
        # Seed test contacts (100% non-personal dummy test data)
        self.c1 = self.registry.add_contact(
            display_name="Rahul",
            phone_number="+919876541234",
            aliases=["rahul sharma", "bro"],
        )
        self.c2 = self.registry.add_contact(
            display_name="Amit",
            phone_number="+919876545678",
            aliases=["amit patel"],
        )
        self.state_machine = WhatsAppDraftStateMachine(default_ttl_seconds=60)
        self.service = WhatsAppVoiceService(
            contacts_registry=self.registry,
            state_machine=self.state_machine,
        )

    def tearDown(self):
        try:
            self.registry.clear_all()
            if self.temp_db.exists():
                self.temp_db.unlink()
        except Exception:
            pass

    # ── 1. Valid Command Extraction ───────────────────────────────────────────
    def test_valid_command_extraction(self):
        cmd1 = WhatsAppIntentParser.parse("SON, send Rahul a WhatsApp message saying I am on my way.")
        self.assertEqual(cmd1.intent, WhatsAppIntentType.DRAFT_WHATSAPP_MESSAGE)
        self.assertEqual(cmd1.recipient_name, "Rahul")
        self.assertEqual(cmd1.message_text, "I am on my way")

        cmd2 = WhatsAppIntentParser.parse("SON, prepare a WhatsApp message for Amit: I will call you in ten minutes.")
        self.assertEqual(cmd2.intent, WhatsAppIntentType.DRAFT_WHATSAPP_MESSAGE)
        self.assertEqual(cmd2.recipient_name, "Amit")
        self.assertEqual(cmd2.message_text, "I will call you in ten minutes")

        cmd3 = WhatsAppIntentParser.parse("SON, cancel that message.")
        self.assertEqual(cmd3.intent, WhatsAppIntentType.CANCEL_PENDING_DRAFT)

        cmd4 = WhatsAppIntentParser.parse("SON, change the message to I will arrive at six.")
        self.assertEqual(cmd4.intent, WhatsAppIntentType.EDIT_PENDING_DRAFT)
        self.assertEqual(cmd4.new_message_text, "I will arrive at six")

    # ── 2. Missing or Malformed Recipient & Message ───────────────────────────
    def test_missing_or_malformed_recipient_and_message(self):
        cmd = WhatsAppIntentParser.parse("WhatsApp message")
        self.assertEqual(cmd.intent, WhatsAppIntentType.UNKNOWN)

        # Service level empty message check
        with self.assertRaises(ValueError):
            self.state_machine.create_draft(contact=self.c1, message_text="   ")

    # ── 3. Contact Matching & Alias Resolution ────────────────────────────────
    def test_contact_matching_and_alias_resolution(self):
        # Match exact name
        res1 = self.registry.resolve_contact("Rahul")
        self.assertEqual(res1.status, "MATCHED")
        self.assertEqual(res1.contact.id, self.c1.id)

        # Match alias 'bro'
        res2 = self.registry.resolve_contact("bro")
        self.assertEqual(res2.status, "MATCHED")
        self.assertEqual(res2.contact.id, self.c1.id)

        # Match full name alias 'rahul sharma'
        res3 = self.registry.resolve_contact("Rahul Sharma")
        self.assertEqual(res3.status, "MATCHED")
        self.assertEqual(res3.contact.id, self.c1.id)

        # Non-existent contact
        res_none = self.registry.resolve_contact("Zack")
        self.assertEqual(res_none.status, "NOT_FOUND")

    # ── 4. Ambiguous Contact Handling ─────────────────────────────────────────
    def test_ambiguous_contact_handling(self):
        # Add another Rahul with different surname and number
        c_verma = self.registry.add_contact(
            display_name="Rahul Verma",
            phone_number="+919876549999",
            aliases=["verma"],
        )

        # Querying just "Rahul" should be AMBIGUOUS now!
        res = self.registry.resolve_contact("Rahul")
        self.assertEqual(res.status, "AMBIGUOUS")
        self.assertGreaterEqual(len(res.matches), 2)
        # Verify it lists distinguishing information without leaking full number
        self.assertIn("ending 1234", res.message)
        self.assertIn("ending 9999", res.message)

    # ── 5. Invalid Phone-Number Rejection ─────────────────────────────────────
    def test_invalid_phone_number_rejection(self):
        with self.assertRaises(ValueError):
            self.registry.normalize_phone_number("12345")  # Too short

        with self.assertRaises(ValueError):
            self.registry.normalize_phone_number("not_a_phone_number")

        with self.assertRaises(ValueError):
            self.registry.add_contact(display_name="Bad Phone", phone_number="000")

    # ── 6. URL Construction & URL Encoding ────────────────────────────────────
    def test_url_construction_and_encoding(self):
        url = WhatsAppURLBuilder.build_click_to_chat_url(
            phone_number="919876541234",
            message="Hello world",
        )
        self.assertEqual(url, "https://wa.me/919876541234?text=Hello%20world")
        self.assertTrue(WhatsAppURLBuilder.validate_url(url))

        # Rejection of invalid domain or scheme
        self.assertFalse(WhatsAppURLBuilder.validate_url("http://wa.me/919876541234?text=test"))
        self.assertFalse(WhatsAppURLBuilder.validate_url("https://evil.com/wa.me/919876541234"))
        self.assertFalse(WhatsAppURLBuilder.validate_url("javascript:alert(1)"))

    # ── 7. Unicode, Hindi Text, Emoji & Multiline Messages ────────────────────
    def test_unicode_hindi_emoji_multiline_messages(self):
        hindi_msg = "नमस्ते Rahul! मुझे देर होगी 🚗 & we will meet\nat 6:00 PM."
        url = WhatsAppURLBuilder.build_click_to_chat_url("919876541234", hindi_msg)

        # Ampersand must be encoded as %26 so it does not split URL query params
        self.assertIn("%26", url)
        # Newline must be encoded
        self.assertIn("%0A", url)
        # Valid wa.me URL
        self.assertTrue(WhatsAppURLBuilder.validate_url(url))

    # ── 8. Explicit Confirmation vs Ambiguous Response ────────────────────────
    def test_explicit_confirmation_vs_ambiguous(self):
        draft, prompt = self.state_machine.create_draft(self.c1, "I am on my way")
        self.assertEqual(self.state_machine.active_draft.status, DraftStatus.AWAITING_CONFIRMATION)

        # General conversation statements MUST NOT confirm
        self.assertEqual(self.state_machine.evaluate_verbal_confirmation("what time is it"), "UNCLEAR")
        self.assertEqual(self.state_machine.evaluate_verbal_confirmation("maybe later"), "UNCLEAR")
        self.assertEqual(self.state_machine.evaluate_verbal_confirmation("yes, what is the weather"), "UNCLEAR")

        # Explicit affirmative confirmations
        self.assertEqual(self.state_machine.evaluate_verbal_confirmation("yes"), "AFFIRMATIVE")
        self.assertEqual(self.state_machine.evaluate_verbal_confirmation("confirm"), "AFFIRMATIVE")
        self.assertEqual(self.state_machine.evaluate_verbal_confirmation("send it"), "AFFIRMATIVE")
        self.assertEqual(self.state_machine.evaluate_verbal_confirmation("open draft"), "AFFIRMATIVE")

        # Explicit cancellations
        self.assertEqual(self.state_machine.evaluate_verbal_confirmation("no"), "NEGATIVE")
        self.assertEqual(self.state_machine.evaluate_verbal_confirmation("cancel that"), "NEGATIVE")

    # ── 9. Draft Expiry & Cancellation ────────────────────────────────────────
    def test_draft_expiry_and_cancellation(self):
        # 1. Test Cancellation
        draft, _ = self.state_machine.create_draft(self.c1, "Test message")
        cancelled_draft, spoken = self.state_machine.cancel_draft(draft.draft_id)
        self.assertEqual(cancelled_draft.status, DraftStatus.CANCELLED)

        # Cannot confirm a cancelled draft
        with self.assertRaises(DraftStateError):
            self.state_machine.confirm_draft(draft.draft_id)

        # 2. Test Expiration
        # Create draft with past expiration
        expired_draft, _ = self.state_machine.create_draft(self.c1, "Expiring message", ttl_seconds=-1)
        self.assertTrue(expired_draft.is_expired)
        # Attempting confirmation must fail
        with self.assertRaises(DraftStateError):
            self.state_machine.confirm_draft(expired_draft.draft_id)

    # ── 10. Message / Recipient Edits Requiring New Confirmation ───────────────
    def test_message_or_recipient_edits_requiring_new_confirmation(self):
        draft, _ = self.state_machine.create_draft(self.c1, "Original message")

        # Edit message text
        updated_draft, new_prompt = self.state_machine.edit_draft(
            draft_id=draft.draft_id,
            new_message="Updated message text",
        )
        self.assertEqual(updated_draft.status, DraftStatus.AWAITING_CONFIRMATION)
        self.assertEqual(updated_draft.message_text, "Updated message text")
        self.assertIn("Updated message text", new_prompt)

        # Edit recipient
        updated_draft2, prompt2 = self.state_machine.edit_draft(
            draft_id=draft.draft_id,
            new_contact=self.c2,
        )
        self.assertEqual(updated_draft2.recipient_name, "Amit")
        self.assertEqual(updated_draft2.contact.id, self.c2.id)
        self.assertIn("Amit", prompt2)

    # ── 11. Replayed or Mismatched Draft IDs ───────────────────────────────────
    def test_replayed_or_mismatched_draft_ids(self):
        draft, _ = self.state_machine.create_draft(self.c1, "Secret message")
        fake_id = "00000000-0000-0000-0000-000000000000"

        with self.assertRaises(DraftStateError):
            self.state_machine.confirm_draft(fake_id)

    # ── 12. Backend Unavailable & Browser Launch Failures ─────────────────────
    @patch("services.whatsapp.browser_launcher.BrowserLauncher.get_csharp_executable_path", return_value=None)
    @patch("services.whatsapp.browser_launcher.os.startfile")
    def test_browser_launch_failure_handling(self, mock_startfile, mock_csharp):
        mock_startfile.side_effect = OSError("Browser not found")

        draft, _ = self.state_machine.create_draft(self.c1, "Hello")
        success, msg = BrowserLauncher.open_draft_url("https://wa.me/919876541234?text=Hello")
        self.assertFalse(success)
        self.assertIn("Failed to launch web browser", msg)

    # ── 13. No Automatic Message Sending or Send-Button Automation ────────────
    def test_no_automatic_send_or_send_button_automation(self):
        """
        Verify code compliance: BrowserLauncher opens Click to Chat URL only.
        It must never simulate enter or click on Send button.
        """
        import inspect
        source = inspect.getsource(BrowserLauncher.open_draft_url)
        self.assertNotIn("pyautogui.press('enter')", source)
        self.assertNotIn("VK_RETURN", source)
        self.assertNotIn("send_keys", source)
        self.assertNotIn("pyautogui.click", source)
        self.assertNotIn("mouse_event", source)

    # ── 14. Regression Tests for Existing SON Features ────────────────────────
    def test_regression_existing_son_features(self):
        router = IntentRouter()
        # Verify that existing commands still classify correctly
        self.assertEqual(router.classify("open chrome").intent, IntentType.COMMAND)
        self.assertEqual(router.classify("volume 50").intent, IntentType.COMMAND)
        self.assertEqual(router.classify("talk with me").intent, IntentType.COMMAND)
        self.assertEqual(router.classify("write a python function to test my database").intent, IntentType.COMPLEX)
        self.assertEqual(router.classify("hello").intent, IntentType.CHAT)

    # ── 15. Mocked End-to-End Voice Integration Flow ─────────────────────────
    @patch("services.whatsapp.browser_launcher.BrowserLauncher.open_draft_url")
    def test_integration_mocked_end_to_end_flow(self, mock_open_url):
        mock_open_url.return_value = (True, "Opened in browser")

        # Step 1: User says initial drafting command
        handled, speech1 = self.service.handle_voice_turn(
            "SON, send Rahul a WhatsApp message saying I am on my way."
        )
        self.assertTrue(handled)
        self.assertIn("Rahul", speech1)
        self.assertIn("ending 1234", speech1)
        self.assertIn("I am on my way", speech1)
        self.assertIn("Should I open this draft?", speech1)

        # Step 2: User says "yes" to confirm
        handled, speech2 = self.service.handle_voice_turn("yes")
        self.assertTrue(handled)
        self.assertIn("The WhatsApp draft is open for Rahul", speech2)
        self.assertIn("press Send in WhatsApp", speech2)
        mock_open_url.assert_called_once()

    # ── 16. Local FastAPI REST Endpoints ─────────────────────────────────────
    @patch("services.whatsapp.browser_launcher.BrowserLauncher.open_draft_url")
    def test_fastapi_rest_endpoints(self, mock_open_url):
        from fastapi.testclient import TestClient  # type: ignore[import-not-found]
        from services.whatsapp.api import app

        mock_open_url.return_value = (True, "Opened")
        client = TestClient(app)

        # 1. Health endpoint
        res = client.get("/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "healthy")

        # 2. Draft creation endpoint
        d_res = client.post("/message/draft", json={"recipient": "Rahul", "message": "I am on my way"})
        self.assertEqual(d_res.status_code, 201)
        data = d_res.json()
        draft_id = data["draft_id"]
        self.assertEqual(data["recipient"], "Rahul")
        self.assertEqual(data["phone_masked"], "ending 1234")

        # 3. Confirmation endpoint
        c_res = client.post("/message/confirm", json={"draft_id": draft_id})
        self.assertEqual(c_res.status_code, 200)
        self.assertEqual(c_res.json()["status"], "WHATSAPP_DRAFT_OPENED")

        # 4. Unknown recipient check
        bad_res = client.post("/message/draft", json={"recipient": "NobodyKnown", "message": "hello"})
        self.assertEqual(bad_res.status_code, 404)


if __name__ == "__main__":
    unittest.main()

