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


def file_model(file_id, name="summary.md"):
    from langchain_core.messages import AIMessage
    from test_lead import ScriptedModel

    return ScriptedModel(
        responses=[
            AIMessage(
                content="", tool_calls=[{"id": "list-call", "name": "list_files", "args": {}}]
            ),
            AIMessage(
                content="",
                tool_calls=[{"id": "read-call", "name": "read_text", "args": {"file_id": file_id}}],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "write-call",
                        "name": "write_text",
                        "args": {"filename": name, "content": "临时摘要：safe sample"},
                    }
                ],
            ),
            AIMessage(content="File artifact registered"),
        ]
    )


def test_run_file_tools_artifact_http_and_download(monkeypatch):
    from test_runs_api import drain, parse_events

    from minideerflow.runtime import runner

    holder = []
    name = '摘要 "v1".md'
    monkeypatch.setattr(runner, "build_chat_model", lambda settings: file_model(holder[0], name))
    app = create_app()
    with TestClient(app) as client:
        thread = client.post("/api/threads", json={}).json()["id"]
        file = client.post(
            f"/api/threads/{thread}/files", files={"file": ("notes.md", "临时正文".encode())}
        ).json()
        holder.append(file["id"])
        response = client.post(
            f"/api/threads/{thread}/runs", json={"message": "read notes and write summary"}
        )
        assert response.status_code == 202
        drain(client, app)
        run = client.get("/api/runs/" + response.json()["run_id"]).json()
        assert run["status"] == "SUCCEEDED"
        assert [trace["name"] for trace in run["tool_calls"]] == [
            "list_files",
            "read_text",
            "write_text",
        ]
        assert run["tool_calls"][1]["result"] == "临时正文"
        artifacts = client.get(f"/api/threads/{thread}/artifacts").json()
        assert len(artifacts) == 1 and artifacts[0]["display_name"] == name
        artifact = artifacts[0]
        download = client.get(
            "/api/artifacts/" + artifact["artifact_id"], params={"thread_id": thread}
        )
        assert download.status_code == 200 and download.content == "临时摘要：safe sample".encode()
        assert download.headers["content-type"].startswith("text/markdown")
        assert "attachment;" in download.headers["content-disposition"]
        assert "filename*=UTF-8''" in download.headers["content-disposition"]
        assert "%22v1%22" in download.headers["content-disposition"]
        files = client.get(f"/api/threads/{thread}/files").json()
        output = next(f for f in files if f["id"] == artifact["file_id"])
        assert hashlib.sha256(download.content).hexdigest() == output["sha256"]
        other = client.post("/api/threads", json={}).json()["id"]
        assert (
            client.get(
                "/api/artifacts/" + artifact["artifact_id"], params={"thread_id": other}
            ).status_code
            == 404
        )
        assert client.get("/api/artifacts/" + artifact["artifact_id"]).status_code == 422
        assert client.get("/api/artifacts/missing", params={"thread_id": thread}).status_code == 404
        events = parse_events(client.get("/api/runs/" + run["id"] + "/events").text)
        starts = [e["payload"]["tool_call_id"] for e in events if e["type"] == "tool_start"]
        ends = [e["payload"]["tool_call_id"] for e in events if e["type"] == "tool_end"]
        assert starts == ends == ["list-call", "read-call", "write-call"]
        assert "storage_key" not in str(artifacts)


def test_file_artifact_run_survive_full_restart(monkeypatch):
    from test_runs_api import drain

    from minideerflow.runtime import runner

    holder = []
    monkeypatch.setattr(runner, "build_chat_model", lambda settings: file_model(holder[0]))
    app = create_app()
    with TestClient(app) as client:
        thread = client.post("/api/threads", json={}).json()["id"]
        cases = [
            ("notes.md", "临时笔记".encode()),
            ("notes.txt", b"text"),
            ("rows.csv", b"a,b\n1,2"),
            ("data.json", b'{"safe":true}'),
            ("stored.pdf", b"%PDF-1.4\nminimal storage signature"),
        ]
        ids = []
        for name, data in cases:
            response = client.post(f"/api/threads/{thread}/files", files={"file": (name, data)})
            assert response.status_code == 201
            ids.append(response.json()["id"])
        holder.append(ids[0])
        run = client.post(
            f"/api/threads/{thread}/runs", json={"message": "read and generate"}
        ).json()
        drain(client, app)
        artifact = client.get(f"/api/threads/{thread}/artifacts").json()[0]
        data = client.get(
            "/api/artifacts/" + artifact["artifact_id"], params={"thread_id": thread}
        ).content
        root = app.state.workspace.storage.root
        # 无登记孤立对象不进入API列表，也不能借内部UUID下载。
        orphan = root / thread / "00000000000000000000000000000000"
        orphan.write_bytes(b"orphan")
    assert app.state.workspace.storage._root_fd == -1
    reopened = create_app()
    with TestClient(reopened) as client:
        files = client.get(f"/api/threads/{thread}/files").json()
        assert len(files) == 6 and all(identifier in [f["id"] for f in files] for identifier in ids)
        assert client.get(f"/api/threads/{thread}/artifacts").json() == [artifact]
        download = client.get(
            "/api/artifacts/" + artifact["artifact_id"], params={"thread_id": thread}
        )
        assert download.content == data and download.status_code == 200
        assert client.get("/api/runs/" + run["run_id"]).json()["status"] == "SUCCEEDED"
        assert client.get("/api/runs/" + run["run_id"] + "/events").status_code == 410
        assert (
            client.get("/api/artifacts/" + orphan.name, params={"thread_id": thread}).status_code
            == 404
        )
        other = client.post("/api/threads", json={}).json()["id"]
        assert (
            client.get(
                "/api/artifacts/" + artifact["artifact_id"], params={"thread_id": other}
            ).status_code
            == 404
        )


