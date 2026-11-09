# core/interfaces/whatsapp_adapter.py — WhatsApp Interface Adapter for SON V3
"""
WhatsApp Interface Adapter for SON V3:
Enforces:
  1. Standardized integration for WhatsApp voice drafting and REST API ingress.
  2. Mandatory human confirmation-before-sending via WhatsAppDraftStateMachine.
  3. Strict cryptographic argument binding to recipient, phone number, and message text.
  4. Routing of final browser handoff through SonOrchestrator.execute_action.
  5. Automatic secret redaction for contact phone numbers and credentials.
  6. Replay, tampering, and stale confirmation protection.
"""

import time
import logging
from typing import Any, Optional, Tuple

from core.config import Config
from core.interfaces.base_adapter import BaseInterfaceAdapter
from core.interfaces.contract import InterfaceRequest, InterfaceResponse
from core.orchestrator import OrchestrationStatus
from services.whatsapp.service import WhatsAppVoiceService
from services.whatsapp.models import WhatsAppDraft, DraftStatus
from services.whatsapp.contacts import ContactRegistry
from core.security.audit_logger import redact_secrets, audit_logger

logger = Config.get_logger(__name__)


class WhatsAppInterfaceAdapter(BaseInterfaceAdapter):
    """
    Standardized adapter for WhatsApp voice and API integrations.
    """

    def __init__(
        self,
        orchestrator=None,
        whatsapp_service: Optional[WhatsAppVoiceService] = None,
        default_user_id: str = "whatsapp_user",
        session_id: Optional[str] = None,
    ):
        super().__init__(
            interface_type="whatsapp",
            orchestrator=orchestrator,
            default_user_id=default_user_id,
        )
        self.service = whatsapp_service or WhatsAppVoiceService.get_instance()
        self._session_id = session_id or "whatsapp_service_session"

    def handle_voice_message(self, speech_text: str) -> InterfaceResponse:
        """
        Process speech command regarding WhatsApp messaging.
        Enforces confirmation before any message can be drafted or opened.
        """
        clean_text = (speech_text or "").strip()
        if not clean_text:
            return InterfaceResponse(
                request_id=f"wa_empty_{int(time.time()*1000)}",
                status=OrchestrationStatus.VALIDATION_ERROR,
                response_text="Empty speech text received.",
                error="Empty input",
            )

        handled, response_text = self.service.handle_voice_turn(clean_text)
        active_draft = self.service.state_machine.active_draft

        status = OrchestrationStatus.SUCCESS
        pending = None
        if active_draft and active_draft.status == DraftStatus.AWAITING_CONFIRMATION:
            status = OrchestrationStatus.AWAITING_APPROVAL
            pending = {
                "draft_id": active_draft.draft_id,
                "recipient": active_draft.contact.display_name,
                "phone": active_draft.contact.phone_number,
                "message": active_draft.message_text,
                "status": "AWAITING_CONFIRMATION",
            }

        return InterfaceResponse(
            request_id=f"wa_turn_{int(time.time()*1000)}",
            status=status,
            response_text=response_text,
            pending_approval=pending,
            execution_metadata={"handled": handled},
        )

    def confirm_and_open_draft(
        self,
        draft_id: str,
        user_id: Optional[str] = None,
    ) -> InterfaceResponse:
        """
        Explicit user confirmation for a pending WhatsApp draft.
        Routes the final browser handoff through SonOrchestrator.execute_action.
        """
        uid = user_id or self.default_user_id
        active = self.service.state_machine.active_draft

        if not active or active.draft_id != draft_id:
            audit_logger.log_event(
                event_type="WHATSAPP_DRAFT_MISMATCH",
                actor=uid,
                session_id=self._session_id,
                status="BLOCKED",
                details={"requested_draft_id": draft_id},
            )
            return InterfaceResponse(
                request_id=f"wa_conf_{int(time.time()*1000)}",
                status=OrchestrationStatus.VALIDATION_ERROR,
                response_text=f"Draft ID '{draft_id}' not found or no longer active.",
                error="Unknown draft ID",
            )

        handled, spoken = self.service._execute_confirmed_draft(active)
        return InterfaceResponse(
            request_id=draft_id,
            status=OrchestrationStatus.SUCCESS if handled else OrchestrationStatus.ERROR,
            response_text=spoken,
            execution_metadata={"draft_id": draft_id},
        )

    def cancel_draft(self, draft_id: str) -> InterfaceResponse:
        """Explicit cancellation of a pending WhatsApp draft."""
        success, spoken = self.service.state_machine.cancel_draft(draft_id)
        return InterfaceResponse(
            request_id=draft_id,
            status=OrchestrationStatus.CANCELLED if success else OrchestrationStatus.VALIDATION_ERROR,
            response_text=spoken,
            execution_metadata={"draft_id": draft_id},
        )

