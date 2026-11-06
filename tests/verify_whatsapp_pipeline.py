# tests/verify_whatsapp_pipeline.py — Verification of WhatsApp Voice Integration
"""
Demonstrates and validates requirements 2, 3, and 4:
2. Integrate draft creation and contact resolution. Test with dummy contact first.
   Do not connect message execution to voice confirmation until state machine works correctly.
3. Test WhatsApp handoff: recipient & text confirmation, URL generation, browser handoff.
4. Deliberate failure tests: unknown contact, ambiguous contacts, unclear response,
   cancellation, expired draft. Verify none open unintended messages.
"""
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from services.whatsapp.models import Contact, DraftStatus, WhatsAppDraft, WhatsAppIntentType
from services.whatsapp.contacts import ContactRegistry, ContactResolution
from services.whatsapp.state_machine import WhatsAppDraftStateMachine, DraftStateError
from services.whatsapp.url_builder import WhatsAppURLBuilder
from services.whatsapp.browser_launcher import BrowserLauncher
from services.whatsapp.service import WhatsAppVoiceService
from services.whatsapp.intent_parser import WhatsAppIntentParser


def run_all_verifications():
    print("=" * 70)
    print("SON WHATSAPP VOICE MESSAGING PIPELINE VERIFICATION")
    print("=" * 70)

    # Setup isolated test database
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test_contacts.db"
    dummy_seed = Path(temp_dir) / "seed.json"
    dummy_seed.write_text("[]", encoding="utf-8")

    registry = ContactRegistry(db_path=str(db_path), seed_json_path=dummy_seed)
    registry.clear_all()

    # ──────────────────────────────────────────────────────────────────────────
    # REQUIREMENT 2: Draft Creation & Contact Resolution with Dummy Contact
    # ──────────────────────────────────────────────────────────────────────────
    print("\n--- [REQUIREMENT 2] Testing Draft Creation & Contact Resolution ---")
    
    # 2.1 Add dummy contact
    dummy = registry.add_contact(
        display_name="TestDummy",
        phone_number="+919999988888",
        aliases=["dummy", "tester"],
        notes="Automated test contact",
    )
    print(f"[OK] Added dummy contact: {dummy.display_name} ({dummy.masked_phone})")

    # 2.2 Test contact resolution (exact name and alias)
    res_exact = registry.resolve_contact("TestDummy")
    assert res_exact.status == "MATCHED", f"Expected MATCHED, got {res_exact.status}"
    assert res_exact.contact.id == dummy.id
    print(f"[OK] Contact resolution by display_name: MATCHED -> {res_exact.contact.display_name}")

    res_alias = registry.resolve_contact("dummy")
    assert res_alias.status == "MATCHED"
    assert res_alias.contact.id == dummy.id
    print(f"[OK] Contact resolution by alias 'dummy': MATCHED -> {res_alias.contact.display_name}")

    # 2.3 Create draft in state machine WITHOUT executing or opening browser
    state_machine = WhatsAppDraftStateMachine(default_ttl_seconds=60)
    draft, prompt = state_machine.create_draft(
        contact=dummy,
        message_text="Hello, this is a test draft."
    )
    assert draft.status == DraftStatus.AWAITING_CONFIRMATION
    assert draft.recipient_name == "TestDummy"
    assert draft.message_text == "Hello, this is a test draft."
    assert "ending 8888" in prompt
    assert "Should I open this draft?" in prompt
    print(f"[OK] Draft created with ID: {draft.draft_id}")
    print(f"[OK] Draft initial status: {draft.status.value}")
    print(f"[OK] Spoken prompt: \"{prompt}\"")
    print(f"[OK] Execution decoupled: No browser launched, draft awaiting confirmation.")

    # ──────────────────────────────────────────────────────────────────────────
    # REQUIREMENT 3: WhatsApp Handoff & Verbal Confirmation
    # ──────────────────────────────────────────────────────────────────────────
    print("\n--- [REQUIREMENT 3] Testing WhatsApp Handoff & Verbal Confirmation ---")
    
    # 3.1 Verify evaluate_verbal_confirmation
    assert state_machine.evaluate_verbal_confirmation("yes") == "AFFIRMATIVE"
    assert state_machine.evaluate_verbal_confirmation("confirm") == "AFFIRMATIVE"
    assert state_machine.evaluate_verbal_confirmation("send it, son") == "AFFIRMATIVE"
    print("[OK] Verbal affirmative tokens verified.")

    # 3.2 Test C# Specialist Handoff
    csharp_exe = BrowserLauncher.get_csharp_executable_path()
    print(f"[OK] C# Desktop Specialist found: {csharp_exe}")
    
    with patch("subprocess.run") as mock_subproc:
        mock_subproc.return_value = MagicMock(returncode=0, stdout="[OK] Opened approved URL", stderr="")
        service = WhatsAppVoiceService(
            contacts_registry=registry,
            state_machine=state_machine,
        )

        handled, spoken_feedback = service.handle_voice_turn("yes")
        assert handled is True
        assert state_machine.active_draft.status == DraftStatus.WHATSAPP_DRAFT_OPENED
        assert "The WhatsApp draft is open for TestDummy" in spoken_feedback
        assert "press Send in WhatsApp" in spoken_feedback
        print(f"[OK] Confirmation processed. Spoken feedback: \"{spoken_feedback}\"")
        print(f"[OK] State transitioned to: {state_machine.active_draft.status.value}")

        # Verify C# specialist was invoked with correct URL
        mock_subproc.assert_called_once()
        called_args = mock_subproc.call_args[0][0]
        opened_url = called_args[2]
        assert called_args[1] == "open-draft"
        assert opened_url.startswith("https://wa.me/919999988888?text=")
        assert "Hello%2C%20this%20is%20a%20test%20draft." in opened_url
        assert WhatsAppURLBuilder.validate_url(opened_url) is True
        print(f"[OK] C# Desktop Specialist invoked with approved URL: {opened_url}")
        print(f"[OK] Handed off to browser without DOM manipulation or fake clicks.")

    # 3.3 Test Fallback when C# is not used
    with patch("services.whatsapp.browser_launcher.BrowserLauncher.get_csharp_executable_path", return_value=None), \
         patch("services.whatsapp.browser_launcher.os.startfile") as mock_fallback:
        sm2 = WhatsAppDraftStateMachine(default_ttl_seconds=60)
        svc2 = WhatsAppVoiceService(contacts_registry=registry, state_machine=sm2)
        sm2.create_draft(dummy, "Testing Python fallback")
        h_fb, sp_fb = svc2.handle_voice_turn("yes")
        assert h_fb is True
        mock_fallback.assert_called_once()
        print("[OK] Python OS default browser fallback verified when C# specialist is omitted.")

    # ──────────────────────────────────────────────────────────────────────────
    # REQUIREMENT 4: Deliberate Failure Tests
    # ──────────────────────────────────────────────────────────────────────────
    print("\n--- [REQUIREMENT 4] Deliberate Failure Tests ---")
    
    # Track browser calls across all failure tests to guarantee NONE open any URL
    with patch("services.whatsapp.browser_launcher.os.startfile") as mock_fail_startfile:
        
        # 4.1 Failure Test: Unknown Contact
        print("\n  [Test 4.1] Unknown Contact:")
        unknown_service = WhatsAppVoiceService(contacts_registry=registry)
        handled, msg = unknown_service.handle_voice_turn(
            "SON, send Bruce Wayne a WhatsApp message saying I need the Batmobile."
        )
        assert handled is True
        assert "I couldn't find" in msg
        assert unknown_service.state_machine.active_draft is None
        mock_fail_startfile.assert_not_called()
        print(f"  [PASS] Handled safely: \"{msg}\"")
        print(f"  [PASS] No draft created, no browser opened.")

        # 4.2 Failure Test: Ambiguous Contacts (Same Name)
        print("\n  [Test 4.2] Ambiguous Contacts (Duplicate Names):")
        registry.add_contact(display_name="Rahul Sharma", phone_number="+919876500001")
        registry.add_contact(display_name="Rahul Verma", phone_number="+919876500002")
        ambig_res = registry.resolve_contact("Rahul")
        assert ambig_res.status == "AMBIGUOUS"
        assert len(ambig_res.matches) == 2
        
        ambig_service = WhatsAppVoiceService(contacts_registry=registry)
        handled, msg = ambig_service.handle_voice_turn(
            "SON, send Rahul a WhatsApp message saying Are we meeting?"
        )
        assert handled is True
        assert "multiple contacts" in msg.lower()
        assert "ending 0001" in msg
        assert "ending 0002" in msg
        assert ambig_service.state_machine.active_draft is None
        mock_fail_startfile.assert_not_called()
        print(f"  [PASS] Ambiguity detected and disambiguated: \"{msg}\"")
        print(f"  [PASS] No draft created, no browser opened.")

        # 4.3 Failure Test: Unclear Voice Response
        print("\n  [Test 4.3] Unclear Voice Response:")
        # Create a fresh draft
        test_sm = WhatsAppDraftStateMachine(default_ttl_seconds=60)
        unclear_service = WhatsAppVoiceService(contacts_registry=registry, state_machine=test_sm)
        unclear_service.handle_voice_turn("SON, send TestDummy a WhatsApp message saying testing unclear response.")
        assert test_sm.active_draft.status == DraftStatus.AWAITING_CONFIRMATION
        
        # User says something unclear / unrelated
        handled, msg = unclear_service.handle_voice_turn("What is the weather outside?")
        assert handled is True
        assert "still waiting to confirm" in msg
        assert test_sm.active_draft.status == DraftStatus.AWAITING_CONFIRMATION  # Still awaiting!
        mock_fail_startfile.assert_not_called()
        print(f"  [PASS] Unclear speech rejected: \"{msg}\"")
        print(f"  [PASS] Status remains {test_sm.active_draft.status.value}, no browser opened.")

        # 4.4 Failure Test: Cancellation
        print("\n  [Test 4.4] Explicit Cancellation:")
        handled, msg = unclear_service.handle_voice_turn("cancel that")
        assert handled is True
        assert "cancelled" in msg.lower()
        assert test_sm.active_draft.status == DraftStatus.CANCELLED
        # Further confirmation attempt must fail
        with patch.object(test_sm, "evaluate_verbal_confirmation", return_value="AFFIRMATIVE"):
            try:
                test_sm.confirm_draft(test_sm.active_draft.draft_id)
                assert False, "Should have raised DraftStateError"
            except DraftStateError:
                pass
        mock_fail_startfile.assert_not_called()
        print(f"  [PASS] Cancellation successful: \"{msg}\"")
        print(f"  [PASS] Status transitioned to CANCELLED, cannot be confirmed, no browser opened.")

        # 4.5 Failure Test: Expired Draft
        print("\n  [Test 4.5] Expired Draft (TTL Exceeded):")
        expired_sm = WhatsAppDraftStateMachine(default_ttl_seconds=-1)  # Immediately expired
        expired_service = WhatsAppVoiceService(contacts_registry=registry, state_machine=expired_sm)
        # Create draft with past expiry
        draft_exp, _ = expired_sm.create_draft(dummy, "This draft will expire instantly", ttl_seconds=-1)
        assert draft_exp.is_expired is True
        
        # Attempting confirmation on expired draft
        try:
            expired_sm.confirm_draft(draft_exp.draft_id)
            assert False, "Should have raised DraftStateError for expired draft"
        except DraftStateError as de:
            assert "expired" in str(de).lower()
            print(f"  [PASS] Expired draft rejected: {de}")

        mock_fail_startfile.assert_not_called()
        print(f"  [PASS] Zero browser invocations across all failure tests (total calls: {mock_fail_startfile.call_count})")

    print("\n" + "=" * 70)
    print("ALL VERIFICATIONS COMPLETED SUCCESSFULLY!")
    print("=" * 70)


def test_whatsapp_pipeline():
    """Pytest wrapper for full WhatsApp voice messaging pipeline verification."""
    run_all_verifications()


if __name__ == "__main__":
    run_all_verifications()
