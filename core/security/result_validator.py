# core/security/result_validator.py — Result Validation and Sanitization Pipeline
"""
Comprehensive Result Validation and Sanitization Engine for SON V3:
Enforces:
  1. Response size bounding (preventing buffer overflow or token exhaustion).
  2. Automatic secret/credential redaction in tool outputs.
  3. Artifact path canonicalization and existence verification.
  4. Isolation delimiter boundary wrapping for external resources.
  5. Untrusted tool output prompt-injection scanning and tagging.
  6. Structured audit logging for result validation events.
"""

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Optional
from pydantic import BaseModel, Field

from core.security.audit_logger import audit_logger, redact_secrets
from core.security.sanitizer import detect_prompt_injection, wrap_untrusted_content
from core.security.secure_file_service import secure_file_service

logger = logging.getLogger("son.security.result_validator")

# Maximum permitted tool output payload (512 KB)
MAX_TOOL_OUTPUT_BYTES = 512 * 1024

# Tools whose output originates from external/untrusted environments
UNTRUSTED_OUTPUT_TOOLS = {
    "read_file",
    "web_search",
    "read_webpage",
    "get_weather",
    "get_news",
    "database_query",
    "list_directory",
    "search_files",
    "execute_python_code",
    "execute_sandbox_command",
    "run_command",
    "run_terminal_command",
}


class ToolValidationResult(BaseModel):
    """Normalized outcome of tool result validation."""
    is_valid: bool = True
    sanitized_output: str
    original_length: int
    truncated: bool = False
    contains_secrets_redacted: bool = False
    contains_prompt_injection: bool = False
    artifact_path: Optional[str] = None
    validation_notes: list[str] = Field(default_factory=list)


class ResultValidator:
    """
    Validates, sanitizes, bounds, and redacts tool execution outputs
    prior to returning results to reasoning agents or presentation interfaces.
    """

    def __init__(self, max_output_bytes: int = MAX_TOOL_OUTPUT_BYTES):
        self.max_output_bytes = max_output_bytes

    def validate_and_sanitize(
        self,
        tool_name: str,
        raw_result: Any,
        session_id: str = "default_session",
        user_id: str = "primary_user",
        wrap_untrusted: bool | None = None,
    ) -> ToolValidationResult:
        """
        Full result validation lifecycle:
          1. Format normalization (dict/list to JSON string, None to 'Done.')
          2. Size constraint check and safe truncation
          3. Sensitive credential redaction
          4. Generated artifact path verification
          5. Prompt injection scanning
          6. Boundary delimiter wrapping for untrusted outputs
        """
        notes: list[str] = []

        # 1. Format normalization
        if raw_result is None:
            text = "Done."
        elif isinstance(raw_result, (dict, list)):
            try:
                text = json.dumps(raw_result, indent=2, default=str)
            except Exception:
                text = str(raw_result)
        else:
            text = str(raw_result)

        orig_len = len(text)

        # 2. Size limitation check
        truncated = False
        text_bytes = len(text.encode("utf-8", errors="replace"))
        if text_bytes > self.max_output_bytes:
            truncated = True
            # Safe truncation
            cutoff = self.max_output_bytes // 2
            text = (
                text[:cutoff]
                + f"\n\n[OUTPUT TRUNCATED: Result exceeded maximum permitted limit of {self.max_output_bytes // 1024} KB. "
                f"Original size: {text_bytes // 1024} KB]"
            )
            notes.append(f"Output truncated from {text_bytes} bytes to limit.")
            audit_logger.log_event(
                event_type="TOOL_RESULT_OVERSIZED_TRUNCATED",
                tool_name=tool_name,
                actor=user_id,
                session_id=session_id,
                status="TRUNCATED",
                details={"original_bytes": text_bytes, "max_bytes": self.max_output_bytes},
            )

        # 3. Secret and credential redaction
        redacted = redact_secrets(text)
        secrets_found = redacted != text
        if secrets_found:
            notes.append("Sensitive secrets or API tokens were redacted from output.")
            audit_logger.log_event(
                event_type="TOOL_RESULT_SECRETS_REDACTED",
                tool_name=tool_name,
                actor=user_id,
                session_id=session_id,
                status="REDACTED",
            )
            text = redacted

        # 4. Artifact existence and path validation
        artifact_path: Optional[str] = None
        if tool_name in ("take_screenshot", "write_file"):
            # Extract path from result if present
            match = re.search(r'(?:saved to|written to|path):\s*([^\s\n\r]+)', text, re.IGNORECASE)
            if match:
                candidate_path = match.group(1).strip("'\"")
                try:
                    p = Path(candidate_path)
                    if p.exists():
                        artifact_path = str(p.resolve())
                        notes.append(f"Verified generated artifact at {artifact_path}")
                    else:
                        notes.append(f"Referenced artifact does not exist: {candidate_path}")
                except Exception as e:
                    notes.append(f"Artifact path validation error: {e}")

        # 5. Prompt injection scanning in output
        has_injection, detected_rules = detect_prompt_injection(text)
        if has_injection:
            notes.append(f"Potential prompt injection detected: {', '.join(detected_rules)}")
            audit_logger.log_event(
                event_type="TOOL_OUTPUT_PROMPT_INJECTION_FLAGGED",
                tool_name=tool_name,
                actor=user_id,
                session_id=session_id,
                status="FLAGGED",
                details={"detected_rules": detected_rules, "tool": tool_name},
            )

        # 6. Untrusted delimiter boundary wrapping
        should_wrap = wrap_untrusted if wrap_untrusted is not None else (tool_name in UNTRUSTED_OUTPUT_TOOLS)
        if should_wrap:
            text = wrap_untrusted_content(
                content=text,
                source=f"tool:{tool_name}",
                source_type="tool_output",
                session_id=session_id,
            )

        return ToolValidationResult(
            is_valid=True,
            sanitized_output=text,
            original_length=orig_len,
            truncated=truncated,
            contains_secrets_redacted=secrets_found,
            contains_prompt_injection=has_injection,
            artifact_path=artifact_path,
            validation_notes=notes,
        )


# Global validator instance
result_validator = ResultValidator()

