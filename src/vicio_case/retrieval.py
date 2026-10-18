from __future__ import annotations

import re
import unicodedata
from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .data import clean_html, question_text
from .taxonomy import Taxonomy, Topic

DISCIPLINE_ALIASES = {
    "direito penal": "penal",
    "direito processual penal": "processo penal",
    "processual penal": "processo penal",
}


def _norm(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.lower())
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


class CandidateRetriever:
    """Gera candidatos; a pontuação lexical não é uma probabilidade de acerto."""

    def __init__(self, taxonomy: Taxonomy, top_k: int = 12):
        self.taxonomy = taxonomy
        self.top_k = max(2, int(top_k))
        self.topics: list[Topic] = [
            taxonomy.by_id[i] for i in sorted(taxonomy.selectable_ids - set(taxonomy.clones))
        ]
        self.topic_docs = [
            f"{topic.caminho} {topic.titulo} {topic.descricao} {topic.disciplina}"
            for topic in self.topics
        ]
        self.word_vectorizer = TfidfVectorizer(
            lowercase=True, strip_accents="unicode", ngram_range=(1, 2),
            min_df=1, sublinear_tf=True, token_pattern=r"(?u)\b\w+\b",
        )
        self.char_vectorizer = TfidfVectorizer(
            lowercase=True, strip_accents="unicode", analyzer="char_wb",
            ngram_range=(3, 5), min_df=1, sublinear_tf=True,
        )
        self.topic_word = self.word_vectorizer.fit_transform(self.topic_docs)
        self.topic_char = self.char_vectorizer.fit_transform(self.topic_docs)

    def _question_doc(self, question: dict[str, Any]) -> str:
        content = question_text(question)
        subject = clean_html(question.get("assunto_origem"))
        discipline = clean_html(question.get("disciplina_origem"))
        # Metadados de origem são pistas fracas: podem conter erros e nunca decidem sozinhos.
        return f"{content}\nAssunto de origem: {subject}\nDisciplina de origem: {discipline}"

    def retrieve(self, question: dict[str, Any]) -> list[dict[str, Any]]:
        document = self._question_doc(question)
        q_word = self.word_vectorizer.transform([document])
        q_char = self.char_vectorizer.transform([document])
        word_scores = cosine_similarity(q_word, self.topic_word).ravel()
        char_scores = cosine_similarity(q_char, self.topic_char).ravel()
        scores = 0.68 * word_scores + 0.32 * char_scores

        origin_subject = _norm(clean_html(question.get("assunto_origem")))
        origin_discipline = _norm(clean_html(question.get("disciplina_origem")))
        origin_discipline = DISCIPLINE_ALIASES.get(origin_discipline, origin_discipline)
        subject_tokens = set(origin_subject.split()) - {"parte", "geral", "tema", "teoria"}

        ranked: list[tuple[float, Topic]] = []
        for index, topic in enumerate(self.topics):
            score = float(scores[index])
            normalized_title = _norm(topic.titulo)
            normalized_path = _norm(topic.caminho)
            if subject_tokens:
                title_tokens = set(normalized_title.split())
                path_tokens = set(normalized_path.split())
                overlap = subject_tokens.intersection(title_tokens)
                path_overlap = subject_tokens.intersection(path_tokens)
                if overlap:
                    score += min(0.10, 0.025 * len(overlap))
                elif path_overlap:
                    score += min(0.06, 0.015 * len(path_overlap))
            topic_discipline = _norm(topic.disciplina)
            if origin_discipline and origin_discipline == topic_discipline:
                score += 0.025
            ranked.append((score, topic))
        ranked.sort(key=lambda pair: pair[0], reverse=True)

        return [
            {**topic.as_prompt_dict(score), "rank": rank}
            for rank, (score, topic) in enumerate(ranked[: self.top_k], start=1)
        ]
