# core/interfaces/automation_adapter.py — Automation Interface Adapter for SON V3
"""
Automation Interface Adapter for SON V3:
Enforces:
  1. Standardized orchestration of scheduled routines and automated tasks.
  2. Independent PolicyEngine evaluation for every step in a routine.
  3. Halting of execution on failure or unapproved high-risk operations.
  4. Preservation of trusted ownership (usr_automation) and session tracking.
  5. Prevention of autonomous approval fabrication by automation loops.
"""

import time
import logging
from typing import Any, Optional, Callable

from core.config import Config
from core.interfaces.base_adapter import BaseInterfaceAdapter
from core.interfaces.contract import InterfaceRequest, InterfaceResponse
from core.orchestrator import OrchestrationStatus
from core.security.audit_logger import audit_logger

logger = Config.get_logger(__name__)


class AutomationInterfaceAdapter(BaseInterfaceAdapter):
    """
    Standardized adapter for background routines and scheduled automations.
    """

    def __init__(
        self,
        orchestrator=None,
        default_user_id: str = "usr_automation",
        session_id: Optional[str] = None,
    ):
        super().__init__(
            interface_type="automation",
            orchestrator=orchestrator,
            default_user_id=default_user_id,
        )
        self._session_id = session_id or "automation_scheduler_session"

    def execute_routine_step(
        self,
        routine_name: str,
        step_number: int,
        tool_name: str,
        arguments: dict[str, Any],
        approval_id: Optional[str] = None,
    ) -> InterfaceResponse:
        """
        Execute an individual step of an automation routine through the central orchestrator.
        Enforces policy evaluation and halts on approval requirement or denial.
        """
        audit_logger.log_event(
            event_type="AUTOMATION_STEP_SUBMITTED",
            actor=self.default_user_id,
            session_id=self._session_id,
            tool_name=tool_name,
            status="PROCESSING",
            details={"routine": routine_name, "step": step_number},
        )

        res = self.execute_action(
            tool_name=tool_name,
            arguments=arguments,
            user_id=self.default_user_id,
            session_id=self._session_id,
            approval_id=approval_id,
        )

        if res.status == OrchestrationStatus.AWAITING_APPROVAL:
            audit_logger.log_event(
                event_type="AUTOMATION_STEP_REQUIRES_APPROVAL",
                actor=self.default_user_id,
                session_id=self._session_id,
                tool_name=tool_name,
                approval_id=res.pending_approval.get("approval_id") if res.pending_approval else None,
                status="AWAITING_APPROVAL",
                details={"routine": routine_name, "step": step_number},
            )

        return res

    def run_safe_sequence(
        self,
        routine_name: str,
        steps: list[dict[str, Any]],
    ) -> list[InterfaceResponse]:
        """
        Execute a sequence of routine steps fail-closed.
        Stops immediately if any step fails or requires unapproved authorization.
        """
        results = []
        for idx, step in enumerate(steps, start=1):
            tool = step.get("tool", "")
            args = step.get("args", {})
            appr = step.get("approval_id")

            step_res = self.execute_routine_step(
                routine_name=routine_name,
                step_number=idx,
                tool_name=tool,
                arguments=args,
                approval_id=appr,
            )
            results.append(step_res)

            # Halt on failure or unfulfilled approval
            if (
                step_res.status in (
                    OrchestrationStatus.DENIED,
                    OrchestrationStatus.PENDING_APPROVAL,
                    OrchestrationStatus.AWAITING_APPROVAL,
                    OrchestrationStatus.ERROR,
                    OrchestrationStatus.INTERNAL_ERROR,
                    OrchestrationStatus.VALIDATION_ERROR,
                )
                or not step_res.tool_results
                or not step_res.tool_results[0].success
            ):
                audit_logger.log_event(
                    event_type="AUTOMATION_SEQUENCE_HALTED",
                    actor=self.default_user_id,
                    session_id=self._session_id,
                    tool_name=tool,
                    status="HALTED",
                    details={"routine": routine_name, "halted_at_step": idx, "reason": step_res.error or step_res.response_text},
                )
                break

        return results
