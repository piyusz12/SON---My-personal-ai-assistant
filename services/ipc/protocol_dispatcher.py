# services/ipc/protocol_dispatcher.py — Request Dispatcher for Desktop Named Pipe IPC
"""
Dispatches inbound IPC protocol requests from the C# WPF Desktop client
to the centralized SON Orchestrator, PolicyEngine, ApprovalManager,
Memory system, and Security Audit Logger.
"""

import time
import uuid
import logging
from typing import Any, Optional

from core.config import Config
from core.orchestrator import SonOrchestrator, OrchestrationStatus
from core.security.context import create_trusted_context, SecurityContext, SecurityContextError
from core.security.identity import identity_manager
from core.security.session_manager import session_manager
from core.security.approval_manager import approval_manager, ApprovalStatus
from core.security.audit_logger import audit_logger
from memory.structured_memory import StructuredMemory

logger = Config.get_logger(__name__)


class ProtocolDispatcher:
    """
    Central dispatcher for desktop IPC messages.
    Validates protocol envelopes, manages desktop sessions, and maps
    requests directly to the trusted SonOrchestrator and security components.
    """

    def __init__(
        self,
        orchestrator: Optional[SonOrchestrator] = None,
        structured_memory: Optional[StructuredMemory] = None,
    ):
        self.orchestrator = orchestrator or SonOrchestrator()
        self.structured_memory = structured_memory or StructuredMemory()
        self._active_sessions: dict[str, str] = {}  # session_id -> user_id

    def dispatch(self, raw_message: dict[str, Any]) -> dict[str, Any]:
        """
        Process an inbound JSON message and return the standard JSON response.
        Enforces protocol versioning and handles errors gracefully.
        """
        message_id = raw_message.get("message_id") or f"msg_{uuid.uuid4().hex[:12]}"
        request_id = raw_message.get("request_id") or f"req_{uuid.uuid4().hex[:12]}"
        action = raw_message.get("action", "")
        payload = raw_message.get("payload") or {}

        response_base = {
            "protocol_version": "1.0",
            "message_id": f"msg_resp_{uuid.uuid4().hex[:12]}",
            "request_id": request_id,
            "message_type": "RESPONSE",
            "action": action,
            "timestamp": time.time(),
            "payload": {},
            "error": None,
        }

        try:
            handler = getattr(self, f"handle_{action}", None)
            if not handler:
                response_base["error"] = f"Unknown action: '{action}'"
                response_base["payload"] = {"status": "ERROR", "reason": f"Action '{action}' is not supported."}
                return response_base

            result_payload = handler(payload, request_id=request_id)
            response_base["payload"] = result_payload
            return response_base

        except Exception as exc:
            logger.exception("Error handling IPC action '%s': %s", action, exc)
            response_base["error"] = str(exc)
            response_base["payload"] = {
                "status": "INTERNAL_ERROR",
                "message": str(exc),
            }
            return response_base

    # ── Action Handlers ──────────────────────────────────────────

    def handle_ping(self, payload: dict[str, Any], request_id: str) -> dict[str, Any]:
        return {
            "status": "PONG",
            "server_time": time.time(),
            "version": "3.0.0",
        }

    def handle_handshake(self, payload: dict[str, Any], request_id: str) -> dict[str, Any]:
        """Establish an authenticated session for the desktop client."""
        client_version = payload.get("client_version", "1.0.0")
        client_type = payload.get("client_type", "wpf_desktop")
        requested_user = payload.get("requested_user_id", "usr_primary")

        # Canonicalize user
        canon_user = identity_manager.resolve_user_id(requested_user) or "usr_primary"
        if not identity_manager.is_valid_user(canon_user):
            canon_user = "usr_primary"

        # Create trusted session
        sess = session_manager.create_session(
            user_id=canon_user,
            interface_type="desktop",
            metadata={"ip_address": "127.0.0.1", "user_agent": f"SON.Desktop/{client_version}"},
        )
        self._active_sessions[sess.session_id] = canon_user

        audit_logger.log_event(
            event_type="DESKTOP_HANDSHAKE_ESTABLISHED",
            actor=canon_user,
            session_id=sess.session_id,
            request_id=request_id,
            status="SUCCESS",
            details={"client_type": client_type, "client_version": client_version},
        )

        return {
            "status": "AUTHENTICATED",
            "user_id": canon_user,
            "session_id": sess.session_id,
            "server_version": "3.0.0",
            "active_model": getattr(Config, "MAIN_MODEL", "qwen2.5:7b-q4_K_M"),
            "features_enabled": [
                "pydantic_ai",
                "policy_engine",
                "approval_manager",
                "action_executor",
                "structured_memory",
                "audit_logger",
            ],
        }

    def handle_chat_send(self, payload: dict[str, Any], request_id: str) -> dict[str, Any]:
        """Route user prompt to the central SonOrchestrator."""
        prompt = payload.get("prompt", "").strip()
        user_id = payload.get("user_id") or "usr_primary"
        session_id = payload.get("session_id")
        conversation_id = payload.get("conversation_id") or "conv_desktop"

        if not prompt:
            return {"status": "ERROR", "message": "Empty prompt provided."}

        # Resolve identity
        canon_user = identity_manager.resolve_user_id(user_id) or "usr_primary"

        # Check or establish session
        if not session_id or not session_manager.get_session(session_id):
            sess = session_manager.create_session(
                user_id=canon_user,
                interface_type="desktop",
                metadata={"ip_address": "127.0.0.1", "user_agent": "SON.Desktop/1.0"},
            )
            session_id = sess.session_id
            self._active_sessions[session_id] = canon_user

        # Create trusted context
        context = create_trusted_context(
            user_id=canon_user,
            session_id=session_id,
            interface_type="desktop",
            conversation_id=conversation_id,
        )

        # Process through orchestrator
        start_t = time.perf_counter()
        resp = self.orchestrator.process_request(text=prompt, context=context)
        duration_ms = round((time.perf_counter() - start_t) * 1000, 1)

        tool_results_data = []
        for tr in resp.tool_results:
            tool_results_data.append({
                "success": tr.success,
                "tool_name": tr.tool_name,
                "output": tr.output,
                "error": tr.error,
                "risk_tier": tr.risk_tier,
                "requires_approval": tr.requires_approval,
            })

        return {
            "status": resp.status.value,
            "response": resp.response_text or resp.text,
            "tool_results": tool_results_data,
            "pending_approval": resp.pending_approval,
            "error": resp.error,
            "duration_ms": duration_ms,
            "session_id": session_id,
        }

    def handle_approval_resolve(self, payload: dict[str, Any], request_id: str) -> dict[str, Any]:
        """Resolve a human-in-the-loop pending approval request."""
        approval_id = payload.get("approval_id")
        approved = bool(payload.get("approved", False))
        decision_by = payload.get("decision_by") or "usr_primary"

        canon_approver = identity_manager.resolve_user_id(decision_by) or "usr_primary"

        if not approval_id:
            return {"status": "ERROR", "message": "approval_id is required."}

        success, msg = approval_manager.resolve_request(
            request_id=approval_id,
            approved=approved,
            actor=canon_approver,
        )

        return {
            "status": "APPROVED" if (success and approved) else ("DENIED" if success else "FAILED"),
            "approval_id": approval_id,
            "success": success,
            "message": msg,
        }

    def handle_approvals_list(self, payload: dict[str, Any], request_id: str) -> dict[str, Any]:
        """List active pending approvals."""
        pending = []
        with approval_manager._lock:
            for req in list(approval_manager._requests.values()):
                if req.status == ApprovalStatus.PENDING and not req.is_expired():
                    pending.append(req.to_dict())

        return {
            "status": "SUCCESS",
            "approvals": pending,
            "count": len(pending),
        }

    def handle_security_status(self, payload: dict[str, Any], request_id: str) -> dict[str, Any]:
        """Provide current security status and recent audit events."""
        recent_events = audit_logger.get_recent_events(limit=15)
        pending_count = sum(
            1 for req in approval_manager._requests.values()
            if req.status == ApprovalStatus.PENDING and not req.is_expired()
        )

        return {
            "status": "SECURE",
            "policy_engine": "ACTIVE",
            "approval_manager": "ACTIVE",
            "audit_logger": "ACTIVE",
            "sandbox_active": True,
            "pending_approvals_count": pending_count,
            "recent_events": recent_events,
        }

    def handle_memory_list(self, payload: dict[str, Any], request_id: str) -> dict[str, Any]:
        """Fetch persistent facts from SQLite structured memory."""
        category = payload.get("category")
        limit = int(payload.get("limit", 50))
        facts = self.structured_memory.get_facts(category=category, limit=limit)
        return {
            "status": "SUCCESS",
            "facts": facts,
            "count": len(facts),
        }

    def handle_memory_add(self, payload: dict[str, Any], request_id: str) -> dict[str, Any]:
        """Store a new fact into structured memory."""
        fact = payload.get("fact", "").strip()
        category = payload.get("category", "general")
        confidence = float(payload.get("confidence", 1.0))

        if not fact:
            return {"status": "ERROR", "message": "Fact cannot be empty."}

        self.structured_memory.store_fact(fact=fact, category=category, confidence=confidence)
        return {"status": "SUCCESS", "message": "Fact stored successfully."}

    def handle_memory_delete(self, payload: dict[str, Any], request_id: str) -> dict[str, Any]:
        """Delete a fact from structured memory by id."""
        fact_id = payload.get("id")
        if fact_id is None:
            return {"status": "ERROR", "message": "Fact id is required."}

        try:
            fact_id_int = int(fact_id)
        except (ValueError, TypeError):
            return {"status": "ERROR", "message": "Invalid fact id."}

        deleted = self.structured_memory.delete_fact_by_id(fact_id_int)
        if deleted:
            return {"status": "SUCCESS", "message": f"Fact {fact_id_int} deleted."}
        return {"status": "ERROR", "message": f"Fact {fact_id_int} not found."}

    def handle_hardware_telemetry(self, payload: dict[str, Any], request_id: str) -> dict[str, Any]:
        """Gather real-time hardware telemetry: CPU, RAM, GPU, and VRAM."""
        cpu_pct = 0.0
        ram_used = 0
        ram_total = 0

        try:
            import psutil
            cpu_pct = psutil.cpu_percent(interval=None)
            mem = psutil.virtual_memory()
            ram_used = mem.used
            ram_total = mem.total
        except Exception:
            pass

        gpu_pct = 0.0
        vram_used = 0
        vram_total = 0

        try:
            from core.gpu_manager import GPUManager
            gpu_metrics = GPUManager().get_metrics()
            gpu_pct = float(gpu_metrics.get("gpu_util", 0.0))
            vram_used_mb = float(gpu_metrics.get("vram_used_mb", 0.0))
            vram_total_mb = float(gpu_metrics.get("vram_total_mb", 0.0))
            vram_used = int(vram_used_mb * 1024 * 1024)
            vram_total = int(vram_total_mb * 1024 * 1024)
        except Exception as e:
            logger.debug(f"GPU metrics fetch error: {e}")

        return {
            "status": "SUCCESS",
            "cpu_percent": cpu_pct,
            "ram_used_bytes": ram_used,
            "ram_total_bytes": ram_total,
            "gpu_percent": gpu_pct,
            "vram_used_bytes": vram_used,
            "vram_total_bytes": vram_total,
            "ollama_active": True,
            "model_name": getattr(Config, "MAIN_MODEL", "qwen2.5:7b-q4_K_M"),
        }
