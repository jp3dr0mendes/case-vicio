"""Os votos versionados em artifacts/llm/ continuam sendo lidos igual pelo código atual.

Se o casamento de texto (llm.match_option) mudar, este teste mostra quais votos mudariam de tema,
o que alteraria o publicacao.csv sem que nenhum modelo tenha sido chamado de novo."""
import json
from pathlib import Path

import pytest

from vicio_case.data import load_topics
from vicio_case.llm import (
    GENERAL_OPTION,
    PROMPT_VERSION,
    HierarchicalPrompts,
    match_option,
)
from vicio_case.runner import load_model_outputs
from vicio_case.taxonomy import Taxonomy, load_clone_map

ROOT = Path(__file__).resolve().parents[1]
FILES = sorted((ROOT / "artifacts" / "llm").glob("*.jsonl"))


@pytest.mark.skipif(not FILES, reason="saídas dos LLMs locais ausentes")
@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_stored_votes_reinterpret_identically(path):
    taxonomy = Taxonomy(load_topics(ROOT / "data/input/temas.csv"), load_clone_map(ROOT / "config/nos_duplicados.json"))
    prompts = HierarchicalPrompts(taxonomy)
    lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert {r["prompt_version"] for r in lines} == {PROMPT_VERSION}
    assert len({r["prompt_sha256_12"] for r in lines}) == 1
    changed = []
    for qid, record in load_model_outputs(path).items():
        if record.get("error"):
            continue
        theme = match_option(str(record["raw"]["passo1"].get("tema", "")), sorted(prompts.level1) + ["FORA"])
        node = None if theme == "FORA" else prompts.level1[theme]
        options = prompts.children_options(node) if node else {}
        if options:
            sub = match_option(str(record["raw"]["passo2"].get("tema", "")), sorted(options) + [GENERAL_OPTION],
                               {theme: GENERAL_OPTION})
            node = options.get(sub, node)
        if node != record["tema_central_id"]:
            changed.append((qid, record["tema_central_id"], node))
    assert changed == []
