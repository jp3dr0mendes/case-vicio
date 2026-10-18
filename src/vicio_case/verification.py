"""Medição da precisão real com rótulos humanos (auditoria cega ou gabarito da Vício).

1. `folha-auditoria` gera uma folha HTML offline com as publicadas misturadas a controles de
   revisão, em ordem aleatória, SEM mostrar a decisão do sistema (auditoria cega).
2. Quem audita escolhe o tema de cada questão e exporta `rotulos_auditoria.csv` (id,tema_id).
3. `medir-precisao` compara o publicacao.csv com esses rótulos pela régua oficial (mesmo nó,
   pai ou filho) e devolve a precisão com intervalo exato de Clopper-Pearson.
O mesmo comando aceita o gabarito da equipe da Vício (mesmo formato id,tema_id).
"""
from __future__ import annotations

import csv
import html
import json
import random
from pathlib import Path
from typing import Any

from scipy.stats import beta

from .data import clean_html, load_questions, load_topics
from .taxonomy import Taxonomy, load_clone_map


def clopper_pearson(successes: int, total: int, confidence: float = 0.95) -> tuple[float, float]:
    """Intervalo exato bilateral para uma proporção binomial."""
    if total == 0:
        return (0.0, 1.0)
    alpha = 1 - confidence
    low = 0.0 if successes == 0 else float(beta.ppf(alpha / 2, successes, total - successes + 1))
    high = 1.0 if successes == total else float(beta.ppf(1 - alpha / 2, successes + 1, total - successes))
    return (low, high)


def one_sided_lower(successes: int, total: int, confidence: float = 0.95) -> float:
    """Limite inferior unilateral: 'com 95% de confiança, a precisão é pelo menos X'."""
    if total == 0 or successes == 0:
        return 0.0
    return float(beta.ppf(1 - confidence, successes, total - successes + 1))


def max_errors_to_prove(total: int, target: float = 0.95, confidence: float = 0.95) -> int | None:
    """Quantos erros, no máximo, ainda permitem afirmar precisão >= alvo (limite unilateral)."""
    best = None
    for errors in range(total + 1):
        if one_sided_lower(total - errors, total, confidence) >= target:
            best = errors
    return best


def _read_publication(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return {row["id"]: row for row in csv.DictReader(handle)}


def read_labels(path: Path) -> dict[str, str]:
    """id -> tema_id (texto). Vazio/'fora' = sem tema; 'nao_sei' = descartado da conta."""
    with path.open(encoding="utf-8", newline="") as handle:
        return {row["id"].strip(): (row.get("tema_id") or "").strip() for row in csv.DictReader(handle)}


def score_publication(publication: Path, labels_path: Path, data_dir: Path, config_dir: Path,
                      forecast_interval: tuple[float, float] | None = None) -> dict[str, Any]:
    taxonomy = Taxonomy(load_topics(data_dir / "temas.csv"), load_clone_map(config_dir / "nos_duplicados.json"))
    rows = _read_publication(publication)
    labels = read_labels(labels_path)
    result: dict[str, Any] = {"rotulos": len(labels)}
    details = []
    for decision in ("publicar", "revisar"):
        judged = correct = 0
        for qid, row in rows.items():
            if row["decisao"] != decision or qid not in labels:
                continue
            label = labels[qid]
            if label.lower() in {"nao_sei", "não sei", "?"}:
                continue
            judged += 1
            ok = False
            if label and label.lower() != "fora" and row["tema_central_id"]:
                ok = taxonomy.counts_as_correct(int(row["tema_central_id"]), int(label))
            correct += ok
            details.append({"id": qid, "decisao": decision, "sistema": row["tema_central_id"],
                            "rotulo": label, "certo": ok})
        low, high = clopper_pearson(correct, judged)
        result[decision] = {
            "avaliadas": judged, "certas": correct,
            "precisao": round(correct / judged, 4) if judged else None,
            "ic95_clopper_pearson": [round(low, 4), round(high, 4)],
            "limite_inferior_unilateral_95": round(one_sided_lower(correct, judged), 4),
        }
    pub = result["publicar"]
    total_published = sum(r["decisao"] == "publicar" for r in rows.values())
    result["publicadas_total"] = total_published
    result["cobertura_da_auditoria"] = round(pub["avaliadas"] / total_published, 4) if total_published else 0
    result["meta_95_comprovada"] = bool(pub["avaliadas"]) and pub["limite_inferior_unilateral_95"] >= 0.95
    result["meta_95_refutada"] = bool(pub["avaliadas"]) and pub["ic95_clopper_pearson"][1] < 0.95
    if forecast_interval and pub["precisao"] is not None:
        result["previsao_intervalo"] = list(forecast_interval)
        result["previsao_acertou_intervalo"] = forecast_interval[0] <= pub["precisao"] <= forecast_interval[1]
    result["erros_publicados"] = [d for d in details if d["decisao"] == "publicar" and not d["certo"]]
    return result


def build_blind_sheet(publication: Path, data_dir: Path, config_dir: Path, out_dir: Path,
                      controls: int = 30, seed: int = 2026) -> dict[str, Any]:
    """Folha de auditoria cega: todas as publicadas + `controls` revisões sorteadas, embaralhadas."""
    taxonomy = Taxonomy(load_topics(data_dir / "temas.csv"), load_clone_map(config_dir / "nos_duplicados.json"))
    questions = {q["id"]: q for q in load_questions(data_dir / "questoes.jsonl")}
    rows = _read_publication(publication)
    rng = random.Random(seed)
    published = [q for q, r in rows.items() if r["decisao"] == "publicar"]
    review = sorted(q for q, r in rows.items() if r["decisao"] == "revisar")
    sample = published + rng.sample(review, min(controls, len(review)))
    rng.shuffle(sample)
    options = sorted(
        (f"{taxonomy.label(i)} [{i}]", i) for i in taxonomy.selectable_ids if i not in taxonomy.clones
    ) + sorted((f"{taxonomy.label(i)} [{i}] (cópia vazia)", i) for i in taxonomy.clones)
    items = []
    for qid in sample:
        q = questions[qid]
        alts = q.get("alternativas") or {}
        items.append({
            "id": qid,
            "texto": clean_html(q.get("enunciado_html")),
            "comando": clean_html(q.get("comando")),
            "alternativas": [f"{k}) {clean_html(v)}" for k, v in alts.items()],
        })
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "amostra_auditoria.csv").write_text(
        "id\n" + "\n".join(sample) + "\n", encoding="utf-8")
    page = _SHEET.replace("__ITEMS__", json.dumps(items, ensure_ascii=False)) \
                 .replace("__OPTIONS__", json.dumps([o for o, _ in options], ensure_ascii=False)) \
                 .replace("__N__", str(len(items)))
    (out_dir / "folha_auditoria.html").write_text(page, encoding="utf-8")
    return {"questoes": len(items), "publicadas": len(published), "controles_revisar": len(sample) - len(published),
            "arquivo": str(out_dir / "folha_auditoria.html"), "semente": seed}


