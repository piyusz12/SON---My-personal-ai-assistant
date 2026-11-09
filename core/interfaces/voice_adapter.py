# core/interfaces/voice_adapter.py — Voice Interface Adapter for SON V3
"""
Voice Interface Adapter for SON V3:
Enforces:
  1. Strict unidirectional voice execution: STT -> VoiceAdapter -> Orchestrator -> TTS.
  2. Speech recognition cannot directly trigger tools or execute system actions.
  3. Session persistence across voice turns.
  4. Non-blocking audio processing with timeout safety.
  5. Verbal communication of pending approvals.
  6. Robust handling of microphone, transcription, and TTS failures.
"""

import time
import logging
from typing import Any, Optional, Tuple, Callable

from core.config import Config
from core.interfaces.base_adapter import BaseInterfaceAdapter
from core.interfaces.contract import InterfaceRequest, InterfaceResponse
from core.orchestrator import OrchestrationStatus
from core.security.context import create_trusted_context
from core.security.audit_logger import audit_logger

logger = Config.get_logger(__name__)


class VoiceInterfaceAdapter(BaseInterfaceAdapter):
    """
    Standardized adapter for voice input/output pipelines.
    """

    def __init__(
        self,
        orchestrator=None,
        tts_engine=None,
        stt_engine=None,
        default_user_id: str = "primary_user",
        session_id: Optional[str] = None,
    ):
        super().__init__(
            interface_type="voice",
            orchestrator=orchestrator,
            default_user_id=default_user_id,
            session_id=session_id,
        )
        self.tts = tts_engine
        self.stt = stt_engine
        if session_id:
            self._session_id = session_id

    def set_session_id(self, session_id: str):
        self._session_id = session_id

    def handle_speech_input(
        self,
        transcribed_text: str,
        conversation_id: Optional[str] = None,
        timeout: float = 60.0,
    ) -> InterfaceResponse:
        """
        Process recognized speech input through the standardized orchestrator contract.
        """
        clean_text = (transcribed_text or "").strip()
        if not clean_text:
            return InterfaceResponse(
                request_id=f"voice_empty_{int(time.time()*1000)}",
                status=OrchestrationStatus.VALIDATION_ERROR,
                response_text="I did not catch that. Please speak again.",
                error="Empty transcription",
            )

        # Build normalized request bound to active voice session
        req = self.normalize_request(
            message=clean_text,
            session_id=self._session_id,
            conversation_id=conversation_id,
            metadata={"source": "microphone_stt"},
        )
        self._session_id = req.session_id

        # Dispatch via base adapter
        response = self.send_request(req, timeout=timeout)

        # Handle speech output via TTS if available
        if self.tts and hasattr(self.tts, "speak") and response.response_text:
            try:
                self.tts.speak(response.response_text)
            except Exception as e:
                logger.error(f"TTS playback failed in voice adapter: {e}")

        return response

    def handle_verbal_approval(
        self,
        approval_id: str,
        verbal_response: str,
    ) -> InterfaceResponse:
        """
        Process verbal confirmation ('yes', 'approve', 'deny', 'no') for a pending action.
        """
        clean = verbal_response.strip().lower()
        is_approved = any(w in clean for w in ("yes", "approve", "confirm", "proceed", "sure", "ok", "go ahead"))
        is_denied = any(w in clean for w in ("no", "deny", "cancel", "stop", "abort", "reject"))

        if not is_approved and not is_denied:
            return InterfaceResponse(
                request_id=f"appr_{int(time.time()*1000)}",
                status=OrchestrationStatus.PENDING_APPROVAL,
                response_text="I couldn't tell if you approved or denied. Please say 'yes' to approve or 'no' to cancel.",
                error="Ambiguous verbal confirmation",
            )

        res = self.handle_approval(
            approval_id=approval_id,
            approved=is_approved,
            session_id=self._session_id,
        )

        if self.tts and hasattr(self.tts, "speak") and res.response_text:
            try:
                self.tts.speak(res.response_text)
            except Exception as e:
                logger.error(f"TTS playback failed in approval resolution: {e}")

        return res
