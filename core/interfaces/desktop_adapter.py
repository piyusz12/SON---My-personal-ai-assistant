# core/interfaces/desktop_adapter.py — Desktop GUI / HUD Interface Adapter for SON V3
"""
Desktop Interface Adapter for SON V3:
Enforces:
  1. Standardized backend communication for desktop GUI and HUD windows.
  2. Strict session and request tracking between PyQt/PySide and SonOrchestrator.
  3. Safe display of proposed actions, risk tiers, and arguments (with secrets redacted).
  4. Explicit Approve and Deny boundaries linked to exact approval request IDs.
  5. Rejection of stale or expired approval dialog responses.
  6. Prevention of GUI direct invocations of host or filesystem operations.
"""

import time
import logging
from typing import Any, Optional, Callable

from core.config import Config, SecurityLevel
from core.interfaces.base_adapter import BaseInterfaceAdapter
from core.interfaces.contract import InterfaceRequest, InterfaceResponse
from core.orchestrator import OrchestrationStatus
from core.security.approval_interface import trusted_approval_interface
from core.security.audit_logger import redact_secrets

logger = Config.get_logger(__name__)


class DesktopInterfaceAdapter(BaseInterfaceAdapter):
    """
    Standardized adapter mediating between desktop GUI components and SonOrchestrator.
    """

    def __init__(
        self,
        orchestrator=None,
        default_user_id: str = "son_desktop_user",
        session_id: Optional[str] = None,
        on_status_change: Optional[Callable[[str], None]] = None,
        on_approval_required: Optional[Callable[[dict[str, Any]], bool]] = None,
    ):
        super().__init__(
            interface_type="desktop_gui",
            orchestrator=orchestrator,
            default_user_id=default_user_id,
        )
        self._session_id = session_id or "desktop_gui_session"
        self.on_status_change = on_status_change
        self.on_approval_required = on_approval_required

    def submit_user_message(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        timeout: float = 60.0,
    ) -> InterfaceResponse:
        """
        Submit a message from the desktop GUI into the central orchestrator pipeline.
        """
        clean_text = (message or "").strip()
        if not clean_text:
            return InterfaceResponse(
                request_id=f"gui_empty_{int(time.time()*1000)}",
                status=OrchestrationStatus.VALIDATION_ERROR,
                response_text="Message cannot be empty.",
                error="Empty input",
            )

        if self.on_status_change:
            self.on_status_change("thinking")

        req = self.normalize_request(
            message=clean_text,
            session_id=self._session_id,
            conversation_id=conversation_id,
            metadata={"source": "desktop_hud"},
        )
        self._session_id = req.session_id

        response = self.send_request(req, timeout=timeout)

        # Handle pending approval via UI callback if needed
        if response.status == OrchestrationStatus.AWAITING_APPROVAL and response.pending_approval:
            approval_id = response.pending_approval.get("approval_id")
            if approval_id and self.on_approval_required:
                approved = self.on_approval_required(response.pending_approval)
                response = self.submit_approval_decision(approval_id, approved)

        if self.on_status_change:
            self.on_status_change("idle")

        return response

    def submit_approval_decision(
        self,
        approval_id: str,
        approved: bool,
    ) -> InterfaceResponse:
        """
        Handle explicit Approve or Deny action triggered by user on the Desktop HUD.
        """
        return self.handle_approval(
            approval_id=approval_id,
            approved=approved,
            session_id=self._session_id,
        )

    def query_system_status(self) -> InterfaceResponse:
        """Safe query for telemetry and system health."""
        return self.execute_action(
            tool_name="get_system_info",
            arguments={},
            session_id=self._session_id,
        )

    def list_docker_containers(self) -> InterfaceResponse:
        """Safe query for container status."""
        return self.execute_action(
            tool_name="docker_list_containers",
            arguments={},
            session_id=self._session_id,
        )

