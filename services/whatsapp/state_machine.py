# services/whatsapp/state_machine.py — Mandatory Confirmation State Machine
"""
Explicit State Machine governing the lifecycle of WhatsApp message drafts.
Guarantees:
- Strict transitions: IDLE -> DRAFT_CREATED -> AWAITING_CONFIRMATION -> CONFIRMED -> WHATSAPP_DRAFT_OPENED
- Safe cancellation & expiration handling at any stage.
- Zero accidental confirmations (checks unique short-lived draft ID).
- Invalidation on edit: Any modification resets confirmation and forces a new voice readback.
- Never sends automatically — only opens prefilled draft in user's browser after explicit confirmation.
"""
import re
import threading
from datetime import datetime, timezone
from typing import Optional, Tuple

from core.config import Config
from services.whatsapp.models import Contact, DraftStatus, WhatsAppDraft
from services.whatsapp.url_builder import WhatsAppURLBuilder

logger = Config.get_logger(__name__)


class DraftStateError(Exception):
    """Raised when an invalid state transition or expired draft operation is attempted."""
    pass


class WhatsAppDraftStateMachine:
    """
    Thread-safe confirmation state machine for WhatsApp message drafts.
    """

    # Unambiguous affirmative tokens for verbal approval (anchored to prevent false confirmations)
    AFFIRMATIVE_PATTERN = re.compile(
        r"^(?:yes|yep|yeah|sure|confirm|send\s+it|open\s+(?:the\s+)?draft|open\s+it|go\s+ahead|proceed|please\s+do|please\s+open)(?:[\s,]+(?:please|son|thanks|thank\s+you|do\s+it))?[.!?]*$",
        re.IGNORECASE,
    )

    # Unambiguous negative/cancellation tokens
    NEGATIVE_PATTERN = re.compile(
        r"^(?:no|nope|cancel|don'?t\s+send|cancel\s+that|cancel\s+message|cancel\s+draft|stop|nevermind|discard)(?:[\s,]+(?:please|son|thanks|thank\s+you))?[.!?]*$",
        re.IGNORECASE,
    )

    def __init__(self, default_ttl_seconds: int = 60):
        self._default_ttl_seconds = default_ttl_seconds
        self._active_draft: Optional[WhatsAppDraft] = None
        self._lock = threading.RLock()

    @property
    def active_draft(self) -> Optional[WhatsAppDraft]:
        """Return the current active draft, checking for expiration first."""
        with self._lock:
            self._check_expiry_locked()
            return self._active_draft

    def _check_expiry_locked(self):
        """Internal helper to mark draft as EXPIRED if past its expiration timestamp."""
        if self._active_draft and self._active_draft.status in (
            DraftStatus.DRAFT_CREATED,
            DraftStatus.AWAITING_CONFIRMATION,
        ):
            if self._active_draft.is_expired:
                logger.info(f"Draft {self._active_draft.draft_id} expired after {self._default_ttl_seconds}s")
                self._active_draft.status = DraftStatus.EXPIRED

    def create_draft(
        self,
        contact: Contact,
        message_text: str,
        ttl_seconds: Optional[int] = None,
    ) -> Tuple[WhatsAppDraft, str]:
        """
        Create a new draft in AWAITING_CONFIRMATION state and generate verbal confirmation prompt.

        Returns:
            Tuple of (WhatsAppDraft, spoken_prompt_string)
        """
        clean_text = message_text.strip()
        if not clean_text:
            raise ValueError("Draft message text cannot be empty.")

        ttl = ttl_seconds or self._default_ttl_seconds
        now = datetime.now(timezone.utc).timestamp()
        expires_at = now + ttl

        with self._lock:
            # If an existing draft is pending, supersede it
            if self._active_draft and self._active_draft.status == DraftStatus.AWAITING_CONFIRMATION:
                logger.info(f"Superseding previous draft {self._active_draft.draft_id}")
                self._active_draft.status = DraftStatus.CANCELLED

            draft = WhatsAppDraft(
                recipient_name=contact.display_name,
                contact=contact,
                message_text=clean_text,
                status=DraftStatus.AWAITING_CONFIRMATION,
                expires_at=expires_at,
            )
            self._active_draft = draft

            # Mandatory exact readback statement
            prompt = (
                f"I have prepared a WhatsApp message for {contact.display_name}, number {contact.masked_phone}. "
                f"The message is: '{clean_text}'. Should I open this draft?"
            )
            logger.info(f"Draft {draft.draft_id} created for {contact.display_name} ({contact.masked_phone})")
            return draft, prompt

    def confirm_draft(self, draft_id: str) -> Tuple[WhatsAppDraft, str]:
        """
        Confirm the pending draft by exact ID and construct the official Click to Chat URL.

        Returns:
            Tuple of (WhatsAppDraft, click_to_chat_url)
        """
        with self._lock:
            self._check_expiry_locked()

            if not self._active_draft:
                raise DraftStateError("No active message draft is waiting for confirmation.")

            if self._active_draft.draft_id != draft_id:
                raise DraftStateError(
                    f"Draft ID mismatch: received '{draft_id}', active is '{self._active_draft.draft_id}'."
                )

            if self._active_draft.status == DraftStatus.EXPIRED:
                raise DraftStateError("The pending WhatsApp draft has expired. Please request the message again.")

            if self._active_draft.status != DraftStatus.AWAITING_CONFIRMATION:
                raise DraftStateError(
                    f"Draft cannot be confirmed from status '{self._active_draft.status.value}'. Must be AWAITING_CONFIRMATION."
                )

            # Generate and validate URL
            url = WhatsAppURLBuilder.build_click_to_chat_url(
                phone_number=self._active_draft.contact.phone_number,
                message=self._active_draft.message_text,
            )

            self._active_draft.status = DraftStatus.CONFIRMED
            self._active_draft.confirmed_at = datetime.now(timezone.utc).timestamp()
            self._active_draft.click_to_chat_url = url

            logger.info(f"Draft {draft_id} explicitly confirmed for {self._active_draft.contact.display_name}")
            return self._active_draft, url

    def mark_draft_opened(self, draft_id: str) -> str:
        """
        Mark a confirmed draft as WHATSAPP_DRAFT_OPENED after browser launch.
        Returns the mandatory completion spoken message.
        """
        with self._lock:
            if not self._active_draft or self._active_draft.draft_id != draft_id:
                raise DraftStateError("Draft ID mismatch or no active draft.")

            if self._active_draft.status != DraftStatus.CONFIRMED:
                raise DraftStateError(f"Cannot open draft from status {self._active_draft.status.value}")

            self._active_draft.status = DraftStatus.WHATSAPP_DRAFT_OPENED
            self._active_draft.opened_at = datetime.now(timezone.utc).timestamp()

            spoken = (
                f"The WhatsApp draft is open for {self._active_draft.contact.display_name}. "
                "Review the recipient and message, then press Send in WhatsApp."
            )
            return spoken

    def cancel_draft(self, draft_id: Optional[str] = None) -> Tuple[WhatsAppDraft, str]:
        """
        Cancel the active draft and clear confirmation.
        """
        with self._lock:
            if not self._active_draft:
                raise DraftStateError("There is no active message draft to cancel.")

            if draft_id and self._active_draft.draft_id != draft_id:
                raise DraftStateError("Draft ID does not match active draft.")

            name = self._active_draft.contact.display_name
            self._active_draft.status = DraftStatus.CANCELLED
            spoken = f"WhatsApp message draft for {name} has been cancelled."
            logger.info(f"Draft {self._active_draft.draft_id} for {name} cancelled.")
            return self._active_draft, spoken

    def edit_draft(
        self,
        draft_id: Optional[str] = None,
        new_message: Optional[str] = None,
        new_contact: Optional[Contact] = None,
    ) -> Tuple[WhatsAppDraft, str]:
        """
        Edit the message text or recipient of a draft.
        Invalidates any prior confirmation and resets expiration.
        """
        with self._lock:
            self._check_expiry_locked()

            if not self._active_draft:
                raise DraftStateError("There is no active message draft to edit.")

            if draft_id and self._active_draft.draft_id != draft_id:
                raise DraftStateError("Draft ID does not match active draft.")

            if self._active_draft.status in (DraftStatus.CONFIRMED, DraftStatus.WHATSAPP_DRAFT_OPENED):
                raise DraftStateError("Cannot edit a draft that has already been confirmed or opened.")

            if new_message and new_message.strip():
                self._active_draft.message_text = new_message.strip()

            if new_contact:
                self._active_draft.contact = new_contact
                self._active_draft.recipient_name = new_contact.display_name

            # Invalidate any prior confirmation and reset timer
            now = datetime.now(timezone.utc).timestamp()
            self._active_draft.status = DraftStatus.AWAITING_CONFIRMATION
            self._active_draft.expires_at = now + self._default_ttl_seconds

            spoken = (
                f"I have updated the WhatsApp message for {self._active_draft.contact.display_name}, "
                f"number {self._active_draft.contact.masked_phone}. The new message is: "
                f"'{self._active_draft.message_text}'. Should I open this draft?"
            )
            return self._active_draft, spoken

    def evaluate_verbal_confirmation(self, speech_text: str) -> str:
        """
        Evaluate user speech input while awaiting confirmation.

        Returns one of:
            - 'AFFIRMATIVE': User gave unambiguous approval ('yes', 'confirm', 'send it').
            - 'NEGATIVE': User explicitly cancelled ('no', 'cancel that', 'don't send').
            - 'UNCLEAR': Ambiguous or general statement. Requires clarification.
        """
        clean = speech_text.strip().lower()

        if self.AFFIRMATIVE_PATTERN.search(clean):
            return "AFFIRMATIVE"
        elif self.NEGATIVE_PATTERN.search(clean):
            return "NEGATIVE"
        else:
            return "UNCLEAR"
