# core/security/__init__.py — SON Defensive Security Architecture Package
from core.security.policy import (
    RiskTier,
    POLICY_VERSION,
    SYSTEM_INSTRUCTIONS_POLICY,
    classify_risk,
)
from core.security.audit_logger import (
    SecurityAuditLogger,
    audit_logger,
    redact_secrets,
    canonical_args_hash,
)
from core.security.approval_manager import (
    ApprovalStatus,
    ApprovalRequest,
    ApprovalManager,
    approval_manager,
)
from core.security.sanitizer import (
    detect_prompt_injection,
    escape_untrusted_delimiters,
    wrap_untrusted_content,
)
from core.security.schemas import (
    ExecuteCodeParams,
    ExecuteSandboxCommandParams,
    ReadFileParams,
    WriteFileParams,
    DeletePathParams,
    OpenAppParams,
    CloseAppParams,
    SetVolumeParams,
    SetBrightnessParams,
    WebSearchParams,
    ReadWebpageParams,
    ShutdownPCParams,
)
from core.security.tool_registry import (
    DefensiveToolRegistry,
    defensive_tool_registry,
)
from core.security.pydantic_agent import (
    DefensivePydanticAgent,
)

__all__ = [
    "RiskTier",
    "POLICY_VERSION",
    "SYSTEM_INSTRUCTIONS_POLICY",
    "classify_risk",
    "SecurityAuditLogger",
    "audit_logger",
    "redact_secrets",
    "canonical_args_hash",
    "ApprovalStatus",
    "ApprovalRequest",
    "ApprovalManager",
    "approval_manager",
    "detect_prompt_injection",
    "escape_untrusted_delimiters",
    "wrap_untrusted_content",
    "ExecuteCodeParams",
    "ExecuteSandboxCommandParams",
    "ReadFileParams",
    "WriteFileParams",
    "DeletePathParams",
    "OpenAppParams",
    "CloseAppParams",
    "SetVolumeParams",
    "SetBrightnessParams",
    "WebSearchParams",
    "ReadWebpageParams",
    "ShutdownPCParams",
    "DefensiveToolRegistry",
    "defensive_tool_registry",
    "DefensivePydanticAgent",
]

