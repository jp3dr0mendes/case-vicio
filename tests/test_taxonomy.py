from pathlib import Path

from vicio_case.data import load_topics
from vicio_case.taxonomy import Taxonomy

ROOT = Path(__file__).resolve().parents[1]


def test_parent_child_is_accepted_but_sibling_is_not():
    taxonomy = Taxonomy(load_topics(ROOT / "data/input/temas.csv"))
    # Criminologia no Estado Democrático de Direito -> dois filhos: modelos e prevenção.
    assert taxonomy.branch_related(4368, 4370)
    assert taxonomy.branch_related(4368, 4369)
    assert not taxonomy.branch_related(4370, 4369)


def test_inactive_topic_cannot_be_considered_equivalent():
    taxonomy = Taxonomy(load_topics(ROOT / "data/input/temas.csv"))
    assert not taxonomy.branch_related(5078, 5062)


def test_counts_as_correct_follows_the_official_rule():
    taxonomy = Taxonomy(load_topics(ROOT / "data/input/temas.csv"))
    assert taxonomy.counts_as_correct(5092, 5092)      # mesmo nó
    assert taxonomy.counts_as_correct(5087, 5092)      # publicou o pai do gabarito
    assert taxonomy.counts_as_correct(5092, 5087)      # publicou o filho do gabarito
    assert not taxonomy.counts_as_correct(5092, 5093)  # irmãos (corrupção passiva x ativa)
    assert not taxonomy.counts_as_correct(5063, 5466)  # 'Ação Penal' em ramos diferentes


def test_clone_nodes_are_marked_and_empty():
    from vicio_case.taxonomy import load_clone_map

    clones = load_clone_map(ROOT / "config/nos_duplicados.json")
    taxonomy = Taxonomy(load_topics(ROOT / "data/input/temas.csv"), clones)
    assert len(taxonomy.clones) == 20
    for clone, original in taxonomy.clones.items():
        assert not taxonomy.by_id[clone].descricao.strip()
        assert not taxonomy.children[clone]
        assert taxonomy.by_id[original].status == "active"
