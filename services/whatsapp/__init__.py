# services/whatsapp/__init__.py — Production WhatsApp Voice-Controlled Messaging for SON V3
"""
Voice-Controlled WhatsApp Message-Drafting Integration:
- Local Contact Resolution with Ambiguity Detection & E.164 normalization
- Mandatory Confirmation State Machine (IDLE -> DRAFT_CREATED -> AWAITING_CONFIRMATION -> CONFIRMED -> WHATSAPP_DRAFT_OPENED)
- Official WhatsApp Click to Chat URL builder (https://wa.me/PHONE?text=ENCODED)
- Desktop browser integration without Send-button automation or DOM injection
- Local FastAPI backend service on 127.0.0.1
"""
from services.whatsapp.models import (
    Contact,
    WhatsAppDraft,
    DraftStatus,
    WhatsAppIntentType,
    WhatsAppVoiceCommand,
)
from services.whatsapp.contacts import ContactRegistry
from services.whatsapp.state_machine import WhatsAppDraftStateMachine
from services.whatsapp.url_builder import WhatsAppURLBuilder
from services.whatsapp.browser_launcher import BrowserLauncher
from services.whatsapp.intent_parser import WhatsAppIntentParser
from services.whatsapp.service import WhatsAppVoiceService

__all__ = [
    "Contact",
    "WhatsAppDraft",
    "DraftStatus",
    "WhatsAppIntentType",
    "WhatsAppVoiceCommand",
    "ContactRegistry",
    "WhatsAppDraftStateMachine",
    "WhatsAppURLBuilder",
    "BrowserLauncher",
    "WhatsAppIntentParser",
    "WhatsAppVoiceService",
]
