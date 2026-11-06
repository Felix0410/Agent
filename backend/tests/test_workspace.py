"""临时目录/数据库验证上传安全，不读取真实用户文件。"""

import asyncio
import hashlib
import io
import os
from contextlib import asynccontextmanager
from uuid import uuid4

import pytest

from minideerflow.runtime.db import RuntimeDatabase
from minideerflow.runtime.repository import RuntimeRepository
from minideerflow.workspace.models import WorkspaceError, validate_filename
from minideerflow.workspace.repository import WorkspaceRepository
from minideerflow.workspace.service import WorkspaceService
from minideerflow.workspace.storage import WorkspaceStorage


class Upload:
    def __init__(self, data=b"hello", filename="notes.md"):
        self.data = io.BytesIO(data)
        self.filename = filename
        self.read_sizes = []

    async def read(self, size):
        self.read_sizes.append(size)
        return self.data.read(size)


@asynccontextmanager
async def workspace(tmp_path):
    db = await RuntimeDatabase.open(tmp_path / "runtime.db")
    await db.init_schema()
    storage = WorkspaceStorage(tmp_path / "workspaces")
    storage.open()
    repo = WorkspaceRepository(db)
    service = WorkspaceService(repo, storage)
    runtime = RuntimeRepository(db)
    try:
        yield service, runtime, storage
    finally:
        storage.close()
        await db.close()


def test_upload_unicode_stream_and_metadata(tmp_path):
    async def scenario():
        async with workspace(tmp_path) as (service, runtime, storage):
            thread = await runtime.create_thread()
            data = ("中" * 23000).encode()
            upload = Upload(data, "笔记.md")
            record = await service.upload(thread.id, upload)
            assert (
                record.size_bytes == len(data) and record.sha256 == hashlib.sha256(data).hexdigest()
            )
            assert all(size == 65536 for size in upload.read_sizes)
            assert "storage_key" not in record.model_dump() and "run_id" not in record.model_dump()
            names = list((storage.root / thread.id).iterdir())
            assert len(names) == 1 and names[0].name == record.storage_key
            assert names[0].stat().st_mode & 0o777 == 0o600
            assert (storage.root / thread.id).stat().st_mode & 0o777 == 0o700
            assert storage.read_registered(record) == data
            assert (await service.list_files(thread.id))[0].id == record.id

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "filename",
    [
        "../x.txt",
        "/tmp/x.txt",
        "a/b.txt",
        "a\\b.txt",
        "a..txt",
        "C:x.txt",
        " x.txt",
        "x.txt ",
        "a\x00.txt",
        "a\n.txt",
        ".",
        "..",
        "x" * 121,
    ],
)
def test_reject_unsafe_names(filename):
    with pytest.raises(WorkspaceError) as error:
        validate_filename(filename)
    assert error.value.code == "INVALID_FILENAME"


@pytest.mark.parametrize(
    ("data", "name", "code"),
    [
        (b"\xff", "notes.md", "INVALID_FILE_CONTENT"),
        (b"\x00", "notes.txt", "INVALID_FILE_CONTENT"),
        (b"not PDF", "notes.pdf", "INVALID_FILE_CONTENT"),
        (b"x", "x.exe", "UNSUPPORTED_FILE_TYPE"),
        (b"x" * (2 * 1024 * 1024 + 1), "large.txt", "FILE_TOO_LARGE"),
        (b"%PDF-" + b"x" * (10 * 1024 * 1024), "large.pdf", "FILE_TOO_LARGE"),
    ],
)
def test_invalid_uploads_clean_new_files(tmp_path, data, name, code):
    async def scenario():
        async with workspace(tmp_path) as (service, runtime, storage):
            thread = await runtime.create_thread()
            with pytest.raises(WorkspaceError) as error:
                await service.upload(thread.id, Upload(data, name))
            assert error.value.code == code
            assert await service.list_files(thread.id) == []
            assert not list((storage.root / thread.id).glob("*"))

    asyncio.run(scenario())


def test_thread_directory_symlink_cannot_escape(tmp_path):
    async def scenario():
        async with workspace(tmp_path) as (service, runtime, storage):
            thread = await runtime.create_thread()
            outside = tmp_path / "outside"
            outside.mkdir()
            (storage.root / thread.id).symlink_to(outside, target_is_directory=True)
            with pytest.raises(WorkspaceError):
                await service.upload(thread.id, Upload())
            assert list(outside.iterdir()) == []

    asyncio.run(scenario())


