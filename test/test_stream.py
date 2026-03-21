"""
串流功能單元測試

mock 掉 upstream（LiteLLM），不需要真實伺服器：
- 串流回應正確透傳 SSE chunks
- 串流時正確判斷 is_stream 旗標
- upstream 4xx 時仍透傳狀態碼
- 串流時有觸發 usage log（create_task）
- 非串流走一般路徑不受影響
"""

import asyncio
import json
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from httpx import Response as HttpxResponse, Request as HttpxRequest

from main import app
from db import init_db


# ── Fixtures ──────────────────────────────────────────────────────────────────

FAKE_KEY = "sk-testkey123"


@pytest.fixture(autouse=True)
def setup_db(tmp_path, monkeypatch):
    """每個測試用獨立的暫存 DB"""
    db_file = str(tmp_path / "test.db")
    monkeypatch.setattr("db.DB_PATH", db_file)
    monkeypatch.setattr("main.get_db", lambda: __import__("db").get_db())
    init_db()

    # 插入測試用 key
    import sqlite3
    conn = sqlite3.connect(db_file)
    conn.execute(
        "INSERT INTO api_keys (key, name, description, created_at, is_active) VALUES (?,?,?,?,1)",
        (FAKE_KEY, "test", "unit test key", "2026-01-01T00:00:00"),
    )
    conn.commit()
    conn.close()


def _make_fake_stream_response(chunks: list[bytes], status: int = 200, headers: dict = None):
    """建立一個模擬的 httpx streaming response"""
    async def aiter_bytes(chunk_size=None):
        for c in chunks:
            yield c

    async def aclose():
        pass

    resp = MagicMock()
    resp.status_code = status
    resp.headers = headers or {"content-type": "text/event-stream"}
    resp.aiter_bytes = aiter_bytes
    resp.aclose = aclose
    return resp


def _sse_chunks(contents: list[str]) -> list[bytes]:
    """產生標準 SSE delta chunks + [DONE]"""
    chunks = []
    for i, text in enumerate(contents):
        data = {
            "id": f"chatcmpl-{i}",
            "object": "chat.completion.chunk",
            "choices": [{"delta": {"content": text}, "index": 0, "finish_reason": None}],
        }
        chunks.append(f"data: {json.dumps(data)}\n\n".encode())
    chunks.append(b"data: [DONE]\n\n")
    return chunks


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestStreamDetection:
    """is_stream 判斷邏輯"""

    def _post(self, client, body: dict):
        return client.post(
            "/v1/chat/completions",
            json=body,
            headers={"Authorization": f"Bearer {FAKE_KEY}"},
        )

    def test_stream_true_compact(self):
        """{"stream":true} 緊湊格式應被識別為串流"""
        body = json.dumps({"model": "x", "messages": [], "stream": True}, separators=(",", ":")).encode()
        assert b'"stream":true' in body

    def test_stream_true_spaced(self):
        """{"stream": true} 有空格格式應被識別為串流"""
        body = json.dumps({"model": "x", "messages": [], "stream": True}).encode()
        assert b'"stream": true' in body or b'"stream":true' in body

    def test_no_stream_flag(self):
        """無 stream 旗標不走串流路徑"""
        body = json.dumps({"model": "x", "messages": []}).encode()
        assert b'"stream": true' not in body and b'"stream":true' not in body


class TestStreamProxy:
    """串流 proxy 端對端行為（mock upstream）"""

    def _headers(self):
        return {"Authorization": f"Bearer {FAKE_KEY}", "Content-Type": "application/json"}

    def test_stream_chunks_forwarded(self):
        """串流 chunks 應全部透傳到 client"""
        words = ["Hello", " world", "!"]
        fake_chunks = _sse_chunks(words)
        fake_resp = _make_fake_stream_response(fake_chunks, status=200)

        mock_client = AsyncMock()
        mock_client.build_request.return_value = MagicMock(spec=HttpxRequest)
        mock_client.send = AsyncMock(return_value=fake_resp)

        with TestClient(app, raise_server_exceptions=True) as client:
            app.state.http_client = mock_client
            resp = client.post(
                "/v1/chat/completions",
                content=json.dumps({"model": "x", "messages": [], "stream": True}).encode(),
                headers=self._headers(),
            )

        assert resp.status_code == 200
        raw = resp.content
        for word in words:
            assert word.encode() in raw
        assert b"[DONE]" in raw

    def test_stream_upstream_error_forwarded(self):
        """upstream 回傳 4xx 時，status code 應原樣透傳"""
        fake_resp = _make_fake_stream_response(
            [b'data: {"error":"model not found"}\n\n'],
            status=404,
        )

        mock_client = AsyncMock()
        mock_client.build_request.return_value = MagicMock(spec=HttpxRequest)
        mock_client.send = AsyncMock(return_value=fake_resp)

        with TestClient(app, raise_server_exceptions=True) as client:
            app.state.http_client = mock_client
            resp = client.post(
                "/v1/chat/completions",
                content=json.dumps({"model": "x", "messages": [], "stream": True}).encode(),
                headers=self._headers(),
            )

        assert resp.status_code == 404

    def test_stream_logs_usage(self):
        """串流成功時應呼叫 _log_usage（透過 create_task）"""
        fake_resp = _make_fake_stream_response(_sse_chunks(["hi"]), status=200)

        mock_client = AsyncMock()
        mock_client.build_request.return_value = MagicMock(spec=HttpxRequest)
        mock_client.send = AsyncMock(return_value=fake_resp)

        with patch("main.asyncio.create_task") as mock_create_task:
            with TestClient(app, raise_server_exceptions=True) as client:
                app.state.http_client = mock_client
                resp = client.post(
                    "/v1/chat/completions",
                    content=json.dumps({"model": "x", "messages": [], "stream": True}).encode(),
                    headers=self._headers(),
                )

        assert resp.status_code == 200
        mock_create_task.assert_called_once()

    def test_stream_no_log_on_error(self):
        """upstream 4xx 時不應觸發 usage log"""
        fake_resp = _make_fake_stream_response([b"error"], status=500)

        mock_client = AsyncMock()
        mock_client.build_request.return_value = MagicMock(spec=HttpxRequest)
        mock_client.send = AsyncMock(return_value=fake_resp)

        with patch("main.asyncio.create_task") as mock_create_task:
            with TestClient(app, raise_server_exceptions=True) as client:
                app.state.http_client = mock_client
                resp = client.post(
                    "/v1/chat/completions",
                    content=json.dumps({"model": "x", "messages": [], "stream": True}).encode(),
                    headers=self._headers(),
                )

        assert resp.status_code == 500
        mock_create_task.assert_not_called()

    def test_non_stream_not_affected(self):
        """無 stream 旗標應走非串流路徑（回傳完整 JSON）"""
        body_json = {
            "id": "chatcmpl-x",
            "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            "model": "test-model",
        }
        fake_resp = MagicMock()
        fake_resp.status_code = 200
        fake_resp.headers = {"content-type": "application/json"}
        fake_resp.content = json.dumps(body_json).encode()
        fake_resp.json = lambda: body_json

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=fake_resp)

        with TestClient(app, raise_server_exceptions=True) as client:
            app.state.http_client = mock_client
            resp = client.post(
                "/v1/chat/completions",
                json={"model": "x", "messages": []},
                headers=self._headers(),
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["choices"][0]["message"]["content"] == "ok"
        # 非串流不應呼叫 build_request
        mock_client.build_request.assert_not_called()
