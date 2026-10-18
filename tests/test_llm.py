import json
from vicio_case.llm import OllamaClient, CLASSIFICATION_SCHEMA


def test_ollama_chat_uses_structured_schema_and_parses_json(monkeypatch):
    expected = {"decisao": "revisar", "tema_central_id": 123, "extras_ids": [], "confianca": 0.7, "motivo": "ambíguo", "justificativa_fora": ""}
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"message": {"content": json.dumps(expected)}}

    def fake_post(url, json, timeout):
        captured.update({"url": url, "json": json, "timeout": timeout})
        return FakeResponse()

    monkeypatch.setattr("vicio_case.llm.requests.post", fake_post)
    client = OllamaClient(base_url="http://ollama-test:11434", model="unit-model", timeout_seconds=42)
    result = client._chat("system", {"question_id": "Q0001"}, CLASSIFICATION_SCHEMA, 0.0)
    assert result == expected
    assert captured["url"] == "http://ollama-test:11434/api/chat"
    assert captured["timeout"] == 42
    assert captured["json"]["format"] == CLASSIFICATION_SCHEMA
    assert captured["json"]["stream"] is False


def test_ollama_chat_retries_once_after_transient_request_error(monkeypatch):
    expected = {"ok": True}
    calls = {"count": 0}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"message": {"content": json.dumps(expected)}}

    def flaky_post(url, json, timeout):
        calls["count"] += 1
        if calls["count"] == 1:
            import requests
            raise requests.ConnectionError("temporary")
        return FakeResponse()

    monkeypatch.setattr("vicio_case.llm.requests.post", flaky_post)
    monkeypatch.setattr("vicio_case.llm.time.sleep", lambda seconds: None)
    client = OllamaClient(base_url="http://ollama-test:11434", model="unit-model")
    assert client._chat("system", {"question_id": "Q0001"}, CLASSIFICATION_SCHEMA, 0.0) == expected
    assert calls["count"] == 2
