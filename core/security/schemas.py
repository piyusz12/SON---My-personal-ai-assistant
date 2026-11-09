# core/security/schemas.py — Pydantic Schemas for Tool Argument Validation
"""
Strict Pydantic models for tool argument validation and execution contracts.
Enforces type safety, constraints, bounds, directory traversal prevention,
SSRF defense, and path integrity before tool dispatch.
"""

import ipaddress
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse
from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictToolParams(BaseModel):
    """Base parameter model forbidding extra/unexpected arguments to prevent parameter injection."""
    model_config = ConfigDict(extra="forbid")


# ══════════════════════════════════════════════════════════════
# Central Tool Execution Contracts
# ══════════════════════════════════════════════════════════════

class ToolExecutionRequest(BaseModel):
    """Central typed execution request contract for all tool operations."""
    request_id: str = Field(..., description="Unique request identifier.")
    user_id: str = Field(..., min_length=1, description="Authenticated user identifier.")
    session_id: str = Field(..., min_length=1, description="Cryptographic session identifier.")
    tool_name: str = Field(..., min_length=1, description="Registered tool name.")
    arguments: dict[str, Any] = Field(default_factory=dict, description="Tool invocation arguments.")
    risk_level: str = Field("low", description="Evaluated risk tier (read_only, low, medium, high, critical).")
    approval_request_id: Optional[str] = Field(None, description="Cryptographic approval request ID if required.")
    execution_timeout: float = Field(30.0, ge=0.01, le=600.0, description="Execution timeout in seconds.")
    execution_metadata: dict[str, Any] = Field(default_factory=dict, description="Metadata and tracing tags.")

    model_config = ConfigDict(extra="forbid")


class ToolExecutionResult(BaseModel):
    """Central typed execution result contract for all tool operations."""
    request_id: str = Field(..., description="Correlating request identifier.")
    tool_name: str = Field(..., description="Executed tool name.")
    status: str = Field(..., description="Execution status code (SUCCESS, ERROR, DENIED, TIMEOUT, etc.).")
    success: bool = Field(..., description="Whether execution completed successfully.")
    result: str = Field(..., description="Validated, sanitized result string.")
    error_code: Optional[str] = Field(None, description="Normalized error category or code.")
    execution_duration: float = Field(0.0, ge=0.0, description="Execution duration in seconds.")
    validation_status: str = Field("VALIDATED", description="Result validation status.")
    audit_reference: Optional[str] = Field(None, description="Cryptographic audit event ID or hash.")
    execution_metadata: dict[str, Any] = Field(default_factory=dict, description="Result metadata.")

    model_config = ConfigDict(extra="forbid")


# ══════════════════════════════════════════════════════════════
# Security Validation Helpers
# ══════════════════════════════════════════════════════════════

FORBIDDEN_WRITE_EXTENSIONS = {
    ".exe", ".dll", ".bat", ".cmd", ".vbs", ".vbe", ".js", ".jse",
    ".wsf", ".wsh", ".ps1", ".ps1xml", ".ps2", ".psc1", ".psc2",
    ".msh", ".msh1", ".msh2", ".mshxml", ".msh1xml", ".msh2xml",
    ".scf", ".lnk", ".inf", ".reg", ".pif", ".scr", ".cpl", ".msi", ".msp"
}

FORBIDDEN_SSRF_HOSTS = {
    "localhost", "127.0.0.1", "0.0.0.0", "::1",
    "169.254.169.254", "metadata.google.internal",
    "instance-data",
}


def _validate_safe_url(v: str) -> str:
    cleaned = v.strip()
    if not (cleaned.startswith("http://") or cleaned.startswith("https://")):
        raise ValueError("URL must start with http:// or https://")
    try:
        parsed = urlparse(cleaned)
        hostname = (parsed.hostname or "").lower()
        if not hostname:
            raise ValueError("URL must contain a valid hostname.")
        if hostname in FORBIDDEN_SSRF_HOSTS:
            raise ValueError(f"Access to private/metadata host '{hostname}' is forbidden (SSRF protection).")
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                raise ValueError(f"Access to private IP address '{hostname}' is forbidden (SSRF protection).")
        except ValueError:
            pass  # Normal domain name
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Invalid URL representation: {e}")
    return cleaned


