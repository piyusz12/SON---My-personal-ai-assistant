# core/host_agent.py — Central HostAgent Core for SON V3
"""
HostAgent — The Central Orchestration and Execution Authority for SON V3.
Responsible for:
  1. Intent Recognition and Task Classification (fast-path heuristics)
  2. Multi-Tier Planning and Tool Discovery
  3. Permission Validation and Human Confirmation Gatekeeping
  4. Hybrid Memory Context Orchestration (L1 RAM, L2 SQLite, L3 ChromaDB)
  5. Multi-Model Routing and Hardware VRAM Governance (Ollama / RTX 4060)
  6. Multi-Tier Execution Coordination (Native API, CLI, UIA, Vision)
  7. Post-Execution Result Verification and State Validation
  8. Structured Telemetry and Event Bus Publishing
  9. Session & Identity Lifecycle Management
"""

import time
import logging
import secrets
from typing import Any, Optional, Union
from pydantic import BaseModel, Field

from core.config import Config
from core.intent_router import IntentRouter, IntentType, IntentResult
from core.orchestrator import (
    SonOrchestrator,
    orchestrator as default_orchestrator,
    OrchestratorResponse,
    OrchestrationStatus,
    ActionResult,
)
from core.interfaces.contract import (
    InterfaceRequest,
    InterfaceResponse,
    InterfaceType,
)
from core.security.context import (
    SecurityContext,
    SecurityContextError,
    create_trusted_context,
)
from core.security.identity import identity_manager
from core.security.session_manager import session_manager
from core.security.policy_engine import SecurityPolicyEngine, policy_engine
from core.security.policy import RiskTier, classify_risk
from core.security.approval_manager import ApprovalManager, approval_manager, ApprovalStatus
from core.security.audit_logger import audit_logger
from core.security.tool_registry import DefensiveToolRegistry, defensive_tool_registry
from core.security.result_validator import result_validator
from core.event_bus import event_bus, EventType
from core.gpu_manager import GPUManager
from core.health import HealthMonitor
from memory.manager import MemoryManager

logger = Config.get_logger(__name__)


class TaskPlan(BaseModel):
    """Decomposed execution plan for multi-step agent actions."""
    task_id: str = Field(default_factory=lambda: f"task_{secrets.token_hex(8)}")
    intent_type: str = "command"
    description: str = ""
    steps: list[dict[str, Any]] = Field(default_factory=list)
    estimated_risk: str = "low"
    requires_approval: bool = False
    context_needed: dict[str, bool] = Field(default_factory=dict)