def test_root_symlink_rejected(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    root = tmp_path / "alias"
    root.symlink_to(outside, target_is_directory=True)
    with pytest.raises(WorkspaceError):
        WorkspaceStorage(root).open()
    assert list(outside.iterdir()) == []


@pytest.mark.parametrize("replace_root", [False, True])
def test_directory_replacement_race_fails_closed(tmp_path, monkeypatch, replace_root):
    original = os.link

    async def scenario():
        async with workspace(tmp_path) as (service, runtime, storage):
            thread = await runtime.create_thread()
            outside = tmp_path / "outside"
            outside.mkdir()
            moved = tmp_path / "moved"

            def replace_then_link(*args, **kwargs):
                target = storage.root if replace_root else storage.root / thread.id
                target.rename(moved)
                target.symlink_to(outside, target_is_directory=True)
                return original(*args, **kwargs)

            monkeypatch.setattr(os, "link", replace_then_link)
            with pytest.raises(WorkspaceError):
                await service.upload(thread.id, Upload())
            assert list(outside.iterdir()) == []
            assert (
                not list(moved.rglob("*"))
                if not replace_root
                else not list((moved / thread.id).iterdir())
            )
            assert await service.list_files(thread.id) == []

    asyncio.run(scenario())


def test_no_clobber_publication_preserves_existing_file(tmp_path, monkeypatch):
    from minideerflow.workspace import storage as module

    class Fixed:
        hex = "a" * 32

    async def scenario():
        async with workspace(tmp_path) as (service, runtime, storage):
            thread = await runtime.create_thread()
            directory = storage.root / thread.id
            directory.mkdir(mode=0o700)
            existing = directory / Fixed.hex
            existing.write_bytes(b"old")
            monkeypatch.setattr(module, "uuid4", lambda: Fixed())
            with pytest.raises(WorkspaceError):
                await service.upload(thread.id, Upload())
            assert existing.read_bytes() == b"old"
            assert [p.name for p in directory.iterdir()] == [Fixed.hex]

    asyncio.run(scenario())


@pytest.mark.parametrize("mode", ["symlink", "hardlink", "changed"])
def test_registered_read_rejects_substitution(tmp_path, mode):
    async def scenario():
        async with workspace(tmp_path) as (service, runtime, storage):
            thread = await runtime.create_thread()
            record = await service.upload(thread.id, Upload())
            path = storage.root / thread.id / record.storage_key
            outside = tmp_path / "outside"
            outside.write_bytes(b"hello")
            if mode == "symlink":
                path.unlink()
                path.symlink_to(outside)
            elif mode == "hardlink":
                os.link(path, tmp_path / "alias")
            else:
                path.write_bytes(b"other")
            with pytest.raises(WorkspaceError):
                storage.read_registered(record)
            assert outside.read_bytes() == b"hello"

    asyncio.run(scenario())


@pytest.mark.parametrize("cancel", [False, True])
def test_registration_failure_and_cancel_cleanup(tmp_path, monkeypatch, cancel):
    async def scenario():
        async with workspace(tmp_path) as (service, runtime, storage):
            thread = await runtime.create_thread()

            async def fail(record):
                if cancel:
                    raise asyncio.CancelledError
                raise RuntimeError("private database detail")

            monkeypatch.setattr(service.repository, "register_upload", fail)
            with pytest.raises(asyncio.CancelledError if cancel else WorkspaceError):
                await service.upload(thread.id, Upload())
            assert not list((storage.root / thread.id).iterdir())
            assert await service.list_files(thread.id) == []

    asyncio.run(scenario())


def test_interrupted_upload_cleans_temporary_file(tmp_path):
    class Interrupted(Upload):
        calls = 0

        async def read(self, size):
            self.calls += 1
            if self.calls == 2:
                raise asyncio.CancelledError
            return b"partial"

    async def scenario():
        async with workspace(tmp_path) as (service, runtime, storage):
            thread = await runtime.create_thread()
            with pytest.raises(asyncio.CancelledError):
                await service.upload(thread.id, Interrupted())
            assert not list((storage.root / thread.id).iterdir())

    asyncio.run(scenario())


def test_count_quota_and_same_upload_name_allowed(tmp_path):
    async def scenario():
        async with workspace(tmp_path) as (service, runtime, storage):
            thread = await runtime.create_thread()
            for _ in range(50):
                await service.upload(thread.id, Upload(b""))
            assert len(await service.list_files(thread.id)) == 50
            with pytest.raises(WorkspaceError) as error:
                await service.upload(thread.id, Upload())
            assert error.value.code == "WORKSPACE_QUOTA_EXCEEDED"
            assert len(list((storage.root / thread.id).iterdir())) == 50

    asyncio.run(scenario())


def test_pdf_signature_and_total_bytes_quota(tmp_path):
    async def scenario():
        async with workspace(tmp_path) as (service, runtime, _storage):
            thread = await runtime.create_thread()
            data = b"%PDF-" + b"x" * (10 * 1024 * 1024 - 5)
            for _ in range(3):
                file = await service.upload(thread.id, Upload(data, "file.pdf"))
                assert file.mime == "application/pdf"
            with pytest.raises(WorkspaceError) as error:
                await service.upload(thread.id, Upload())
            assert error.value.code == "WORKSPACE_QUOTA_EXCEEDED"
            assert len(await service.list_files(thread.id)) == 3

    asyncio.run(scenario())


def test_unknown_thread_never_creates_directory(tmp_path):
    async def scenario():
        async with workspace(tmp_path) as (service, _runtime, storage):
            with pytest.raises(WorkspaceError) as error:
                await service.upload(str(uuid4()), Upload())
            assert error.value.code == "THREAD_NOT_FOUND"
            assert list(storage.root.iterdir()) == []

    asyncio.run(scenario())
