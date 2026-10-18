import csv
from pathlib import Path

from vicio_case.verification import (
    build_blind_sheet,
    clopper_pearson,
    max_errors_to_prove,
    one_sided_lower,
    score_publication,
)

ROOT = Path(__file__).resolve().parents[1]


def test_clopper_pearson_known_values():
    low, high = clopper_pearson(95, 100)
    assert abs(low - 0.8872) < 1e-3 and abs(high - 0.9836) < 1e-3
    assert clopper_pearson(0, 0) == (0.0, 1.0)
    assert one_sided_lower(100, 100) > 0.97


def test_errors_allowed_to_prove_95_with_100_audited():
    assert max_errors_to_prove(100) == 1
    assert max_errors_to_prove(30) is None  # 30 itens nunca bastam para comprovar 95%


def test_score_uses_official_branch_rule(tmp_path):
    pub = tmp_path / "pub.csv"
    with pub.open("w", newline="") as h:
        w = csv.writer(h)
        w.writerow(["id", "decisao", "tema_central_id", "extras_ids", "confianca", "motivo"])
        w.writerow(["Q0001", "publicar", "5087", "", "0.9", ""])   # pai do rótulo -> certo
        w.writerow(["Q0002", "publicar", "5092", "", "0.9", ""])   # irmão do rótulo -> erro
        w.writerow(["Q0003", "publicar", "5092", "", "0.9", ""])   # não sei -> fora da conta
        w.writerow(["Q0004", "revisar", "5159", "", "0.5", "x"])
    labels = tmp_path / "rot.csv"
    labels.write_text("id,tema_id\nQ0001,5092\nQ0002,5093\nQ0003,nao_sei\nQ0004,5157\n")
    out = score_publication(pub, labels, ROOT / "data/input", ROOT / "config", (0.85, 0.98))
    assert out["publicar"]["avaliadas"] == 2 and out["publicar"]["certas"] == 1
    assert out["revisar"]["certas"] == 1
    assert [e["id"] for e in out["erros_publicados"]] == ["Q0002"]
    assert out["meta_95_comprovada"] is False


def test_blind_sheet_hides_system_decisions(tmp_path):
    # Publicação sintética (o teste não depende do publicacao.csv da raiz, ausente na imagem Docker).
    pub = tmp_path / "pub.csv"
    with pub.open("w", newline="") as h:
        w = csv.writer(h)
        w.writerow(["id", "decisao", "tema_central_id", "extras_ids", "confianca", "motivo"])
        for i in range(1, 41):
            decision = "publicar" if i <= 15 else "revisar"
            w.writerow([f"Q{i:04d}", decision, "5092", "", "0.97", "" if decision == "publicar" else "x"])
    info = build_blind_sheet(pub, ROOT / "data/input", ROOT / "config", tmp_path / "out", controls=10)
    page = (tmp_path / "out" / "folha_auditoria.html").read_text(encoding="utf-8")
    assert info == {**info, "questoes": 25, "publicadas": 15, "controles_revisar": 10}
    assert "publicar" not in page and "revisar" not in page and "0.97" not in page and "5092]" in page
    order = (tmp_path / "out" / "amostra_auditoria.csv").read_text().split()[1:]
    assert len(order) == 25 and order != sorted(order)  # embaralhada: posição não revela a decisão
