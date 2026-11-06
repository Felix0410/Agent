"""文件HTTP使用临时Workspace，无模型也可独立工作。"""

import hashlib

import pytest
from fastapi.testclient import TestClient

from minideerflow.main import create_app


def test_upload_list_and_reopen():
    app = create_app()
    with TestClient(app) as client:
        thread = client.post("/api/threads", json={}).json()["id"]
        data = "临时样例".encode()
        response = client.post(
            f"/api/threads/{thread}/files",
            files={"file": ("notes.md", data, "application/x-wrong")},
        )
        assert response.status_code == 201
        file = response.json()
        assert (
            file["mime"] == "text/markdown" and file["sha256"] == hashlib.sha256(data).hexdigest()
        )
        assert "storage_key" not in file and "run_id" not in file
        assert client.get(f"/api/threads/{thread}/files").json() == [file]
        assert client.get("/health").status_code == 200
    with TestClient(create_app()) as client:
        assert client.get(f"/api/threads/{thread}/files").json() == [file]


@pytest.mark.parametrize(
    ("filename", "data", "code"),
    [
        ("../escape.txt", b"x", "INVALID_FILENAME"),
        ("file.txt", b"\xff", "INVALID_FILE_CONTENT"),
        ("file.pdf", b"not-pdf", "INVALID_FILE_CONTENT"),
        ("file.exe", b"x", "UNSUPPORTED_FILE_TYPE"),
    ],
)
def test_safe_upload_errors(filename, data, code):
    with TestClient(create_app()) as client:
        thread = client.post("/api/threads", json={}).json()["id"]
        response = client.post(f"/api/threads/{thread}/files", files={"file": (filename, data)})
        assert response.status_code == 422 and response.json()["detail"]["code"] == code
        assert "/Users/" not in response.text


def test_one_file_only_and_unknown_thread():
    with TestClient(create_app()) as client:
        assert client.get("/api/threads/missing/files").status_code == 404
        thread = client.post("/api/threads", json={}).json()["id"]
        assert (
            client.post(
                f"/api/threads/{thread}/files", files={"other": ("a.txt", b"a")}
            ).status_code
            == 422
        )
        response = client.post(
            f"/api/threads/{thread}/files",
            files=[("file", ("a.txt", b"a")), ("file", ("b.txt", b"b"))],
        )
        assert response.status_code == 422
        assert client.get(f"/api/threads/{thread}/files").json() == []
