# tests/execution/test_path_security.py — Tests for Path Traversal & Security Boundaries
import os
from pathlib import Path
import tempfile
import zipfile
import pytest
from core.execution.tier1_native.filesystem import NativeFileSystem


@pytest.fixture
def fs():
    return NativeFileSystem()


def test_path_traversal_detection(fs):
    base = Path("C:\\AI\\SON")
    escaped = Path("C:\\AI\\SON\\..\\..\\Windows\\System32")
    ok, err = fs.validate_traversal(base, escaped)
    assert ok is False
    assert "Path traversal detected" in err


def test_valid_child_path(fs):
    base = Path("C:\\AI\\SON")
    child = Path("C:\\AI\\SON\\core\\execution")
    ok, err = fs.validate_traversal(base, child)
    assert ok is True


def test_protect_system_drive_roots(fs):
    is_prot, reason = fs.is_protected_path("C:\\")
    assert is_prot is True

    is_prot, reason = fs.is_protected_path("C:")
    assert is_prot is True


def test_protect_windows_directory(fs):
    is_prot, reason = fs.is_protected_path("C:\\Windows\\System32\\cmd.exe")
    assert is_prot is True


def test_protect_users_root(fs):
    is_prot, reason = fs.is_protected_path("C:\\Users")
    assert is_prot is True


def test_zip_slip_vulnerability_blocked(fs):
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create a malicious zip with traversal in filename
        malicious_zip = Path(tmp_dir) / "slip.zip"
        with zipfile.ZipFile(malicious_zip, "w") as z:
            z.writestr("../../../evil.txt", "pwned")

        extract_dst = Path(tmp_dir) / "extracted"
        res = fs.extract_zip(malicious_zip, extract_dst)
        assert res["success"] is False
        assert "Zip-Slip" in res["error"]