def test_artifact_before_failed_run_remains_downloadable(monkeypatch):
    from langchain_core.messages import AIMessage, ToolMessage
    from test_lead import ScriptedModel
    from test_runs_api import drain, parse_events

    from minideerflow.runtime import runner

    class FailAfterWrite(ScriptedModel):
        def _generate(self, messages, *args, **kwargs):
            if any(isinstance(m, ToolMessage) for m in messages):
                raise RuntimeError("private failure")
            return super()._generate(messages, *args, **kwargs)

    monkeypatch.setattr(
        runner,
        "build_chat_model",
        lambda settings: FailAfterWrite(
            responses=[
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "id": "written",
                            "name": "write_text",
                            "args": {
                                "filename": "summary.md",
                                "content": "real artifact before error",
                            },
                        }
                    ],
                ),
            ]
        ),
    )
    app = create_app()
    with TestClient(app) as client:
        thread = client.post("/api/threads", json={}).json()["id"]
        run = client.post(f"/api/threads/{thread}/runs", json={"message": "write then fail"}).json()
        drain(client, app)
        saved = client.get("/api/runs/" + run["run_id"]).json()
        assert saved["status"] == "FAILED" and saved["answer"] is None
        artifact = client.get(f"/api/threads/{thread}/artifacts").json()[0]
        download = client.get(
            "/api/artifacts/" + artifact["artifact_id"], params={"thread_id": thread}
        )
        assert download.content == b"real artifact before error"
        events = parse_events(client.get("/api/runs/" + run["run_id"] + "/events").text)
        assert any(e["type"] == "tool_end" and e["payload"]["ok"] for e in events)
        assert (
            client.post(f"/api/threads/{thread}/runs", json={"message": "unsafe retry"}).status_code
            == 409
        )


@pytest.mark.parametrize("mode", ["symlink", "mutated"])
def test_download_rejects_replaced_bytes_and_symlink(monkeypatch, tmp_path, mode):
    from test_runs_api import drain

    from minideerflow.runtime import runner

    holder = []
    monkeypatch.setattr(runner, "build_chat_model", lambda settings: file_model(holder[0]))
    app = create_app()
    with TestClient(app) as client:
        thread = client.post("/api/threads", json={}).json()["id"]
        holder.append(
            client.post(
                f"/api/threads/{thread}/files", files={"file": ("notes.md", b"notes")}
            ).json()["id"]
        )
        client.post(f"/api/threads/{thread}/runs", json={"message": "create"})
        drain(client, app)
        artifact = client.get(f"/api/threads/{thread}/artifacts").json()[0]
        file = client.portal.call(app.state.workspace.repository.get_file, artifact["file_id"])
        path = app.state.workspace.storage.root / thread / file.storage_key
        outside = tmp_path / "outside"
        outside.write_bytes(b"private outside sentinel")
        if mode == "symlink":
            path.unlink()
            path.symlink_to(outside)
        else:
            path.write_bytes(b"mutated data")
        response = client.get(
            "/api/artifacts/" + artifact["artifact_id"], params={"thread_id": thread}
        )
        assert response.status_code == 422
        assert str(tmp_path) not in response.text and "sentinel" not in response.text
        assert outside.read_bytes() == b"private outside sentinel"


def test_http_upload_size_limit_and_cleanup():
    with TestClient(create_app()) as client:
        thread = client.post("/api/threads", json={}).json()["id"]
        response = client.post(
            f"/api/threads/{thread}/files",
            files={"file": ("large.txt", b"x" * (2 * 1024 * 1024 + 1))},
        )
        assert response.status_code == 413 and response.json()["detail"]["code"] == "FILE_TOO_LARGE"
        assert client.get(f"/api/threads/{thread}/files").json() == []


def test_http_quota_error_is_structured(monkeypatch):
    from minideerflow.workspace import repository

    monkeypatch.setattr(repository, "THREAD_FILE_LIMIT", 1)
    with TestClient(create_app()) as client:
        thread = client.post("/api/threads", json={}).json()["id"]
        assert (
            client.post(
                f"/api/threads/{thread}/files", files={"file": ("one.txt", b"one")}
            ).status_code
            == 201
        )
        response = client.post(f"/api/threads/{thread}/files", files={"file": ("two.txt", b"two")})
        assert (
            response.status_code == 409
            and response.json()["detail"]["code"] == "WORKSPACE_QUOTA_EXCEEDED"
        )
        assert len(client.get(f"/api/threads/{thread}/files").json()) == 1