_SHEET = """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Auditoria cega</title>
<style>
:root{--bg:#fafaf8;--fg:#1d1d1b;--muted:#6b6b66;--card:#fff;--line:#e3e2dc;--accent:#2f5d8a}
@media (prefers-color-scheme:dark){:root{--bg:#161615;--fg:#ecebe6;--muted:#a3a29b;--card:#20201e;--line:#34332f;--accent:#8db4dd}}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,sans-serif}
main{max-width:860px;margin:0 auto;padding:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px;margin:12px 0}
.meta{color:var(--muted);font-size:14px} input[type=text]{width:100%;box-sizing:border-box;padding:8px;font-size:15px;
border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--fg)}
button{padding:8px 14px;border-radius:6px;border:1px solid var(--accent);background:var(--accent);color:#fff;cursor:pointer}
.row{display:flex;gap:8px;flex-wrap:wrap;margin-top:8px} .row label{font-size:14px;color:var(--muted)}
header{position:sticky;top:0;background:var(--bg);padding:8px 0;border-bottom:1px solid var(--line)}
</style></head><body><main>
<header><strong>Auditoria cega — __N__ questões</strong>
<div class="meta">Escolha o tema que a questão cobra, <em>sem</em> consultar a classificação do sistema. Use "fora" se nenhum tema serve e "nao_sei" se não souber.
O progresso fica salvo neste navegador. <span id="prog"></span></div>
<div class="row"><button onclick="exportar()">Exportar rotulos_auditoria.csv</button></div></header>
<datalist id="temas"></datalist><div id="lista"></div>
<script>
const ITEMS=__ITEMS__, OPTIONS=__OPTIONS__, KEY="auditoria-cega-vicio";
let st={}; try{st=JSON.parse(localStorage.getItem(KEY)||"{}")}catch(e){}
const dl=document.getElementById("temas"); OPTIONS.forEach(o=>{const e=document.createElement("option");e.value=o;dl.appendChild(e)});
["fora","nao_sei"].forEach(o=>{const e=document.createElement("option");e.value=o;dl.appendChild(e)});
const esc=s=>s.replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
const lista=document.getElementById("lista");
ITEMS.forEach((q,i)=>{const d=document.createElement("div");d.className="card";
d.innerHTML=`<div class="meta">${i+1}/${ITEMS.length} · ${q.id}</div><p>${esc(q.texto)}</p>`+
(q.comando?`<p><em>${esc(q.comando)}</em></p>`:"")+`<ul>${q.alternativas.map(a=>`<li>${esc(a)}</li>`).join("")}</ul>`+
`<input type="text" list="temas" placeholder="Digite para buscar o tema…" data-id="${q.id}" value="${esc(st[q.id]||"")}">`;
lista.appendChild(d)});
function prog(){document.getElementById("prog").textContent=`Preenchidas: ${Object.values(st).filter(Boolean).length}/${ITEMS.length}`}
document.querySelectorAll("input[data-id]").forEach(inp=>inp.addEventListener("change",e=>{st[e.target.dataset.id]=e.target.value.trim();
try{localStorage.setItem(KEY,JSON.stringify(st))}catch(err){} prog()})); prog();
function idDe(v){if(!v)return"";if(v==="fora"||v==="nao_sei")return v;const m=v.match(/\\[(\\d+)\\]/);return m?m[1]:""}
function exportar(){const linhas=["id,tema_id"].concat(ITEMS.map(q=>q.id+","+idDe(st[q.id]||"")));
const a=document.createElement("a");a.href=URL.createObjectURL(new Blob([linhas.join("\\n")+"\\n"],{type:"text/csv"}));
a.download="rotulos_auditoria.csv";a.click()}
</script></main></body></html>
"""
