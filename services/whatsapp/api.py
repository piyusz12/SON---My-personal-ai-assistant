# services/whatsapp/api.py — Local FastAPI Service for WhatsApp Messaging Integration
"""
Production-quality local REST API for WhatsApp message drafting.
Security & Policy:
- Bound strictly to 127.0.0.1 (never exposed externally).
- CORS limited to local loopback origins.
- Validates all request schemas and short-lived draft IDs.
- NEVER exposes an endpoint that automatically sends messages or clicks Send.
"""
import logging
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from core.config import Config
from services.whatsapp.browser_launcher import BrowserLauncher
from services.whatsapp.contacts import ContactRegistry
from services.whatsapp.models import (
    CancelRequest,
    CancelResponse,
    ConfirmRequest,
    ConfirmResponse,
    Contact,
    DraftRequest,
    DraftResponse,
    DraftStatus,
    EditRequest,
)
from services.whatsapp.service import WhatsAppVoiceService
from services.whatsapp.state_machine import DraftStateError

logger = Config.get_logger(__name__)

app = FastAPI(
    title="SON V3 WhatsApp Messaging Service",
    description="Local secure API for voice-controlled WhatsApp message drafting with human approval.",
    version="3.0.0",
)

# Origin Protection: Restrict strictly to loopback interface
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1",
        "http://localhost",
        "http://127.0.0.1:8765",
        "http://localhost:8765",
        "http://127.0.0.1:8766",
        "http://localhost:8766",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def get_service() -> WhatsAppVoiceService:
    return WhatsAppVoiceService.get_instance()


@app.get("/health", status_code=status.HTTP_200_OK)
def health_check() -> Dict[str, Any]:
    """Report service health, active draft status, and contact count."""
    svc = get_service()
    active = svc.state_machine.active_draft
    return {
        "status": "healthy",
        "service": "whatsapp_drafting",
        "active_draft_id": active.draft_id if active else None,
        "active_draft_status": active.status.value if active else None,
        "contacts_count": len(svc.contacts.list_all_contacts()),
    }


@app.post("/message/draft", response_model=DraftResponse, status_code=status.HTTP_201_CREATED)
def create_draft(req: DraftRequest) -> DraftResponse:
    """Validate recipient from local address book and create an expiring draft."""
    svc = get_service()
    resolution = svc.contacts.resolve_contact(req.recipient)

    if resolution.status == "NOT_FOUND":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=resolution.message,
        )
    elif resolution.status == "AMBIGUOUS":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=resolution.message,
        )

    contact = resolution.contact
    assert contact is not None

    try:
        draft, prompt = svc.state_machine.create_draft(contact=contact, message_text=req.message)
        return DraftResponse(
            draft_id=draft.draft_id,
            recipient=contact.display_name,
            phone_masked=contact.masked_phone,
            message=draft.message_text,
            status=draft.status,
            expires_in_seconds=draft.remaining_seconds,
            spoken_prompt=prompt,
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@app.post("/message/confirm", response_model=ConfirmResponse)
def confirm_draft(req: ConfirmRequest) -> ConfirmResponse:
    """Confirm the exact pending draft and open it in the default web browser."""
    svc = get_service()
    try:
        confirmed_draft, url = svc.state_machine.confirm_draft(req.draft_id)
        # Launch browser through secure orchestrator
        from core.orchestrator import orchestrator as global_orch
        from core.security.context import create_trusted_context

        wa_ctx = create_trusted_context(
            user_id="primary_user",
            interface_type="whatsapp",
            session_id=f"wa_api_confirm_{req.draft_id}",
        )
        act_res = global_orch.execute_action(
            tool_name="open_whatsapp_draft",
            arguments={"url": url},
            context=wa_ctx,
            tool_func=BrowserLauncher.open_draft_url,
        )
        if not act_res.success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Browser launch failed: {act_res.output}",
            )

        spoken = svc.state_machine.mark_draft_opened(confirmed_draft.draft_id)
        return ConfirmResponse(
            draft_id=confirmed_draft.draft_id,
            status=confirmed_draft.status,
            click_to_chat_url=url,
            spoken_status=spoken,
        )
    except DraftStateError as de:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(de))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@app.post("/message/cancel", response_model=CancelResponse)
def cancel_draft(req: CancelRequest) -> CancelResponse:
    """Cancel a specific pending draft."""
    svc = get_service()
    try:
        draft, spoken = svc.state_machine.cancel_draft(req.draft_id)
        return CancelResponse(
            draft_id=draft.draft_id,
            status=draft.status,
            message=spoken,
        )
    except DraftStateError as de:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(de))


@app.post("/message/edit", response_model=DraftResponse)
def edit_draft(req: EditRequest) -> DraftResponse:
    """Edit message text or recipient of a draft, invalidating prior confirmation."""
    svc = get_service()
    new_contact = None
    if req.new_recipient:
        res = svc.contacts.resolve_contact(req.new_recipient)
        if res.status != "MATCHED":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=res.message)
        new_contact = res.contact

    try:
        draft, prompt = svc.state_machine.edit_draft(
            draft_id=req.draft_id,
            new_message=req.new_message,
            new_contact=new_contact,
        )
        return DraftResponse(
            draft_id=draft.draft_id,
            recipient=draft.contact.display_name,
            phone_masked=draft.contact.masked_phone,
            message=draft.message_text,
            status=draft.status,
            expires_in_seconds=draft.remaining_seconds,
            spoken_prompt=prompt,
        )
    except DraftStateError as de:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(de))


@app.get("/message/current")
def get_current_draft() -> Optional[Dict[str, Any]]:
    """Return currently active draft if any."""
    svc = get_service()
    active = svc.state_machine.active_draft
    if not active:
        return None
    return {
        "draft_id": active.draft_id,
        "recipient": active.contact.display_name,
        "phone_masked": active.contact.masked_phone,
        "message": active.message_text,
        "status": active.status.value,
        "remaining_seconds": active.remaining_seconds,
    }


@app.get("/contacts", response_model=List[Contact])
def list_contacts() -> List[Contact]:
    """Retrieve all locally configured contacts."""
    svc = get_service()
    return svc.contacts.list_all_contacts()


@app.post("/contacts", response_model=Contact, status_code=status.HTTP_201_CREATED)
def add_contact(contact_data: Dict[str, Any]) -> Contact:
    """Add a validated contact to the local registry."""
    svc = get_service()
    try:
        return svc.contacts.add_contact(
            display_name=contact_data["display_name"],
            phone_number=contact_data["phone_number"],
            aliases=contact_data.get("aliases", []),
            notes=contact_data.get("notes", ""),
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
