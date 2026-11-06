# services/whatsapp/models.py — Data Models and Enums for WhatsApp Voice Messaging
"""
Strongly typed Pydantic models and schemas for WhatsApp voice messaging integration.
All models validate input lengths, types, and values to prevent injection and state corruption.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
import uuid
from pydantic import BaseModel, Field, field_validator


class DraftStatus(str, Enum):
    """Explicit Lifecycle states of a WhatsApp message draft."""
    IDLE = "IDLE"
    DRAFT_CREATED = "DRAFT_CREATED"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    CONFIRMED = "CONFIRMED"
    WHATSAPP_DRAFT_OPENED = "WHATSAPP_DRAFT_OPENED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class WhatsAppIntentType(str, Enum):
    """Recognized WhatsApp voice intents."""
    DRAFT_WHATSAPP_MESSAGE = "draft_whatsapp_message"
    CONFIRM_PENDING_DRAFT = "confirm_pending_draft"
    EDIT_PENDING_DRAFT = "edit_pending_draft"
    CANCEL_PENDING_DRAFT = "cancel_pending_draft"
    HELP = "help"
    UNKNOWN = "unknown"


class Contact(BaseModel):
    """Locally stored verified contact."""
    id: str = Field(default_factory=lambda: f"cnt_{uuid.uuid4().hex[:8]}")
    display_name: str = Field(..., min_length=1, max_length=100)
    phone_number: str = Field(..., description="International format digits without leading plus sign (e.g. 919876541234)")
    aliases: List[str] = Field(default_factory=list)
    notes: Optional[str] = Field(default="", max_length=500)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def last_four(self) -> str:
        """Last four digits of phone number for safe voice confirmation readout."""
        digits = "".join(c for c in self.phone_number if c.isdigit())
        return digits[-4:] if len(digits) >= 4 else digits

    @property
    def masked_phone(self) -> str:
        """Masked phone string for safe logging and display."""
        return f"ending {self.last_four}"


class WhatsAppDraft(BaseModel):
    """Expiring, validated pending message draft."""
    draft_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    recipient_name: str = Field(..., min_length=1, max_length=100)
    contact: Contact
    message_text: str = Field(..., min_length=1, max_length=4000)
    status: DraftStatus = Field(default=DraftStatus.DRAFT_CREATED)
    created_at: float = Field(default_factory=lambda: datetime.now(timezone.utc).timestamp())
    expires_at: float
    confirmed_at: Optional[float] = None
    opened_at: Optional[float] = None
    click_to_chat_url: Optional[str] = None

    @property
    def is_expired(self) -> bool:
        """Check if current UTC time has passed expiration timestamp."""
        now = datetime.now(timezone.utc).timestamp()
        return now >= self.expires_at

    @property
    def remaining_seconds(self) -> int:
        """Remaining seconds before draft expires."""
        now = datetime.now(timezone.utc).timestamp()
        diff = self.expires_at - now
        return max(0, int(diff))


class WhatsAppVoiceCommand(BaseModel):
    """Structured extraction of a voice command."""
    intent: WhatsAppIntentType
    recipient_name: Optional[str] = None
    message_text: Optional[str] = None
    new_message_text: Optional[str] = None
    new_recipient_name: Optional[str] = None
    raw_transcript: str = ""
    confidence: float = 1.0


# ── REST API Request / Response Schemas ──────────────────────────────────────

class DraftRequest(BaseModel):
    recipient: str = Field(..., min_length=1, max_length=100)
    message: str = Field(..., min_length=1, max_length=4000)


class DraftResponse(BaseModel):
    draft_id: str
    recipient: str
    phone_masked: str
    message: str
    status: DraftStatus
    expires_in_seconds: int
    spoken_prompt: str


class ConfirmRequest(BaseModel):
    draft_id: str


class ConfirmResponse(BaseModel):
    draft_id: str
    status: DraftStatus
    click_to_chat_url: str
    spoken_status: str


class CancelRequest(BaseModel):
    draft_id: str


class CancelResponse(BaseModel):
    draft_id: str
    status: DraftStatus
    message: str


class EditRequest(BaseModel):
    draft_id: str
    new_message: Optional[str] = Field(default=None, max_length=4000)
    new_recipient: Optional[str] = Field(default=None, max_length=100)
