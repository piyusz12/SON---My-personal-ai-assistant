# services/whatsapp/intent_parser.py — Structured Voice Intent Parser for WhatsApp
"""
Extracts strongly typed WhatsApp voice intents from raw speech transcripts.
Intents supported:
- draft_whatsapp_message
- confirm_pending_draft
- edit_pending_draft
- cancel_pending_draft
- help

Security & Untrusted Input Protections:
- All speech transcripts and LLM responses are treated as untrusted input.
- Bounded text lengths (recipient <= 100 chars, message <= 4000 chars).
- Never infers contacts or invents message bodies silently.
- Strict schema validation via WhatsAppVoiceCommand model.
"""
import json
import logging
import re
from typing import Optional

from core.config import Config
from services.whatsapp.models import WhatsAppIntentType, WhatsAppVoiceCommand

logger = Config.get_logger(__name__)


class WhatsAppIntentParser:
    """
    Parses voice recognition transcripts into structured WhatsAppVoiceCommand objects.
    Combines sub-millisecond regex parsing with optional structured LLM extraction.
    """

    # 1. Draft patterns
    DRAFT_PATTERNS = [
        re.compile(
            r"^(?:son,?\s*)?(?:send|prepare|write|draft)\s+(?:a\s+)?whatsapp\s+message\s+(?:to|for)\s+(?P<recipient>[^:\n,]+?)(?:\s*[:,\-]\s*|\s+(?:saying|that|with\s+text)\s+)(?P<message>.+)$",
            re.IGNORECASE,
        ),
        re.compile(
            r"^(?:son,?\s*)?(?:send|tell|message)\s+(?P<recipient>[^:\n,]+?)\s+(?:a\s+)?whatsapp\s+message\s+(?:saying|that)\s+(?P<message>.+)$",
            re.IGNORECASE,
        ),
        re.compile(
            r"^(?:son,?\s*)?(?:send|message)\s+(?P<recipient>[^:\n,]+?)\s+on\s+whatsapp\s+(?:saying|that|with\s+text)\s+(?P<message>.+)$",
            re.IGNORECASE,
        ),
        re.compile(
            r"^(?:son,?\s*)?whatsapp\s+(?P<recipient>[^:\n,]+?)\s+(?:saying|that|with\s+message)\s+(?P<message>.+)$",
            re.IGNORECASE,
        ),
        re.compile(
            r"^(?:son,?\s*)?whatsapp\s+message\s+to\s+(?P<recipient>[^:\n,]+?)\s*:\s*(?P<message>.+)$",
            re.IGNORECASE,
        ),
    ]

    # 2. Confirmation patterns
    CONFIRM_PATTERN = re.compile(
        r"^(?:son,?\s*)?(?:yes|yep|yeah|sure|confirm|send\s+it|open\s+(?:the\s+)?draft|open\s+it|go\s+ahead|proceed|please\s+open|please\s+do)$",
        re.IGNORECASE,
    )

    # 3. Cancellation patterns
    CANCEL_PATTERN = re.compile(
        r"^(?:son,?\s*)?(?:cancel\s+(?:that\s+)?message|cancel\s+(?:the\s+)?draft|cancel\s+that|cancel|don'?t\s+send|discard\s+draft|stop)$",
        re.IGNORECASE,
    )

    # 4. Edit patterns
    EDIT_MESSAGE_PATTERN = re.compile(
        r"^(?:son,?\s*)?(?:change|edit|update)\s+(?:the\s+)?message\s+(?:to|as)\s+(?P<new_message>.+)$",
        re.IGNORECASE,
    )
    EDIT_RECIPIENT_PATTERN = re.compile(
        r"^(?:son,?\s*)?(?:change|edit|update)\s+(?:the\s+)?recipient\s+(?:to)\s+(?P<new_recipient>.+)$",
        re.IGNORECASE,
    )

    # 5. Help patterns
    HELP_PATTERN = re.compile(
        r"^(?:son,?\s*)?(?:whatsapp\s+help|how\s+to\s+(?:send|use)\s+whatsapp|help\s+with\s+whatsapp)$",
        re.IGNORECASE,
    )

    @classmethod
    def parse(cls, transcript: str, brain_client=None) -> WhatsAppVoiceCommand:
        """
        Parse raw speech transcript into a validated WhatsAppVoiceCommand.

        Args:
            transcript: Recognized speech from microphone / Whisper
            brain_client: Optional LLM brain instance for conversational fallback

        Returns:
            WhatsAppVoiceCommand instance
        """
        raw = transcript.strip()
        clean = raw.rstrip(".!? ")

        if not clean:
            return WhatsAppVoiceCommand(
                intent=WhatsAppIntentType.UNKNOWN,
                raw_transcript=raw,
                confidence=0.0,
            )

        # 1. Check Confirmation
        if cls.CONFIRM_PATTERN.match(clean):
            return WhatsAppVoiceCommand(
                intent=WhatsAppIntentType.CONFIRM_PENDING_DRAFT,
                raw_transcript=raw,
                confidence=0.98,
            )

        # 2. Check Cancellation
        if cls.CANCEL_PATTERN.match(clean):
            return WhatsAppVoiceCommand(
                intent=WhatsAppIntentType.CANCEL_PENDING_DRAFT,
                raw_transcript=raw,
                confidence=0.98,
            )

        # 3. Check Edit Message
        m_msg = cls.EDIT_MESSAGE_PATTERN.match(clean)
        if m_msg:
            new_text = m_msg.group("new_message").strip()
            return WhatsAppVoiceCommand(
                intent=WhatsAppIntentType.EDIT_PENDING_DRAFT,
                new_message_text=new_text,
                raw_transcript=raw,
                confidence=0.95,
            )

        # 4. Check Edit Recipient
        m_rec = cls.EDIT_RECIPIENT_PATTERN.match(clean)
        if m_rec:
            new_rec = m_rec.group("new_recipient").strip()
            return WhatsAppVoiceCommand(
                intent=WhatsAppIntentType.EDIT_PENDING_DRAFT,
                new_recipient_name=new_rec,
                raw_transcript=raw,
                confidence=0.95,
            )

        # 5. Check Help
        if cls.HELP_PATTERN.match(clean):
            return WhatsAppVoiceCommand(
                intent=WhatsAppIntentType.HELP,
                raw_transcript=raw,
                confidence=0.95,
            )

        # 6. Check Draft Message
        for pattern in cls.DRAFT_PATTERNS:
            match = pattern.match(clean)
            if match:
                recipient = match.group("recipient").strip().strip("\"'")
                message = match.group("message").strip().strip("\"'")
                # Validate length bounds
                if len(recipient) > 100 or len(message) > 4000:
                    logger.warning("Recipient or message text exceeded maximum length.")
                    return WhatsAppVoiceCommand(
                        intent=WhatsAppIntentType.UNKNOWN,
                        raw_transcript=raw,
                        confidence=0.0,
                    )
                return WhatsAppVoiceCommand(
                    intent=WhatsAppIntentType.DRAFT_WHATSAPP_MESSAGE,
                    recipient_name=recipient,
                    message_text=message,
                    raw_transcript=raw,
                    confidence=0.96,
                )

        # 7. Optional LLM fallback for non-standard phrasings if brain is available
        if brain_client and ("whatsapp" in clean.lower() or "message" in clean.lower()):
            try:
                extracted = cls._extract_with_llm(clean, brain_client)
                if extracted:
                    return extracted
            except Exception as e:
                logger.warning(f"LLM intent fallback extraction failed: {e}")

        return WhatsAppVoiceCommand(
            intent=WhatsAppIntentType.UNKNOWN,
            raw_transcript=raw,
            confidence=0.0,
        )

    @classmethod
    def _extract_with_llm(cls, transcript: str, brain_client) -> Optional[WhatsAppVoiceCommand]:
        """Strict JSON schema extraction via local LLM."""
        prompt = (
            "Extract structured WhatsApp voice intent from this transcript:\n"
            f"\"{transcript}\"\n\n"
            "Respond ONLY with a JSON object in this schema:\n"
            "{\n"
            "  \"intent\": \"draft_whatsapp_message\" | \"confirm_pending_draft\" | \"edit_pending_draft\" | \"cancel_pending_draft\" | \"help\" | \"unknown\",\n"
            "  \"recipient_name\": \"string or null\",\n"
            "  \"message_text\": \"string or null\"\n"
            "}\n"
            "Do not include any other text."
        )
        if hasattr(brain_client, "think"):
            res = brain_client.think(prompt, skip_memory=True, skip_codebase=True)
            # Find JSON block
            m = re.search(r"\{[\s\S]*\}", res)
            if m:
                data = json.loads(m.group(0))
                intent_str = data.get("intent", "unknown")
                try:
                    intent_type = WhatsAppIntentType(intent_str)
                    return WhatsAppVoiceCommand(
                        intent=intent_type,
                        recipient_name=data.get("recipient_name") or None,
                        message_text=data.get("message_text") or None,
                        raw_transcript=transcript,
                        confidence=0.85,
                    )
                except ValueError:
                    pass
        return None
