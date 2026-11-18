# core/execution/execution_router.py — Central Four-Tier Execution Router for SON V3
"""
Central Four-Tier Execution Router for SON V3.
Directs tool and Windows operations to the most reliable available tier:
  Tier 1: Native Windows APIs (ctypes, psutil, pathlib, win32)
  Tier 2: Controlled PowerShell & CLI Engine (strict allowlist, templates, shell=False)
  Tier 3: Windows UI Automation (Phase 3 — explicit interface, returns UNAVAILABLE)
  Tier 4: Visual Computer Use (Phase 4 — explicit interface, returns UNAVAILABLE)

All executions pass through the existing security pipeline (PolicyEngine,
ApprovalManager, DefensiveToolRegistry, ActionExecutor).
"""
import logging
import os
from pathlib import Path
import time
from typing import Any, Callable, Dict, Optional

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
from core.execution.tier1_native import NativeTier
from core.execution.tier2_shell import ShellTier

logger = logging.getLogger(__name__)


class ExecutionRouter:
    """
    Central Execution Router for SON V3.
    Governs tier selection, policy enforcement, timeout bounding, and post-execution verification.
    """

    def __init__(self):
        self._tier1: Optional[NativeTier] = None
        self._tier2: Optional[ShellTier] = None
        self._initialized = False

    def initialize(self):
        """Lazily initialize execution tier adapters."""
        if self._initialized:
            return

        try:
            self._tier1 = NativeTier()
            logger.info("[ExecutionRouter] Tier 1 (Native) initialized.")
        except Exception as e:
            logger.error(f"[ExecutionRouter] Failed to initialize Tier 1: {e}")

        try:
            self._tier2 = ShellTier()
            logger.info("[ExecutionRouter] Tier 2 (Shell) initialized.")
        except Exception as e:
            logger.error(f"[ExecutionRouter] Failed to initialize Tier 2: {e}")

        self._initialized = True

    @property
    def tier1(self) -> NativeTier:
        if not self._initialized:
            self.initialize()
        if not self._tier1:
            raise RuntimeError("Tier 1 Native adapter is not available.")
        return self._tier1

    @property
    def tier2(self) -> ShellTier:
        if not self._initialized:
            self.initialize()
        if not self._tier2:
            raise RuntimeError("Tier 2 Shell adapter is not available.")
        return self._tier2

    def select_tier(self, tool_name: str, arguments: Dict[str, Any]) -> OperationPolicy:
        """Helper to get policy for tool."""
        return get_policy(tool_name)

    def route(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        context: Optional[ExecutionContext] = None,
    ) -> ExecutionResult:
        """
        Primary execution entry point.
        Evaluates policy, selects tier, bounds timeout, executes through adapter,
        and verifies the outcome deterministically.
        """
        if not self._initialized:
            self.initialize()

        ctx = context or ExecutionContext()
        policy = get_policy(tool_name)
        start_time = time.perf_counter()

        # Build formal routing decision
        timeout = min(policy.timeout_seconds, ctx.timeout_seconds)
        decision = RoutingDecision(
            operation=tool_name,
            tier=policy.preferred_tier,
            adapter=policy.preferred_tier.value,
            tool_name=tool_name,
            arguments=arguments,
            permission_level=policy.permission_level,
            timeout_seconds=timeout,
            verification_strategy=policy.verification_strategy,
            requires_approval=policy.requires_approval,
            reason=policy.description,
        )

        logger.info(
            f"[ExecutionRouter] Routing '{tool_name}' -> {policy.preferred_tier.value} "
            f"[{policy.permission_level}] (approval={policy.requires_approval})"
        )

        # 1. Gate: Strictly DENIED operations fail-closed immediately
        if policy.permission_level == DENIED:
            duration_ms = (time.perf_counter() - start_time) * 1000
            return ExecutionResult(
                status=ExecutionStatus.DENIED,
                error=f"Operation '{tool_name}' is in the DENIED risk tier and cannot be executed.",
                tier_used=policy.preferred_tier,
                tool_name=tool_name,
                duration_ms=duration_ms,
                routing_decision=decision,
                verified=False,
            )

        # 2. Gate: Check timeout on context
        if ctx.is_expired():
            duration_ms = (time.perf_counter() - start_time) * 1000
            return ExecutionResult(
                status=ExecutionStatus.TIMEOUT,
                error="Execution context expired before tool launch.",
                tier_used=policy.preferred_tier,
                tool_name=tool_name,
                duration_ms=duration_ms,
                routing_decision=decision,
                verified=False,
            )

        # 3. Route according to selected tier
        result: ExecutionResult
        try:
            if policy.preferred_tier == TierLevel.TIER1_NATIVE:
                result = self.tier1.execute(tool_name, arguments, ctx)

            elif policy.preferred_tier == TierLevel.TIER2_SHELL:
                result = self.tier2.execute(tool_name, arguments, ctx)

            elif policy.preferred_tier == TierLevel.TIER3_UIA:
                # Explicit Tier 3 interface — reports unavailable
                result = ExecutionResult(
                    status=ExecutionStatus.UNAVAILABLE,
                    error="Tier 3 (Windows UI Automation) is not yet implemented. This capability will be available in Phase 3.",
                    tier_used=TierLevel.TIER3_UIA,
                    tool_name=tool_name,
                    routing_decision=decision,
                )

            elif policy.preferred_tier == TierLevel.TIER4_VISUAL:
                # Explicit Tier 4 interface — reports unavailable
                result = ExecutionResult(
                    status=ExecutionStatus.UNAVAILABLE,
                    error="Tier 4 (Visual Computer Use) is not yet implemented. This capability will be available in Phase 4.",
                    tier_used=TierLevel.TIER4_VISUAL,
                    tool_name=tool_name,
                    routing_decision=decision,
                )

            else:
                result = ExecutionResult(
                    status=ExecutionStatus.FAILURE,
                    error=f"Unknown execution tier: {policy.preferred_tier}",
                    tool_name=tool_name,
                    routing_decision=decision,
                )

        except Exception as e:
            logger.exception(f"[ExecutionRouter] Unexpected error executing '{tool_name}': {e}")
            result = ExecutionResult(
                status=ExecutionStatus.FAILURE,
                error=str(e),
                tier_used=policy.preferred_tier,
                tool_name=tool_name,
                routing_decision=decision,
            )

        # 4. Attach routing decision and total duration
        result.routing_decision = decision
        result.duration_ms = (time.perf_counter() - start_time) * 1000

        # 5. Deterministic Outcome Verification
        result.verified = self._verify_outcome(tool_name, arguments, result, policy.verification_strategy)
        if not result.verified and result.status == ExecutionStatus.SUCCESS:
            logger.warning(f"[ExecutionRouter] Post-execution verification failed for '{tool_name}' ({policy.verification_strategy})")

        return result

    def _verify_outcome(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        result: ExecutionResult,
        strategy: str,
    ) -> bool:
        """Verify that the action actually produced its intended state change."""
        if result.status != ExecutionStatus.SUCCESS:
            return False

        try:
            if strategy == "check_no_error":
                return result.error is None

            elif strategy == "check_output_non_empty":
                return result.output is not None and bool(str(result.output).strip())

            elif strategy == "check_path_exists":
                target = arguments.get("path") or arguments.get("destination") or arguments.get("zip_path") or arguments.get("extract_to")
                if target:
                    return Path(target).exists()
                return True

            elif strategy == "check_path_gone":
                target = arguments.get("path")
                if target:
                    return not Path(target).exists()
                return True

            elif strategy == "check_process_started":
                app_name = arguments.get("name")
                if app_name and self._tier1:
                    time.sleep(0.2)
                    check = self._tier1.process.is_app_running(app_name)
                    return check.get("running", True)
                return True

            return True
        except Exception as e:
            logger.debug(f"[ExecutionRouter] Verification exception: {e}")
            return False


# Global ExecutionRouter singleton
execution_router = ExecutionRouter()
