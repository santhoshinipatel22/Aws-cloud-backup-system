import os
import shutil
import tempfile
import pytest
from backup import backup_files


def test_backup_creates_directory(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "hello.txt").write_text("world")

    dest_parent = tmp_path / "dest"
    result = backup_files(str(src), str(dest_parent))

    assert os.path.isdir(result)
    assert os.path.isfile(os.path.join(result, "hello.txt"))
    assert open(os.path.join(result, "hello.txt")).read() == "world"


def test_missing_source_raises(tmp_path):
    dest_parent = tmp_path / "dest"
    with pytest.raises(ValueError):
        backup_files(str(tmp_path / "nope"), str(dest_parent))


def test_incremental_skips_unchanged(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.txt").write_text("1")

    dest = tmp_path / "dest"
    first = backup_files(str(src), str(dest))
    # modify file
    (src / "b.txt").write_text("2")
    second = backup_files(str(src), str(dest), incremental=True)

    assert os.path.isdir(second)
    assert os.path.exists(os.path.join(second, "b.txt"))
    # a.txt should also be copied because we compare to previous backup
    assert os.path.exists(os.path.join(second, "a.txt"))


def test_encrypt_available_or_skip(tmp_path):
    try:
        from backup import encrypt_directory
    except ImportError:
        pytest.skip("encryption support not installed")
    src = tmp_path / "src"
    src.mkdir()
    (src / "c.txt").write_text("3")
    dest_parent = tmp_path / "dest"
    backup_dir = backup_files(str(src), str(dest_parent))
    encrypted = encrypt_directory(backup_dir, "pass")
    assert encrypted.endswith(".enc")
    assert os.path.exists(encrypted)


def test_s3_upload_skipped(tmp_path, monkeypatch):
    try:
        import boto3
    except ImportError:
        pytest.skip("boto3 not installed")
    # monkeypatch upload_file to avoid real network
    class Dummy:
        def upload_file(self, Filename, Bucket, Key):
            assert os.path.exists(Filename)
            self.last = (Filename, Bucket, Key)
    monkeypatch.setattr(boto3, "client", lambda service: Dummy())
    src = tmp_path / "src"
    src.mkdir()
    (src / "d.txt").write_text("4")
    dest_parent = tmp_path / "dest"
    backup_dir = backup_files(str(src), str(dest_parent))

    from backup import upload_to_s3, upload_to_glacier
    key = upload_to_s3(backup_dir, "mybucket", "prefix/")
    assert key.startswith("prefix/")
    # glacier
    class DummyGlacier:
        def upload_archive(self, vaultName, body):
            assert vaultName == "myvault"
            return {"archiveId": "abc123"}
    monkeypatch.setattr(boto3, "client", lambda service: DummyGlacier())
    archive_id = upload_to_glacier(backup_dir, "myvault")
    assert archive_id == "abc123"
