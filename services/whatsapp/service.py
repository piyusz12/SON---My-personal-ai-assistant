# services/whatsapp/service.py — High-Level WhatsApp Voice Service Orchestrator
"""
Orchestrates the entire voice-controlled WhatsApp messaging workflow:
1. Speech intent parsing
2. Local deterministic contact resolution with ambiguity detection
3. Confirmation state machine management
4. Secure official Click to Chat URL construction
5. Default browser handoff without automated Send clicks or DOM tampering
"""
import logging
from typing import Optional, Tuple

from core.config import Config
from services.whatsapp.browser_launcher import BrowserLauncher
from services.whatsapp.contacts import ContactRegistry, ContactResolution
from services.whatsapp.intent_parser import WhatsAppIntentParser
from services.whatsapp.models import (
    Contact,
    DraftStatus,
    WhatsAppDraft,
    WhatsAppIntentType,
    WhatsAppVoiceCommand,
)
from services.whatsapp.state_machine import DraftStateError, WhatsAppDraftStateMachine
from services.whatsapp.url_builder import WhatsAppURLBuilder

logger = Config.get_logger(__name__)


class WhatsAppVoiceService:
    """
    Unified coordinator for voice-controlled WhatsApp drafting in SON V3.
    """

    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(
        self,
        contacts_registry: Optional[ContactRegistry] = None,
        state_machine: Optional[WhatsAppDraftStateMachine] = None,
    ):
        self.contacts = contacts_registry or ContactRegistry()
        self.state_machine = state_machine or WhatsAppDraftStateMachine()

    def handle_voice_turn(self, speech_text: str, brain_client=None) -> Tuple[bool, str]:
        """
        Main entry point for voice turns related to WhatsApp.

        Returns:
            Tuple of (handled_bool, response_spoken_text)
        """
        clean = speech_text.strip()
        active = self.state_machine.active_draft

        # ── CASE 1: Currently Awaiting Confirmation ───────────────────────────
        if active and active.status == DraftStatus.AWAITING_CONFIRMATION:
            # Check confirmation or cancellation first
            eval_result = self.state_machine.evaluate_verbal_confirmation(clean)

            if eval_result == "AFFIRMATIVE":
                return self._execute_confirmed_draft(active)

            elif eval_result == "NEGATIVE":
                _, spoken = self.state_machine.cancel_draft(active.draft_id)
                return True, spoken

            # Check if user requested an edit while awaiting confirmation
            command = WhatsAppIntentParser.parse(clean, brain_client=brain_client)
            if command.intent == WhatsAppIntentType.EDIT_PENDING_DRAFT:
                return self._handle_edit(active, command)
            elif command.intent == WhatsAppIntentType.CANCEL_PENDING_DRAFT:
                _, spoken = self.state_machine.cancel_draft(active.draft_id)
                return True, spoken

            # If user started a completely new draft request, supersede previous
            if command.intent == WhatsAppIntentType.DRAFT_WHATSAPP_MESSAGE:
                return self._handle_new_draft(command)

            # Otherwise, speech was unclear / general conversation
            clarification = (
                f"I'm still waiting to confirm the WhatsApp draft for {active.contact.display_name}. "
                "Should I open this draft? Please say 'yes' to open, or 'cancel' to discard."
            )
            return True, clarification

        # ── CASE 2: General Command Parsing ───────────────────────────────────
        command = WhatsAppIntentParser.parse(clean, brain_client=brain_client)

        if command.intent == WhatsAppIntentType.DRAFT_WHATSAPP_MESSAGE:
            return self._handle_new_draft(command)

        elif command.intent == WhatsAppIntentType.CANCEL_PENDING_DRAFT:
            if active and active.status == DraftStatus.AWAITING_CONFIRMATION:
                _, spoken = self.state_machine.cancel_draft(active.draft_id)
                return True, spoken
            return True, "There is no pending WhatsApp message draft to cancel."

        elif command.intent == WhatsAppIntentType.EDIT_PENDING_DRAFT:
            if active and active.status == DraftStatus.AWAITING_CONFIRMATION:
                return self._handle_edit(active, command)
            return True, "There is no active WhatsApp draft to edit. You can say: 'send Rahul a WhatsApp message saying I am on my way'."

        elif command.intent == WhatsAppIntentType.HELP:
            help_text = (
                "To send a WhatsApp message, say: 'SON, send Rahul a WhatsApp message saying I am on my way'. "
                "I will verify the contact, read the message back for your verbal confirmation, and open the draft in WhatsApp Web."
            )
            return True, help_text

        return False, ""

    def _handle_new_draft(self, command: WhatsAppVoiceCommand) -> Tuple[bool, str]:
        """Process intent to draft a new WhatsApp message."""
        if not command.recipient_name or not command.message_text:
            return True, "Please specify both the recipient name and the message you'd like to send."

        # 1. Resolve contact deterministically
        resolution = self.contacts.resolve_contact(command.recipient_name)

        if resolution.status == "NOT_FOUND":
            return True, resolution.message
        elif resolution.status == "AMBIGUOUS":
            return True, resolution.message

        contact = resolution.contact
        assert contact is not None

        # 2. Create draft in AWAITING_CONFIRMATION state
        try:
            _, prompt = self.state_machine.create_draft(
                contact=contact,
                message_text=command.message_text,
            )
            return True, prompt
        except Exception as e:
            logger.error(f"Failed to create draft: {e}", exc_info=True)
            return True, f"Error preparing message: {e}"

    def _execute_confirmed_draft(self, draft: WhatsAppDraft) -> Tuple[bool, str]:
        """Execute explicit confirmation and handoff to default browser through secure orchestrator."""
        try:
            confirmed_draft, url = self.state_machine.confirm_draft(draft.draft_id)
            from core.security.context import create_trusted_context
            from core.orchestrator import orchestrator as global_orch

            wa_ctx = create_trusted_context(
                user_id="primary_user",
                interface_type="whatsapp",
                session_id=f"wa_draft_{draft.draft_id}",
            )
            act_res = global_orch.execute_action(
                tool_name="open_whatsapp_draft",
                arguments={"url": url},
                context=wa_ctx,
                tool_func=BrowserLauncher.open_draft_url,
            )
            if not act_res.success:
                return True, f"Could not launch browser: {act_res.output}"

            spoken = self.state_machine.mark_draft_opened(confirmed_draft.draft_id)
            return True, spoken
        except DraftStateError as de:
            return True, str(de)
        except Exception as e:
            logger.error(f"Error opening confirmed draft: {e}", exc_info=True)
            return True, f"An unexpected error occurred while opening WhatsApp: {e}"

    def _handle_edit(self, active: WhatsAppDraft, command: WhatsAppVoiceCommand) -> Tuple[bool, str]:
        """Handle modification of text or recipient of active draft."""
        new_contact = None
        if command.new_recipient_name:
            res = self.contacts.resolve_contact(command.new_recipient_name)
            if res.status != "MATCHED":
                return True, res.message
            new_contact = res.contact

        try:
            _, prompt = self.state_machine.edit_draft(
                draft_id=active.draft_id,
                new_message=command.new_message_text,
                new_contact=new_contact,
            )
            return True, prompt
        except Exception as e:
            return True, f"Could not update draft: {e}"
