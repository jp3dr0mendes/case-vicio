from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class Topic:
    tema_id: int
    parent_id: int | None
    disciplina: str
    nivel: int
    titulo: str
    caminho: str
    descricao: str
    status: str

    def as_prompt_dict(self, lexical_score: float | None = None) -> dict[str, Any]:
        result = {
            "tema_id": self.tema_id,
            "parent_id": self.parent_id,
            "disciplina": self.disciplina,
            "nivel": self.nivel,
            "titulo": self.titulo,
            "caminho": self.caminho,
            "descricao": self.descricao,
        }
        if lexical_score is not None:
            result["similaridade_lexical"] = round(float(lexical_score), 4)
        return result


class Taxonomy:
    def __init__(self, df: pd.DataFrame):
        self.by_id: dict[int, Topic] = {}
        for row in df.to_dict("records"):
            parent = row["parent_id"]
            parent_id = None if pd.isna(parent) else int(parent)
            topic = Topic(
                tema_id=int(row["tema_id"]),
                parent_id=parent_id,
                disciplina=str(row["disciplina"]),
                nivel=int(row["nivel"]),
                titulo=str(row["titulo"]),
                caminho=str(row["caminho"]),
                descricao=str(row["descricao"]),
                status=str(row["status"]).lower(),
            )
            self.by_id[topic.tema_id] = topic
        self.active_ids = {
            topic_id for topic_id, topic in self.by_id.items() if topic.status == "active"
        }
        self.selectable_ids = {
            topic_id for topic_id in self.active_ids if self.by_id[topic_id].nivel >= 1
        }
        self._validate_acyclic()

    def _validate_acyclic(self) -> None:
        for topic_id in self.by_id:
            seen: set[int] = set()
            cursor: int | None = topic_id
            while cursor is not None:
                if cursor in seen:
                    raise ValueError(f"Ciclo detectado na árvore de temas: {cursor}")
                seen.add(cursor)
                topic = self.by_id.get(cursor)
                if topic is None:
                    raise ValueError(f"Pai inexistente na árvore: {cursor}")
                cursor = topic.parent_id

    def ancestors(self, topic_id: int, include_self: bool = True) -> list[int]:
        if topic_id not in self.by_id:
            return []
        output: list[int] = []
        cursor: int | None = topic_id if include_self else self.by_id[topic_id].parent_id
        while cursor is not None:
            output.append(cursor)
            cursor = self.by_id[cursor].parent_id
        return output

    def branch_related(self, left_id: int, right_id: int) -> bool:
        """True apenas se os nós forem iguais ou um for ancestral do outro."""
        if left_id not in self.active_ids or right_id not in self.active_ids:
            return False
        return left_id in self.ancestors(right_id) or right_id in self.ancestors(left_id)

    def is_active_selectable(self, topic_id: int | None) -> bool:
        return topic_id is not None and topic_id in self.selectable_ids

    def topic_for(self, topic_id: int) -> Topic:
        return self.by_id[topic_id]
