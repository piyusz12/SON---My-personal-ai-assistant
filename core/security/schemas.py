# core/security/schemas.py — Pydantic Schemas for Tool Argument Validation
"""
Strict Pydantic models for tool argument validation.
Enforces type safety, constraints, bounds, and path integrity before tool dispatch.
"""

from pathlib import Path
from pydantic import BaseModel, Field, field_validator


class ExecuteCodeParams(BaseModel):
    """Parameters for executing code in the E2B isolated sandbox."""
    code: str = Field(..., min_length=1, max_length=50000, description="Python code to execute inside the isolated sandbox.")
    timeout: int = Field(30, ge=1, le=300, description="Execution timeout in seconds.")


class ExecuteSandboxCommandParams(BaseModel):
    """Parameters for executing terminal command inside E2B isolated sandbox."""
    command: str = Field(..., min_length=1, max_length=2000, description="Terminal command to run inside sandbox.")
    timeout: int = Field(30, ge=1, le=300, description="Execution timeout in seconds.")


class ReadFileParams(BaseModel):
    """Parameters for reading a file safely."""
    path: str = Field(..., min_length=1, description="Path to the file to read.")
    max_lines: int = Field(200, ge=1, le=5000, description="Maximum number of lines to return.")

    @field_validator("path")
    @classmethod
    def validate_path(cls, v: str) -> str:
        cleaned = v.strip().strip("'\"")
        if not cleaned:
            raise ValueError("File path cannot be empty.")
        return cleaned


class WriteFileParams(BaseModel):
    """Parameters for writing a file."""
    path: str = Field(..., min_length=1, description="Destination file path.")
    content: str = Field(..., max_length=1000000, description="Content to write.")

    @field_validator("path")
    @classmethod
    def validate_path(cls, v: str) -> str:
        cleaned = v.strip().strip("'\"")
        if not cleaned:
            raise ValueError("File path cannot be empty.")
        # Reject attempts to overwrite protected Windows system roots directly
        try:
            resolved = str(Path(cleaned).resolve()).lower()
        except Exception:
            resolved = cleaned.lower()
        if "c:\\windows" in resolved or "system32" in resolved:
            raise ValueError(f"Writing to protected Windows system directory '{cleaned}' is forbidden.")
        return cleaned


class DeletePathParams(BaseModel):
    """Parameters for deleting a file or directory (HIGH RISK)."""
    path: str = Field(..., min_length=1, description="Target path to delete.")

    @field_validator("path")
    @classmethod
    def validate_path(cls, v: str) -> str:
        cleaned = v.strip().strip("'\"")
        if not cleaned:
            raise ValueError("Path to delete cannot be empty.")
        # Block drive root deletions (e.g. C:\ or C:)
        try:
            resolved = Path(cleaned).resolve()
        except Exception:
            resolved = Path(cleaned)
        if resolved == resolved.anchor or str(resolved).endswith(":\\") or cleaned.strip("\\/") in ("C:", "D:", "c:", "d:"):
            raise ValueError(f"Deleting drive root '{cleaned}' is strictly forbidden.")
        return cleaned


class OpenAppParams(BaseModel):
    """Parameters for opening an application."""
    name: str = Field(..., min_length=1, max_length=200, description="Application or workspace name.")


class CloseAppParams(BaseModel):
    """Parameters for closing an application (HIGH RISK)."""
    name: str = Field(..., min_length=1, max_length=100, description="Application name to terminate.")


class SetVolumeParams(BaseModel):
    """Parameters for setting system volume."""
    level: int = Field(..., ge=0, le=100, description="Volume level from 0 to 100.")


class SetBrightnessParams(BaseModel):
    """Parameters for setting screen brightness."""
    level: int = Field(..., ge=0, le=100, description="Brightness level from 0 to 100.")


class WebSearchParams(BaseModel):
    """Parameters for searching the web."""
    query: str = Field(..., min_length=1, max_length=500, description="Search query string.")
    max_results: int = Field(5, ge=1, le=20, description="Maximum number of search results.")


class ReadWebpageParams(BaseModel):
    """Parameters for reading a webpage."""
    url: str = Field(..., min_length=4, max_length=2000, description="HTTP/HTTPS URL of the webpage to read.")

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        cleaned = v.strip()
        if not (cleaned.startswith("http://") or cleaned.startswith("https://")):
            raise ValueError("URL must start with http:// or https://")
        return cleaned


class ShutdownPCParams(BaseModel):
    """Parameters for system shutdown / restart (HIGH RISK)."""
    delay_seconds: int = Field(30, ge=0, le=3600, description="Delay in seconds before shutdown.")
