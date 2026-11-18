# core/execution/execution_result.py — Execution Router Result Schemas
"""
Structured results, tier definitions, and routing decisions for SON V3 Phase 2.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class TierLevel(str, Enum):
    """Four execution tiers of SON V3."""
    TIER1_NATIVE = "tier1_native"      # Native Win32 APIs, ctypes, psutil, python stdlib
    TIER2_SHELL = "tier2_shell"        # Controlled PowerShell & CLI with strict templates
    TIER3_UIA = "tier3_uia"            # Windows UI Automation (Phase 3)
    TIER4_VISUAL = "tier4_visual"      # Visual Computer Use & Grounding (Phase 4)


class ExecutionStatus(str, Enum):
    """Outcome status of an execution attempt."""
    SUCCESS = "success"
    FAILURE = "failure"
    DENIED = "denied"
    TIMEOUT = "timeout"
    PENDING_APPROVAL = "pending_approval"
    UNAVAILABLE = "unavailable"


@dataclass
class RoutingDecision:
    """Detailed decision made by the ExecutionRouter for a given tool/operation."""
    operation: str
    tier: TierLevel
    adapter: str
    tool_name: str
    arguments: Dict[str, Any]
    permission_level: str              # READ / LOCAL_REVERSIBLE / HIGH_IMPACT / DENIED
    timeout_seconds: float
    verification_strategy: str
    requires_approval: bool = False
    reason: str = ""


@dataclass
class ExecutionResult:
    """Standardized result returned by ExecutionRouter and all tier adapters."""
    status: ExecutionStatus
    output: Any = None
    error: Optional[str] = None
    tier_used: Optional[TierLevel] = None
    tool_name: str = ""
    duration_ms: float = 0.0
    routing_decision: Optional[RoutingDecision] = None
    audit_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    verified: bool = False

    @property
    def is_success(self) -> bool:
        return self.status == ExecutionStatus.SUCCESS

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "output": self.output,
            "error": self.error,
            "tier_used": self.tier_used.value if self.tier_used else None,
            "tool_name": self.tool_name,
            "duration_ms": self.duration_ms,
            "verified": self.verified,
            "metadata": self.metadata,
        }
