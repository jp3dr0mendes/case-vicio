from pathlib import Path

from vicio_case.data import clean_html, load_questions, load_topics, question_text
from vicio_case.taxonomy import Taxonomy

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "input"


def test_case_files_have_expected_cardinality_and_unique_ids():
    questions = load_questions(DATA / "questoes.jsonl")
    topics = load_topics(DATA / "temas.csv")
    assert len(questions) == 359
    assert len({question["id"] for question in questions}) == 359
    assert len(topics) == 377


def test_html_is_removed_but_content_is_preserved():
    assert clean_html("<p>Tribunal <i>do Júri</i><br> CPP</p>") == "Tribunal do Júri CPP"


def test_question_text_includes_alternatives_and_command():
    question = {
        "enunciado_html": "<b>Inquérito policial</b>",
        "comando": "Assinale a correta",
        "alternativas": {"A": "Arquivamento", "B": "Denúncia"},
    }
    text = question_text(question)
    assert "Inquérito policial" in text
    assert "Assinale a correta" in text
    assert "Arquivamento" in text and "Denúncia" in text


def test_taxonomy_is_acyclic_and_inactive_topics_are_not_selectable():
    taxonomy = Taxonomy(load_topics(DATA / "temas.csv"))
    assert len(taxonomy.active_ids) == 375
    assert len(taxonomy.selectable_ids) == 371
    assert 5078 not in taxonomy.selectable_ids
    assert 5234 not in taxonomy.selectable_ids


def test_compose_file_is_valid_yaml_and_has_expected_services():
    import yaml
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    assert {"app", "db", "ollama", "adminer"}.issubset(compose["services"])
    assert compose["services"]["db"]["healthcheck"]
    assert "local-llm" in compose["services"]["ollama"]["profiles"]