class HostAgent:
    """
    HostAgent is the single coordinating authority across all client surfaces.
    No client surface, background routine, or sub-agent executes privileged
    actions without passing through this HostAgent pipeline.
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(
        self,
        orchestrator: Optional[SonOrchestrator] = None,
        memory_manager: Optional[MemoryManager] = None,
        intent_router: Optional[IntentRouter] = None,
    ):
        if getattr(self, "_initialized", False):
            return

        self.orchestrator = orchestrator or default_orchestrator
        self.memory = memory_manager or MemoryManager()
        self.intent_router = intent_router or IntentRouter()
        self.tool_registry = defensive_tool_registry
        self.policy_engine = policy_engine
        self.approval_manager = approval_manager
        self.event_bus = event_bus
        self.gpu_manager = GPUManager()
        self.health_monitor = HealthMonitor()

        self._initialized = True
        logger.info("HostAgent initialized as the central authority.")
        self.event_bus.publish(EventType.SON_READY, {"timestamp": time.time()}, source="host_agent")

    # ── Main Entrypoint: Process Normalized Request ─────────────────

    def process_request(
        self,
        request: Union[InterfaceRequest, str],
        user_id: str = "primary_user",
        session_id: Optional[str] = None,
        interface: str = "cli",
        conversation_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> InterfaceResponse:
        """
        Main execution gateway. Processes incoming requests through the full pipeline:
        Listen/Ingest → Classify → Plan → Memory → Validate → Execute → Verify → Respond
        """
        start_time = time.time()

        # 1. Normalize into strict InterfaceRequest
        try:
            if isinstance(request, str):
                req = InterfaceRequest(
                    user_id=user_id,
                    session_id=session_id,
                    interface=interface,
                    conversation_id=conversation_id,
                    message=request,
                    metadata=metadata or {},
                )
            else:
                req = request
        except Exception as ve:
            logger.warning(f"Request normalization validation failed: {ve}")
            return InterfaceResponse(
                request_id=f"req_{secrets.token_hex(8)}",
                status=OrchestrationStatus.AUTHENTICATION_ERROR,
                error=str(ve),
                response_text=f"Authentication Error: {ve}",
            )

        req_id = req.request_id
        msg = req.message.strip()

        # Publish request received event
        self.event_bus.publish(
            EventType.REQUEST_RECEIVED,
            {"message": msg, "interface": req.interface, "user_id": req.user_id},
            source="host_agent",
            session_id=req.session_id,
            request_id=req_id,
        )

        # 2. Authenticate Identity & Session Context
        try:
            sec_ctx = req.to_security_context()
            # Register or refresh session
            if req.session_id:
                session_manager.register_session(req.session_id, req.user_id, req.interface)
        except SecurityContextError as sce:
            logger.warning(f"SecurityContext validation failed: {sce}")
            return InterfaceResponse(
                request_id=req_id,
                status=OrchestrationStatus.AUTHENTICATION_ERROR,
                error=str(sce),
                response_text=f"Authentication Error: {sce}",
            )

        if not msg:
            return InterfaceResponse(
                request_id=req_id,
                status=OrchestrationStatus.SUCCESS,
                response_text="",
            )

        # 3. Intent Classification & Task Planning
        intent_res: IntentResult = self.intent_router.classify(msg)
        self.event_bus.publish(
            EventType.THINKING,
            {"intent": intent_res.intent.value, "confidence": intent_res.confidence},
            source="host_agent",
            session_id=req.session_id,
            request_id=req_id,
        )

        # 4. Context & Memory Retrieval Strategy
        # Deterministic commands bypass L3 vector search completely (<1ms)
        include_semantic = (intent_res.intent == IntentType.COMPLEX) and intent_res.needs_memory
        memory_context = ""
        try:
            memory_context = self.memory.build_context(msg, include_semantic=include_semantic)
        except Exception as me:
            logger.debug(f"Memory retrieval warning (non-fatal): {me}")

        # 5. Route to Orchestrator with Trusted SecurityContext
        # SonOrchestrator manages the defensive agent, policy engine, and action execution
        orch_res: OrchestratorResponse = self.orchestrator.process_request(
            message=msg,
            context=sec_ctx,
            memory_context=memory_context,
            intent_override=intent_res.intent.value,
        )

        # 6. Post-Execution Result Verification
        verified_results = []
        for act_res in orch_res.tool_results:
            is_valid, reason = result_validator.validate_output(act_res.output, act_res.tool_name)
            if not is_valid:
                act_res.success = False
                act_res.error = f"Result validation failed: {reason}"
            verified_results.append(act_res)
            self.event_bus.publish(
                EventType.TOOL_COMPLETED,
                {"tool_name": act_res.tool_name, "success": act_res.success, "risk_tier": act_res.risk_tier},
                source="host_agent",
                session_id=req.session_id,
                request_id=req_id,
            )

        # 7. Record Dialogue Turn in Memory
        if orch_res.status == OrchestrationStatus.SUCCESS and orch_res.response_text:
            try:
                self.memory.record_turn(msg, orch_res.response_text)
            except Exception as e:
                logger.debug(f"Memory recording error: {e}")

        # 8. Assemble Normalized InterfaceResponse
        duration_ms = (time.time() - start_time) * 1000.0
        response = InterfaceResponse(
            request_id=req_id,
            status=orch_res.status,
            response_text=orch_res.response_text or orch_res.text or "",
            tool_results=verified_results,
            pending_approval=orch_res.pending_approval,
            error=orch_res.error,
            execution_metadata={
                "intent": intent_res.intent.value,
                "duration_ms": duration_ms,
                "tools_executed": len(verified_results),
            },
        )

        self.event_bus.publish(
            EventType.REQUEST_COMPLETED,
            {"status": response.status.value, "duration_ms": duration_ms},
            source="host_agent",
            session_id=req.session_id,
            request_id=req_id,
        )

        return response

    # ── Direct Action Execution (Gated by Host Security) ─────────────

    def execute_action(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        context: Optional[SecurityContext] = None,
        approval_id: Optional[str] = None,
    ) -> ActionResult:
        """
        Execute an isolated action directly through the central security gate.
        """
        self.event_bus.publish(
            EventType.TOOL_STARTED,
            {"tool_name": tool_name, "arguments_keys": list(arguments.keys())},
            source="host_agent",
        )
        return self.orchestrator.execute_action(
            tool_name=tool_name,
            arguments=arguments,
            context=context,
            approval_id=approval_id,
        )

    # ── Approval Management ──────────────────────────────────────────

    def resolve_approval(
        self,
        approval_id: str,
        decision: bool,
        user_id: str = "primary_user",
        session_id: Optional[str] = None,
    ) -> OrchestratorResponse:
        """
        Resolve a pending cryptographic approval and execute if approved.
        """
        self.event_bus.publish(
            EventType.APPROVAL_RESOLVED,
            {"approval_id": approval_id, "decision": decision},
            source="host_agent",
            session_id=session_id,
        )
        ctx = create_trusted_context(user_id=user_id, interface_type="cli", session_id=session_id)
        return self.orchestrator.handle_approval(
            approval_id=approval_id,
            decision=decision,
            context=ctx,
        )

    # ── Subsystem State & Health ─────────────────────────────────────

    def get_status(self) -> dict[str, Any]:
        """Unified system status including GPU, Memory, and Service health."""
        gpu_metrics = self.gpu_manager.get_metrics()
        return {
            "version": "3.0.0",
            "host_agent": "ONLINE",
            "gpu": gpu_metrics,
            "registered_tools": len(self.tool_registry.list_tools()),
            "recent_events": len(self.event_bus.get_recent_events()),
            "services": self.health_monitor.get_status() if hasattr(self.health_monitor, "get_status") else {},
        }


# Global HostAgent singleton
host_agent = HostAgent()
