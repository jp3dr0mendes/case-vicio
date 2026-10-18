from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pandas as pd
from bs4 import BeautifulSoup

QUESTION_REQUIRED_FIELDS = {
    "id", "enunciado_html", "comando", "alternativas",
    "disciplina_origem", "assunto_origem",
}
PUBLICATION_COLUMNS = [
    "id", "decisao", "tema_central_id", "extras_ids", "confianca", "motivo"
]
VALID_DECISIONS = {"publicar", "revisar", "fora"}


class DataValidationError(ValueError):
    """Erro em dados de entrada/saída que impede uma execução segura."""


def clean_html(value: Any) -> str:
    if value is None:
        return ""
    text = BeautifulSoup(str(value), "html.parser").get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()


def alternatives_to_text(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(f"{key}: {clean_html(val)}" for key, val in value.items())
    if isinstance(value, list):
        return " ".join(clean_html(item) for item in value)
    return clean_html(value)


def question_text(question: dict[str, Any]) -> str:
    parts = [
        clean_html(question.get("enunciado_html")),
        clean_html(question.get("comando")),
        alternatives_to_text(question.get("alternativas")),
    ]
    return "\n".join(part for part in parts if part)


def load_questions(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise DataValidationError(f"Arquivo de questões não encontrado: {path}")
    questions: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, start=1):
            if not raw.strip():
                continue
            try:
                item = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise DataValidationError(
                    f"JSON inválido em {path}, linha {line_number}: {exc}"
                ) from exc
            missing = QUESTION_REQUIRED_FIELDS - item.keys()
            if missing:
                raise DataValidationError(
                    f"Questão na linha {line_number} sem campos: {sorted(missing)}"
                )
            if not str(item.get("id", "")).strip():
                raise DataValidationError(f"ID vazio em {path}, linha {line_number}")
            questions.append(item)
    ids = [item["id"] for item in questions]
    if len(ids) != len(set(ids)):
        raise DataValidationError("Há IDs de questão duplicados no JSONL")
    return questions


def load_topics(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise DataValidationError(f"Arquivo de temas não encontrado: {path}")
    df = pd.read_csv(path, dtype={"tema_id": "Int64", "parent_id": "Int64"})
    required = {"tema_id", "parent_id", "disciplina", "nivel", "titulo", "caminho", "descricao", "status"}
    missing = required - set(df.columns)
    if missing:
        raise DataValidationError(f"CSV de temas sem colunas: {sorted(missing)}")
    if df["tema_id"].isna().any() or df["tema_id"].duplicated().any():
        raise DataValidationError("tema_id vazio ou duplicado na árvore de temas")
    df["tema_id"] = df["tema_id"].astype(int)
    df["parent_id"] = df["parent_id"].astype("Int64")
    df["nivel"] = pd.to_numeric(df["nivel"], errors="raise").astype(int)
    for col in ["disciplina", "titulo", "caminho", "descricao", "status"]:
        df[col] = df[col].fillna("").astype(str)
    existing_ids = set(df["tema_id"].tolist())
    for row in df.itertuples(index=False):
        if pd.notna(row.parent_id) and int(row.parent_id) not in existing_ids:
            raise DataValidationError(
                f"Tema {row.tema_id} aponta para pai inexistente {row.parent_id}"
            )
    return df


def validate_publication_rows(
    rows: list[dict[str, Any]], question_ids: set[str], active_topic_ids: set[int]
) -> None:
    if len(rows) != len(question_ids):
        raise DataValidationError(
            f"Saída com {len(rows)} linhas; esperado {len(question_ids)}"
        )
    ids = [str(row.get("id", "")) for row in rows]
    if len(ids) != len(set(ids)):
        raise DataValidationError("Saída contém IDs de questão duplicados")
    if set(ids) != question_ids:
        missing = question_ids - set(ids)
        extra = set(ids) - question_ids
        raise DataValidationError(f"IDs divergentes. Ausentes={missing}; extras={extra}")
    for row in rows:
        decision = row.get("decisao")
        if decision not in VALID_DECISIONS:
            raise DataValidationError(f"Decisão inválida em {row.get('id')}: {decision}")
        raw_topic_id = row.get("tema_central_id")
        if decision == "fora":
            if raw_topic_id is not None and str(raw_topic_id).strip() != "":
                raise DataValidationError("Decisão 'fora' deve deixar tema_central_id vazio")
        else:
            try:
                topic_id = int(raw_topic_id)
            except (TypeError, ValueError):
                raise DataValidationError(
                    f"{decision} exige tema_central_id válido em {row.get('id')}"
                )
            if topic_id not in active_topic_ids:
                raise DataValidationError(
                    f"Tema central inexistente/inativo ({topic_id}) em {row.get('id')}"
                )
        try:
            confidence = float(row.get("confianca"))
        except (TypeError, ValueError):
            raise DataValidationError(f"Confiança inválida em {row.get('id')}")
        if not 0.0 <= confidence <= 1.0:
            raise DataValidationError(f"Confiança fora de [0, 1] em {row.get('id')}")
        raw_extras = row.get("extras_ids", "")
        extras_text = "" if raw_extras is None else str(raw_extras).strip()
        extras = [part for part in extras_text.split(";") if part.strip()]
        if len(extras) != len(set(extras)):
            raise DataValidationError(f"extras_ids duplicados em {row.get('id')}")
        for extra in extras:
            try:
                extra_id = int(extra)
            except ValueError as exc:
                raise DataValidationError(f"extra inválido ({extra}) em {row.get('id')}") from exc
            if extra_id not in active_topic_ids:
                raise DataValidationError(f"extra inexistente/inativo ({extra_id}) em {row.get('id')}")
            if decision != "fora" and extra_id == int(raw_topic_id):
                raise DataValidationError(f"tema central repetido em extras_ids para {row.get('id')}")
        if decision == "fora" and extras:
            raise DataValidationError(f"Decisão 'fora' deve deixar extras_ids vazio ({row.get('id')})")
        if decision in {"revisar", "fora"} and not str(row.get("motivo", "")).strip():
            raise DataValidationError(f"Motivo obrigatório em {row.get('id')}")
