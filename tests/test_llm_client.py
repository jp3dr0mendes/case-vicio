"""Cliente Ollama sem servidor: respostas simuladas para testar o fluxo de dois passos e as falhas."""
import json
from pathlib import Path

import pytest

from vicio_case import llm
from vicio_case.data import load_topics
from vicio_case.llm import HierarchicalPrompts, LLMResponseError, OllamaClient
from vicio_case.taxonomy import Taxonomy, load_clone_map

ROOT = Path(__file__).resolve().parents[1]
TAX = Taxonomy(load_topics(ROOT / "data/input/temas.csv"), load_clone_map(ROOT / "config/nos_duplicados.json"))
QUESTION = {"id": "Q", "enunciado_html": "Prescrição executória", "comando": "", "alternativas": {}}


class FakeResponse:
    def __init__(self, content: str):
        self._content = content

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"message": {"content": self._content}}


def install(monkeypatch, answers: list[dict]) -> list[dict]:
    sent: list[dict] = []

    def fake_post(url, json=None, timeout=None):
        sent.append(json)
        return FakeResponse(llm.json.dumps(answers[min(len(sent), len(answers)) - 1], ensure_ascii=False))

    monkeypatch.setattr(llm.requests, "post", fake_post)
    monkeypatch.setattr(llm.time, "sleep", lambda _: None)
    return sent


def test_two_step_classification_maps_to_subtopic(monkeypatch):
    sent = install(monkeypatch, [
        {"assunto_cobrado": "prescrição", "tema": "Penal > Prescrição"},
        {"assunto_cobrado": "executória", "tema": "Prescrição da Pretensão Executória"},
    ])
    out = OllamaClient(model="fake").classify(QUESTION, HierarchicalPrompts(TAX))
    assert out["tema_central_id"] == 5189 and out["fora"] is False
    assert len(sent) == 2 and sent[0]["options"]["temperature"] == 0.0


def test_repeating_the_theme_in_step_two_means_general_theme(monkeypatch):
    install(monkeypatch, [{"tema": "Penal > Prescrição"}, {"tema": "Penal > Prescrição"}])
    out = OllamaClient(model="fake").classify(QUESTION, HierarchicalPrompts(TAX))
    assert out["tema_central_id"] == 5185


def test_answering_the_exam_question_fails_with_auditable_trace(monkeypatch):
    sent = install(monkeypatch, [{"tema": "B: I e III, apenas."}])
    with pytest.raises(LLMResponseError) as info:
        OllamaClient(model="fake", max_attempts=3).classify(QUESTION, HierarchicalPrompts(TAX))
    err = info.value
    assert err.passo == 1 and len(err.tentativas) == 3 and len(sent) == 3
    assert json.loads(err.tentativas[0]["resposta_bruta"])["tema"] == "B: I e III, apenas."
    assert [p["options"]["temperature"] for p in sent] == [0.0, 0.3, 0.3]


def test_step_two_failure_keeps_step_one_result(monkeypatch):
    install(monkeypatch, [{"tema": "Penal > Prescrição"}, {"tema": "não sei"}])
    with pytest.raises(LLMResponseError) as info:
        OllamaClient(model="fake", max_attempts=2).classify(QUESTION, HierarchicalPrompts(TAX))
    assert info.value.passo == 2 and info.value.parcial["tema_nivel_1"] == 5185
