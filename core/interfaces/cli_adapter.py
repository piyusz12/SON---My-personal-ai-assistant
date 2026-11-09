# core/interfaces/cli_adapter.py — CLI Interface Adapter for SON V3
"""
CLI Interface Adapter for SON V3:
Enforces:
  1. Standardized ingress for CLI interactive turns and console commands.
  2. Safe execution of read-only and action-oriented commands through SonOrchestrator.
  3. Interactive human-in-the-loop approval prompting via terminal UI.
  4. Redaction of sensitive credentials before recording in command history.
  5. Timeout, interrupt, and cancellation handling.
"""

import time
import logging
from typing import Any, Optional, Callable

from core.config import Config, SecurityLevel
from core.interfaces.base_adapter import BaseInterfaceAdapter
from core.interfaces.contract import InterfaceRequest, InterfaceResponse
from core.orchestrator import OrchestrationStatus
from core.security.audit_logger import redact_secrets

logger = Config.get_logger(__name__)


class CLIInterfaceAdapter(BaseInterfaceAdapter):
    """
    Standardized adapter for interactive terminal and CLI execution.
    """

    def __init__(
        self,
        orchestrator=None,
        terminal_ui=None,
        default_user_id: str = "primary_user",
        session_id: Optional[str] = None,
    ):
        super().__init__(
            interface_type="cli",
            orchestrator=orchestrator,
            default_user_id=default_user_id,
            session_id=session_id,
        )
        self.ui = terminal_ui
        if session_id:
            self._session_id = session_id
        self._history: list[dict[str, Any]] = []

    def set_session_id(self, session_id: str):
        self._session_id = session_id

    def execute_prompt(
        self,
        prompt_text: str,
        conversation_id: Optional[str] = None,
        timeout: float = 60.0,
        interactive_approval: bool = True,
    ) -> InterfaceResponse:
        """
        Execute a user prompt from the command line through the normalized contract.
        Prompts for approval interactively if the action requires it.
        """
        clean_text = (prompt_text or "").strip()
        if not clean_text:
            return InterfaceResponse(
                request_id=f"cli_empty_{int(time.time()*1000)}",
                status=OrchestrationStatus.VALIDATION_ERROR,
                response_text="Empty prompt received.",
                error="Empty input",
            )

        # Normalize request
        req = self.normalize_request(
            message=clean_text,
            session_id=self._session_id,
            conversation_id=conversation_id,
            metadata={"source": "cli_prompt"},
        )
        self._session_id = req.session_id

        # Dispatch through orchestrator
        response = self.send_request(req, timeout=timeout)

        # If action requires approval and interactive approval is enabled
        if response.status == OrchestrationStatus.AWAITING_APPROVAL and response.pending_approval:
            approval_id = response.pending_approval.get("approval_id")
            if interactive_approval and approval_id:
                approved = False
                if self.ui and hasattr(self.ui, "ask_permission"):
                    tool_name = response.pending_approval.get("tool_name", "Action")
                    args = response.pending_approval.get("arguments", {})
                    approved = self.ui.ask_permission(tool_name, redact_secrets(args), SecurityLevel.CRITICAL)

                # Send approval decision
                response = self.handle_approval(
                    approval_id=approval_id,
                    approved=approved,
                    session_id=self._session_id,
                )

        # Record history with redacted secrets
        self._history.append({
            "timestamp": time.time(),
            "request_id": response.request_id,
            "prompt": redact_secrets(clean_text),
            "status": response.status.value,
        })

        # Display response on UI if provided
        if self.ui and hasattr(self.ui, "show_son_response") and response.response_text:
            self.ui.show_son_response(response.response_text)

        return response
