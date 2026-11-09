# core/interfaces/contract.py — Standard Interface Request-Response Contract for SON V3
"""
Standard Interface Request-Response Contract for SON V3:
Enforces:
  1. Normalized request schema across all user interfaces.
  2. Normalized response schema with standardized execution outcomes.
  3. Strict interface identifier validation (rejecting unknown interfaces).
  4. Immutable binding of authenticated identity and session context.
  5. Conversion to and from central Orchestrator context and responses.
"""

from enum import Enum
import time
import secrets
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator

from core.orchestrator import OrchestratorResponse, OrchestrationStatus, ActionResult
from core.security.context import SecurityContext, SecurityContextError, create_trusted_context


VALID_INTERFACE_IDENTIFIERS = {
    "cli",
    "voice",
    "desktop",
    "desktop_gui",
    "whatsapp",
    "automation",
    "brain",
    "core_brain",
    "api",
    "router",
    "internet_agent",
    "desktop_agent",
    "test",
}


class InterfaceType(str, Enum):
    CLI = "cli"
    VOICE = "voice"
    DESKTOP = "desktop"
    DESKTOP_GUI = "desktop_gui"
    WHATSAPP = "whatsapp"
    AUTOMATION = "automation"
    BRAIN = "brain"
    API = "api"


class InterfaceRequest(BaseModel):
    """
    Normalized, validated request model for all SON interfaces.
    """
    request_id: str = Field(default_factory=lambda: f"req_{secrets.token_urlsafe(16)}")
    user_id: str = "primary_user"
    session_id: Optional[str] = None
    interface: str = "cli"
    conversation_id: Optional[str] = None
    message: str = ""
    timestamp: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("interface")
    @classmethod
    def validate_interface(cls, v: str) -> str:
        clean = (v or "").strip().lower()
        if clean not in VALID_INTERFACE_IDENTIFIERS:
            raise SecurityContextError(f"Security Error: Unknown or unauthorized interface identifier: '{v}'.")
        return clean

    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, v: str) -> str:
        clean = (v or "").strip()
        if not clean:
            raise SecurityContextError("User ID must be a non-empty, authenticated identity string.")
        return clean

    def to_security_context(self) -> SecurityContext:
        """Derive a trusted SecurityContext bound to this normalized request."""
        return create_trusted_context(
            user_id=self.user_id,
            interface_type=self.interface,
            session_id=self.session_id,
            conversation_id=self.conversation_id,
            metadata=self.metadata,
        )


class InterfaceResponse(BaseModel):
    """
    Normalized structured response model returned to all interfaces.
    """
    request_id: str
    status: OrchestrationStatus
    response_text: str = ""
    tool_results: list[ActionResult] = Field(default_factory=list)
    pending_approval: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    execution_metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_orchestrator_response(
        cls,
        orch_res: OrchestratorResponse,
        request_id: Optional[str] = None,
    ) -> "InterfaceResponse":
        """Map central OrchestratorResponse into normalized InterfaceResponse."""
        return cls(
            request_id=request_id or orch_res.request_id,
            status=orch_res.status,
            response_text=orch_res.response_text or orch_res.text,
            tool_results=orch_res.tool_results,
            pending_approval=orch_res.pending_approval,
            error=orch_res.error,
            execution_metadata=orch_res.execution_metadata,
        )

