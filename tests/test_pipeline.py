from pathlib import Path
import csv
import json

from vicio_case.pipeline import run_data_audit, run_pipeline

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/input"


def small_dataset(tmp_path):
    import shutil
    data_dir = tmp_path / "small_input"
    data_dir.mkdir(exist_ok=True)
    question_lines = (DATA / "questoes.jsonl").read_text(encoding="utf-8").splitlines()[:2]
    (data_dir / "questoes.jsonl").write_text("\n".join(question_lines) + "\n", encoding="utf-8")
    shutil.copy2(DATA / "temas.csv", data_dir / "temas.csv")
    return data_dir


def test_baseline_exports_all_359_for_manual_review(tmp_path):
    result = run_pipeline(DATA, tmp_path, mode="baseline")
    assert result["total"] == 359
    assert result["publicar"] == 0
    assert result["revisar"] == 359
    assert result["fora"] == 0
    with (tmp_path / "publicacao.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 359
    assert set(rows[0]) == {"id", "decisao", "tema_central_id", "extras_ids", "confianca", "motivo"}
    assert all(row["decisao"] == "revisar" for row in rows)
    assert all(row["tema_central_id"] for row in rows)
    assert all(row["motivo"] for row in rows)
    assert (tmp_path / "previsao.txt").exists()
    metadata = json.loads((tmp_path / "run_metadata.json").read_text(encoding="utf-8"))
    assert len(metadata["dataset_sha256"]) == 64
    assert metadata["semantic_validation_performed"] is False
    assert metadata["decision_counts"]["revisar"] == 359
    assert metadata["duration_seconds"] >= 0
    assert metadata["primary_calls_completed"] == 0
    traces = json.loads((tmp_path / "decision_audit.json").read_text(encoding="utf-8"))
    assert len(traces) == 359


def test_audit_reports_known_metadata_gaps(tmp_path):
    audit = run_data_audit(DATA, tmp_path)
    assert audit["questions"] == 359
    assert audit["topics"] == 377
    assert audit["missing_command"] == 94
    assert audit["missing_subject"] == 18
    assert audit["inactive_topics"] == 2


def test_model_failure_degrades_to_review(monkeypatch, tmp_path):
    import vicio_case.pipeline as pipeline

    class BrokenOllama:
        model = "broken-test-model"

        def classify(self, question, candidates):
            raise TimeoutError("simulated model timeout")

    monkeypatch.setattr(pipeline, "OllamaClient", BrokenOllama)
    data_dir = small_dataset(tmp_path)
    output_dir = tmp_path / "output"
    result = run_pipeline(data_dir, output_dir, mode="ollama", max_workers=1)
    assert result["total"] == 2
    assert result["publicar"] == 0
    assert result["revisar"] == 2
    rows = list(csv.DictReader((output_dir / "publicacao.csv").open(encoding="utf-8", newline="")))
    assert all("Falha no modelo/verificação" in row["motivo"] for row in rows)


def test_ollama_pipeline_writes_publish_decisions_when_both_stages_agree(monkeypatch, tmp_path):
    import vicio_case.pipeline as pipeline

    class AgreeingOllama:
        model = "mock-test-model"

        def classify(self, question, candidates):
            return {
                "decisao": "publicar", "tema_central_id": candidates[0]["tema_id"],
                "extras_ids": [], "confianca": 0.99, "motivo": "",
                "justificativa_fora": "", "provider_model": self.model,
            }

        def verify(self, question, candidates, proposal):
            return {
                "concorda": True, "decisao": "publicar",
                "tema_central_id": proposal["tema_central_id"],
                "confianca": 0.98, "motivo": "Confirmado", "provider_model": self.model,
            }

    monkeypatch.setattr(pipeline, "OllamaClient", AgreeingOllama)
    data_dir = small_dataset(tmp_path)
    output_dir = tmp_path / "output"
    result = run_pipeline(data_dir, output_dir, mode="ollama", max_workers=2)
    assert result["total"] == 2
    assert result["publicar"] == 2
    assert result["revisar"] == 0
    metadata = json.loads((output_dir / "run_metadata.json").read_text(encoding="utf-8"))
    assert metadata["primary_calls_completed"] == 2
    assert metadata["verification_calls_completed"] == 2
    rows = list(csv.DictReader((output_dir / "publicacao.csv").open(encoding="utf-8", newline="")))
    assert all(row["decisao"] == "publicar" for row in rows)
    assert all(float(row["confianca"]) == 0.98 for row in rows)


def test_verifier_failure_preserves_primary_trace_but_never_publishes(monkeypatch, tmp_path):
    import vicio_case.pipeline as pipeline

    class BrokenVerifier:
        model = "mock-verifier-failure"

        def classify(self, question, candidates):
            return {
                "decisao": "publicar", "tema_central_id": candidates[0]["tema_id"],
                "extras_ids": [], "confianca": 0.99, "motivo": "",
                "justificativa_fora": "",
            }

        def verify(self, question, candidates, proposal):
            raise TimeoutError("simulated verifier timeout")

    monkeypatch.setattr(pipeline, "OllamaClient", BrokenVerifier)
    data_dir = small_dataset(tmp_path)
    output_dir = tmp_path / "output"
    result = run_pipeline(data_dir, output_dir, mode="ollama", max_workers=1)
    assert result["publicar"] == 0
    assert result["revisar"] == 2
    metadata = json.loads((output_dir / "run_metadata.json").read_text(encoding="utf-8"))
    assert metadata["primary_calls_completed"] == 2
    assert metadata["verification_calls_completed"] == 0
    traces = json.loads((output_dir / "decision_audit.json").read_text(encoding="utf-8"))
    assert traces["Q0001"]["primary"]["decisao"] == "publicar"
    assert traces["Q0001"]["verifier"] is None
