from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
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
    """Árvore de temas. Regra da régua: mesmo nó, pai ou filho = mesmo ramo; irmãos = erro."""

    def __init__(self, df: pd.DataFrame, clones: dict[int, int] | None = None):
        self.by_id: dict[int, Topic] = {}
        for row in df.to_dict("records"):
            parent = row["parent_id"]
            parent_id = None if pd.isna(parent) else int(parent)
            topic = Topic(
                tema_id=int(row["tema_id"]),
                parent_id=parent_id,
                disciplina=str(row["disciplina"]),
                nivel=int(row["nivel"]),
                titulo=str(row["titulo"]).strip(),
                caminho=str(row["caminho"]).strip(),
                descricao=str(row["descricao"]),
                status=str(row["status"]).strip().lower(),
            )
            self.by_id[topic.tema_id] = topic
        self._validate_acyclic()
        self.children: dict[int, list[int]] = {topic_id: [] for topic_id in self.by_id}
        for topic in self.by_id.values():
            if topic.parent_id is not None:
                self.children[topic.parent_id].append(topic.tema_id)
        self.active_ids = {
            topic_id for topic_id, topic in self.by_id.items() if topic.status == "active"
        }
        # Clones vazios (decisão manual em config/nos_duplicados.json): clone -> nó original.
        self.clones: dict[int, int] = {
            int(k): int(v) for k, v in (clones or {}).items() if int(k) in self.by_id and int(v) in self.by_id
        }
        # Selecionável = ativo, não-raiz e sem ancestral inativo.
        self.selectable_ids = {
            topic_id
            for topic_id in self.active_ids
            if self.by_id[topic_id].nivel >= 1
            and all(a in self.active_ids for a in self.ancestors(topic_id))
        }

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
        """True se os nós forem iguais ou um for ancestral do outro (irmãos -> False)."""
        if left_id not in self.active_ids or right_id not in self.active_ids:
            return False
        return left_id in self.ancestors(right_id) or right_id in self.ancestors(left_id)

    def counts_as_correct(self, published_id: int, reference_id: int) -> bool:
        """Régua oficial: o próprio tema, o pai ou um filho dele. Irmãos contam como erro."""
        if published_id == reference_id:
            return True
        pub = self.by_id.get(published_id)
        ref = self.by_id.get(reference_id)
        if pub is None or ref is None:
            return False
        return pub.parent_id == reference_id or ref.parent_id == published_id

    def lowest_common_ancestor(self, left_id: int, right_id: int) -> int | None:
        left = self.ancestors(left_id)
        right = set(self.ancestors(right_id))
        for node in left:
            if node in right:
                return node
        return None

    def level1_of(self, topic_id: int) -> int | None:
        for node in self.ancestors(topic_id):
            if self.by_id[node].nivel == 1:
                return node
        return None

    def is_active_selectable(self, topic_id: int | None) -> bool:
        return topic_id is not None and topic_id in self.selectable_ids

    def topic_for(self, topic_id: int) -> Topic:
        return self.by_id[topic_id]

    def label(self, topic_id: int) -> str:
        """Caminho completo legível (disciplina > tema > subtema)."""
        names = [self.by_id[n].titulo for n in reversed(self.ancestors(topic_id))]
        return " > ".join(names)

    def prompt_listing(self) -> str:
        """Lista compacta de todos os temas selecionáveis, em ordem de árvore."""
        lines: list[str] = []

        def walk(node_id: int) -> None:
            for child in sorted(self.children[node_id], key=lambda c: self.by_id[c].titulo):
                if child in self.selectable_ids:
                    note = ""
                    if child in self.clones:
                        note = f"  [DUPLICATA VAZIA: use {self.clones[child]}]"
                    lines.append(f"{child} | {self.label(child)}{note}")
                    walk(child)

        roots = sorted(
            (t for t in self.by_id.values() if t.parent_id is None), key=lambda t: t.titulo
        )
        for root in roots:
            if root.tema_id in self.active_ids:
                walk(root.tema_id)
        return "\n".join(lines)


def load_clone_map(path: Path) -> dict[int, int]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {int(k): int(v) for k, v in data.get("clones", {}).items()}
