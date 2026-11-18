# tests/execution/test_tier1_filesystem.py — Tests for Tier 1 File System
import os
from pathlib import Path
import tempfile
import pytest
from core.execution.tier1_native.filesystem import NativeFileSystem


@pytest.fixture
def fs():
    return NativeFileSystem()


def test_list_directory_valid(fs):
    res = fs.list_directory("C:\\AI")
    assert res["success"] is True
    assert res["count"] > 0
    assert any(e["name"] == "SON" for e in res["entries"])


def test_list_directory_nonexistent(fs):
    res = fs.list_directory("C:\\NonExistentPath_123456789")
    assert res["success"] is False
    assert "not found" in res["error"]


def test_read_file(fs):
    res = fs.read_file("C:\\AI\\SON\\pytest.ini")
    assert res["success"] is True
    assert "pytest" in res["content"]


def test_temp_file_lifecycle(fs):
    with tempfile.TemporaryDirectory() as tmp_dir:
        test_file = Path(tmp_dir) / "test_lifecycle.txt"

        # 1. Create
        c_res = fs.create_file(test_file, content="Hello SON Phase 2")
        assert c_res["success"] is True
        assert test_file.exists()

        # 2. Read
        r_res = fs.read_file(test_file)
        assert r_res["success"] is True
        assert r_res["content"] == "Hello SON Phase 2"

        # 3. Metadata
        m_res = fs.get_metadata(test_file)
        assert m_res["success"] is True
        assert m_res["is_file"] is True
        assert m_res["size_bytes"] > 0

        # 4. Copy
        copy_dst = Path(tmp_dir) / "test_copy.txt"
        cp_res = fs.copy_path(test_file, copy_dst)
        assert cp_res["success"] is True
        assert copy_dst.exists()

        # 5. Move
        move_dst = Path(tmp_dir) / "test_moved.txt"
        mv_res = fs.move_path(copy_dst, move_dst)
        assert mv_res["success"] is True
        assert move_dst.exists()
        assert not copy_dst.exists()

        # 6. Delete
        d_res = fs.delete_path(move_dst)
        assert d_res["success"] is True
        assert not move_dst.exists()


def test_zip_compress_and_extract(fs):
    with tempfile.TemporaryDirectory() as tmp_dir:
        src_dir = Path(tmp_dir) / "data_folder"
        src_dir.mkdir()
        (src_dir / "sample.txt").write_text("Zip compression test", encoding="utf-8")

        zip_dst = Path(tmp_dir) / "archive.zip"
        c_res = fs.compress_folder(src_dir, zip_dst)
        assert c_res["success"] is True
        assert zip_dst.exists()

        extract_dst = Path(tmp_dir) / "extracted"
        e_res = fs.extract_zip(zip_dst, extract_dst)
        assert e_res["success"] is True
        assert (extract_dst / "sample.txt").exists()


def test_protect_system_directories(fs):
    is_prot, reason = fs.is_protected_path("C:\\Windows")
    assert is_prot is True

    is_prot, reason = fs.is_protected_path("C:\\Program Files")
    assert is_prot is True

    is_prot, reason = fs.is_protected_path("C:\\")
    assert is_prot is True


def test_block_deletion_of_protected_system_dir(fs):
    res = fs.delete_path("C:\\Windows")
    assert res["success"] is False
    assert "Security Error" in res["error"]
