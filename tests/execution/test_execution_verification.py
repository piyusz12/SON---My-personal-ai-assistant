# tests/execution/test_execution_verification.py — Tests for Post-Execution Verification
from pathlib import Path
import tempfile
import pytest
from core.execution.execution_router import execution_router
from core.execution.execution_result import ExecutionResult, ExecutionStatus


def test_verification_check_output_non_empty():
    res = execution_router.route("list_directory", {"path": "C:\\AI"})
    assert res.status == ExecutionStatus.SUCCESS
    assert res.verified is True


def test_verification_check_path_exists():
    with tempfile.TemporaryDirectory() as tmp_dir:
        test_file = str(Path(tmp_dir) / "verify_exists.txt")
        res = execution_router.route("create_file", {"path": test_file, "content": "verified"})
        assert res.status == ExecutionStatus.SUCCESS
        assert res.verified is True
        assert Path(test_file).exists()


def test_verification_check_path_gone():
    with tempfile.TemporaryDirectory() as tmp_dir:
        test_file = Path(tmp_dir) / "to_delete.txt"
        test_file.write_text("goodbye")
        res = execution_router.route("delete_file", {"path": str(test_file)})
        assert res.status == ExecutionStatus.SUCCESS
        assert res.verified is True
        assert not test_file.exists()


def test_verification_fails_on_execution_failure():
    res = execution_router.route("read_file", {"path": "C:\\Definitely_Not_A_File_987654321.txt"})
    assert res.status == ExecutionStatus.FAILURE
    assert res.verified is False
