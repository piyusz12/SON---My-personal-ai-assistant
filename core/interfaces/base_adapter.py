# core/interfaces/base_adapter.py — Abstract Base Interface Adapter for SON V3
"""
Base Interface Adapter for SON V3:
Enforces:
  1. Common request normalization for all ingress interfaces.
  2. Structured response conversion and error status mapping.
  3. Safe timeout, cancellation, and concurrency management.
  4. Unified routing through the centralized SonOrchestrator.
  5. Consistent approval resolution propagation.
  6. Persistent adapter session bound to authenticated principal.
"""

import time
import logging
from abc import ABC
from typing import Any, Optional
import concurrent.futures

from core.config import Config
from core.orchestrator import SonOrchestrator, orchestrator as default_orchestrator, OrchestrationStatus
from core.interfaces.contract import InterfaceRequest, InterfaceResponse, InterfaceType
from core.security.context import SecurityContext, SecurityContextError, create_trusted_context
from core.security.session_manager import session_manager
from core.security.audit_logger import audit_logger

logger = Config.get_logger(__name__)


class BaseInterfaceAdapter(ABC):
    """
    Abstract interface adapter standardizing communication with SonOrchestrator.
    """

    def __init__(
        self,
        interface_type: str = "cli",
        orchestrator: Optional[SonOrchestrator] = None,
        default_user_id: str = "primary_user",
        session_id: Optional[str] = None,
    ):
        self.interface_type = interface_type
        self.orchestrator = orchestrator or default_orchestrator
        self.default_user_id = default_user_id

        # Bind persistent session to adapter
        if session_id:
            sess = session_manager.register_session(session_id, default_user_id, interface_type)
            self._session_id = sess.session_id
        else:
            sess = session_manager.create_session(default_user_id, interface_type)
            self._session_id = sess.session_id

        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=8, thread_name_prefix=f"{interface_type}_worker")
        self._active_requests: dict[str, concurrent.futures.Future] = {}

    def set_session_id(self, session_id: str):
        self._session_id = session_id

    def normalize_request(
        self,
        message: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> InterfaceRequest:
        """Create a validated, normalized InterfaceRequest."""
        return InterfaceRequest(
            user_id=user_id or self.default_user_id,
            session_id=session_id or self._session_id,
            interface=self.interface_type,
            conversation_id=conversation_id,
            message=message,
            metadata=metadata or {},
        )

    def send_request(
        self,
        request: InterfaceRequest,
        timeout: float = 60.0,
    ) -> InterfaceResponse:
        """
        Synchronously dispatch a normalized request to the central orchestrator
        with timeout and cancellation protections.
        """
        start_time = time.perf_counter()

        def _execute():
            ctx = request.to_security_context()
            return self.orchestrator.process_request(request.message, context=ctx)

        future = self._executor.submit(_execute)
        self._active_requests[request.request_id] = future

        try:
            orch_res = future.result(timeout=timeout)
            return InterfaceResponse.from_orchestrator_response(orch_res, request_id=request.request_id)
        except concurrent.futures.TimeoutError:
            future.cancel()
            duration_ms = (time.perf_counter() - start_time) * 1000
            audit_logger.log_event(
                event_type="INTERFACE_REQUEST_TIMEOUT",
                request_id=request.request_id,
                session_id=request.session_id or self._session_id,
                actor=request.user_id,
                status="TIMEOUT",
                details={"interface": self.interface_type, "timeout": timeout},
            )
            return InterfaceResponse(
                request_id=request.request_id,
                status=OrchestrationStatus.TIMEOUT,
                response_text=f"Request timed out after {timeout} seconds.",
                error="Operation timed out",
                execution_metadata={"duration_ms": duration_ms, "timeout": timeout},
            )
        except SecurityContextError as sce:
            duration_ms = (time.perf_counter() - start_time) * 1000
            return InterfaceResponse(
                request_id=request.request_id,
                status=OrchestrationStatus.VALIDATION_ERROR,
                response_text=f"Security Error: {sce}",
                error=str(sce),
                execution_metadata={"duration_ms": duration_ms, "failure_category": "validation_error"},
            )
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(f"Error executing request across adapter '{self.interface_type}': {e}", exc_info=True)
            return InterfaceResponse(
                request_id=request.request_id,
                status=OrchestrationStatus.INTERNAL_ERROR,
                response_text=f"An internal error occurred: {e}",
                error=str(e),
                execution_metadata={"duration_ms": duration_ms, "failure_category": "internal_error"},
            )
        finally:
            self._active_requests.pop(request.request_id, None)

    def cancel_request(self, request_id: str) -> bool:
        """Cancel an in-flight request if possible."""
        future = self._active_requests.get(request_id)
        if future and not future.done():
            cancelled = future.cancel()
            if cancelled:
                audit_logger.log_event(
                    event_type="INTERFACE_REQUEST_CANCELLED",
                    request_id=request_id,
                    status="CANCELLED",
                    details={"interface": self.interface_type},
                )
            return cancelled
        return False

    def handle_approval(
        self,
        approval_id: str,
        approved: bool,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> InterfaceResponse:
        """Forward an interactive approval decision to the orchestrator."""
        uid = user_id or self.default_user_id
        sid = session_id or self._session_id
        ctx = create_trusted_context(
            user_id=uid,
            interface_type=self.interface_type,
            session_id=sid,
        )
        orch_res = self.orchestrator.handle_approval(
            approval_id=approval_id,
            approved=approved,
            context=ctx,
        )
        return InterfaceResponse.from_orchestrator_response(orch_res)

    def execute_action(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        approval_id: Optional[str] = None,
    ) -> InterfaceResponse:
        """Execute a direct tool action through the central orchestrator."""
        uid = user_id or self.default_user_id
        sid = session_id or self._session_id
        ctx = create_trusted_context(
            user_id=uid,
            interface_type=self.interface_type,
            session_id=sid,
        )
        act_res = self.orchestrator.execute_action(
            tool_name=tool_name,
            arguments=arguments,
            context=ctx,
            approval_id=approval_id,
        )
        status = OrchestrationStatus.SUCCESS if act_res.success else (
            OrchestrationStatus.PENDING_APPROVAL if act_res.requires_approval else OrchestrationStatus.DENIED
        )
        return InterfaceResponse(
            request_id=act_res.approval_id or f"act_{int(time.time()*1000)}",
            status=status,
            response_text=act_res.output,
            tool_results=[act_res],
            pending_approval={"approval_id": act_res.approval_id} if act_res.approval_id else None,
            error=act_res.error,
            execution_metadata=act_res.execution_metadata,
        )

    def shutdown(self):
        """Cleanly shutdown adapter background thread pool."""
        self._executor.shutdown(wait=False)