# ══════════════════════════════════════════════════════════════
# Tool Parameter Models
# ══════════════════════════════════════════════════════════════

class ExecuteCodeParams(StrictToolParams):
    """Parameters for executing code in the E2B isolated sandbox."""
    code: str = Field(..., min_length=1, max_length=50000, description="Python code to execute inside the isolated sandbox.")
    timeout: int = Field(30, ge=1, le=300, description="Execution timeout in seconds.")


class ExecuteSandboxCommandParams(StrictToolParams):
    """Parameters for executing terminal command inside E2B isolated sandbox."""
    command: str = Field(..., min_length=1, max_length=2000, description="Terminal command to run inside sandbox.")
    timeout: int = Field(30, ge=1, le=300, description="Execution timeout in seconds.")


class ReadFileParams(StrictToolParams):
    """Parameters for reading a file safely."""
    path: str = Field(..., min_length=1, description="Path to the file to read.")
    max_lines: int = Field(200, ge=1, le=5000, description="Maximum number of lines to return.")

    @field_validator("path")
    @classmethod
    def validate_path(cls, v: str) -> str:
        cleaned = v.strip().strip("'\"")
        if not cleaned:
            raise ValueError("File path cannot be empty.")
        if "\x00" in cleaned:
            raise ValueError("File path cannot contain null bytes.")
        norm = cleaned.replace("\\", "/")
        if any(part == ".." for part in norm.split("/")):
            raise ValueError(f"Directory traversal sequence '..' is forbidden in '{cleaned}'.")
        return cleaned


class WriteFileParams(StrictToolParams):
    """Parameters for writing a file."""
    path: str = Field(..., min_length=1, description="Destination file path.")
    content: str = Field(..., max_length=1000000, description="Content to write.")

    @field_validator("path")
    @classmethod
    def validate_path(cls, v: str) -> str:
        cleaned = v.strip().strip("'\"")
        if not cleaned:
            raise ValueError("File path cannot be empty.")
        if "\x00" in cleaned:
            raise ValueError("File path cannot contain null bytes.")
        norm = cleaned.replace("\\", "/")
        if any(part == ".." for part in norm.split("/")):
            raise ValueError(f"Directory traversal sequence '..' is forbidden in '{cleaned}'.")

        # Reject executable/script extensions
        suffix = Path(cleaned).suffix.lower()
        if suffix in FORBIDDEN_WRITE_EXTENSIONS:
            raise ValueError(f"Writing executable or script files ({suffix}) is strictly forbidden.")

        # Reject attempts to overwrite protected Windows system roots directly
        try:
            resolved = str(Path(cleaned).resolve()).lower()
        except Exception:
            resolved = cleaned.lower()
        if "c:\\windows" in resolved or "system32" in resolved:
            raise ValueError(f"Writing to protected Windows system directory '{cleaned}' is forbidden.")
        return cleaned


class DeletePathParams(StrictToolParams):
    """Parameters for deleting a file or directory (HIGH RISK)."""
    path: str = Field(..., min_length=1, description="Target path to delete.")

    @field_validator("path")
    @classmethod
    def validate_path(cls, v: str) -> str:
        cleaned = v.strip().strip("'\"")
        if not cleaned:
            raise ValueError("Path to delete cannot be empty.")
        if "\x00" in cleaned:
            raise ValueError("Path cannot contain null bytes.")
        norm = cleaned.replace("\\", "/")
        if any(part == ".." for part in norm.split("/")):
            raise ValueError(f"Directory traversal sequence '..' is forbidden in '{cleaned}'.")

        # Block drive root or filesystem root deletions (e.g. C:\ or C: or /)
        try:
            resolved = Path(cleaned).resolve()
        except Exception:
            resolved = Path(cleaned)

        resolved_str = str(resolved).rstrip("\\/")
        anchor_str = str(resolved.anchor).rstrip("\\/") if hasattr(resolved, "anchor") else ""
        if (
            (anchor_str and resolved_str == anchor_str)
            or str(resolved).endswith(":\\")
            or str(resolved).endswith(":/")
            or cleaned.strip("\\/") in ("C:", "D:", "E:", "F:", "c:", "d:", "e:", "f:", "/")
        ):
            raise ValueError(f"Deleting drive root '{cleaned}' is strictly forbidden.")
        return cleaned


