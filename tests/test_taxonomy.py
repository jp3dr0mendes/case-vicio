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
