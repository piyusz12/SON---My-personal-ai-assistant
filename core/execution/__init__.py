# core/execution/__init__.py — Four-Tier Execution Architecture
"""
Execution Router and Multi-Tier Windows OS Spine for SON V3 Phase 2.
Exporting ExecutionRouter, ExecutionContext, ExecutionResult, ExecutionPolicy, TierLevel.
"""
from core.execution.execution_context import ExecutionContext
from core.execution.execution_policy import (
    DENIED,
    HIGH_IMPACT,
    LOCAL_REVERSIBLE,
    READ,
    OperationPolicy,
    get_policy,
)
from core.execution.execution_result import (
    ExecutionResult,
    ExecutionStatus,
    RoutingDecision,
    TierLevel,
)
from core.execution.execution_router import ExecutionRouter, execution_router

__all__ = [
    "ExecutionRouter",
    "execution_router",
    "ExecutionContext",
    "ExecutionResult",
    "ExecutionStatus",
    "RoutingDecision",
    "TierLevel",
    "OperationPolicy",
    "get_policy",
    "READ",
    "LOCAL_REVERSIBLE",
    "HIGH_IMPACT",
    "DENIED",
]