class OpenAppParams(StrictToolParams):
    """Parameters for opening an application."""
    name: str = Field(..., min_length=1, max_length=200, description="Application or workspace name.")


class CloseAppParams(StrictToolParams):
    """Parameters for closing an application (HIGH RISK)."""
    name: str = Field(..., min_length=1, max_length=100, description="Application name to terminate.")


class SetVolumeParams(StrictToolParams):
    """Parameters for setting system volume."""
    level: int = Field(..., ge=0, le=100, description="Volume level from 0 to 100.")


class SetBrightnessParams(StrictToolParams):
    """Parameters for setting screen brightness."""
    level: int = Field(..., ge=0, le=100, description="Brightness level from 0 to 100.")


class WebSearchParams(StrictToolParams):
    """Parameters for searching the web."""
    query: str = Field(..., min_length=1, max_length=500, description="Search query string.")
    max_results: int = Field(5, ge=1, le=20, description="Maximum number of search results.")


class ReadWebpageParams(StrictToolParams):
    """Parameters for reading a webpage."""
    url: str = Field(..., min_length=4, max_length=2000, description="HTTP/HTTPS URL of the webpage to read.")

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        return _validate_safe_url(v)


class ShutdownPCParams(StrictToolParams):
    """Parameters for system shutdown / restart (HIGH RISK)."""
    delay_seconds: int = Field(30, ge=0, le=3600, description="Delay in seconds before shutdown.")


class DatabaseQueryParams(StrictToolParams):
    """Parameters for executing a controlled SQL query."""
    query: str = Field(..., min_length=1, max_length=5000, description="SQL query string.")
    params: list = Field(default_factory=list, description="Parameterized values for SQL query.")


class ListDirectoryParams(StrictToolParams):
    """Parameters for listing an approved directory."""
    dir_path: str = Field(".", min_length=1, description="Path of the directory to list.")
    max_items: int = Field(100, ge=1, le=1000, description="Maximum number of items to return.")


class SearchFilesParams(StrictToolParams):
    """Parameters for searching files within approved workspaces."""
    pattern: str = Field(..., min_length=1, max_length=200, description="Glob search pattern, e.g. '*.py' or '*report*'.")
    root_dir: str = Field(".", min_length=1, description="Root directory to start searching from.")
    max_results: int = Field(50, ge=1, le=500, description="Maximum results to return.")


class GetWeatherParams(StrictToolParams):
    """Parameters for weather retrieval."""
    city: str = Field("auto", max_length=100, description="City name or 'auto' for current location.")


class GetNewsParams(StrictToolParams):
    """Parameters for news headline retrieval."""
    topic: str = Field("technology", max_length=100, description="Topic of interest.")


class OpenWebsiteParams(StrictToolParams):
    """Parameters for opening a website."""
    url: str = Field(..., min_length=1, max_length=2000, description="URL or domain to open in browser.")

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        return _validate_safe_url(v)


class DockerListContainersParams(StrictToolParams):
    """Parameters for listing Docker containers."""
    all: bool = Field(False, description="Whether to include stopped containers.")


class DockerContainerActionParams(StrictToolParams):
    """Parameters for Docker container start/stop/restart."""
    container: str = Field(..., min_length=1, max_length=200, description="Container name or ID.")


class GetSystemInfoParams(StrictToolParams):
    """Parameters for retrieving system metrics and host info."""
    category: str = Field("all", max_length=50, description="Category of system info requested.")


class TakeScreenshotParams(StrictToolParams):
    """Parameters for capturing a screenshot."""
    save_path: str | None = Field(None, max_length=500, description="Optional destination path for screenshot image.")


class OpenWhatsAppDraftParams(StrictToolParams):
    """Parameters for opening a confirmed WhatsApp draft."""
    url: str = Field(..., min_length=1, max_length=2000, description="Pre-validated Click-to-Chat URL.")
