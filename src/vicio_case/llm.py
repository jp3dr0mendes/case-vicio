"""Classificador local via Ollama, hierárquico em dois passos (tema -> subtema).

Ver prompts/classificacao.md para o texto dos prompts e o histórico de versões descartadas.
"""
from __future__ import annotations

import difflib
import json
import os
import time
import unicodedata
from typing import Any

import requests

from .data import question_text
from .taxonomy import Taxonomy

PROMPT_VERSION = "classificacao-v3-hierarquica"
GENERAL_OPTION = "(o tema como um todo / vários subtemas)"
FORMAT_RULES = (
    'Responda em JSON: {"assunto_cobrado": "frase curta dizendo qual instituto jurídico a questão cobra", '
    '"tema": "copie exatamente o nome de uma das opções listadas"}. NUNCA responda a questão de concurso nem escolha '
    "alternativa A/B/C/D/E: sua tarefa é só CLASSIFICAR o assunto."
)


class LLMResponseError(ValueError):
    """Resposta do modelo malformada, fora das opções ou chamada sem sucesso após as retentativas.

    Carrega o necessário para auditar a falha: o passo (1 = tema, 2 = subtema), o resultado parcial
    já obtido e, por tentativa, o erro e a resposta bruta do modelo."""

    def __init__(self, message: str, raw_content: str | None = None):
        super().__init__(message)
        self.raw_content = raw_content
        self.tentativas: list[dict[str, Any]] = []
        self.passo: int | None = None
        self.parcial: dict[str, Any] | None = None


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", str(text)).lower().strip(" .-:\"'")
    return " ".join(text.split())


def match_option(answer: str, options: list[str], aliases: dict[str, str] | None = None) -> str | None:
    """Casamento estrito: igual, ou mesmo último segmento do caminho (se único). Sem palpite.

    aliases: textos equivalentes a uma opção (ex.: no passo 2, repetir o nome do tema = tema geral)."""
    answer = str(answer).split("  (subtemas:")[0].split(" (subtemas:")[0]  # modelo copiou a linha inteira
    target = _norm(answer)
    for alias, option in (aliases or {}).items():
        if _norm(alias) == target or _norm(alias).split(" > ")[-1] == target.split(" > ")[-1]:
            return option
    if not target:
        return None
    exact = [o for o in options if _norm(o) == target]
    if exact:
        return exact[0]
    suffix = [o for o in options if _norm(o).split(" > ")[-1] == target.split(" > ")[-1]]
    if len(suffix) == 1:
        return suffix[0]
    if suffix:
        return None  # nome repetido em ramos diferentes (ex.: "Ação Penal"): não chuta
    # Só erro de digitação (inclusive os da própria árvore): similaridade alta e vencedor isolado.
    scored = sorted(
        ((difflib.SequenceMatcher(None, target, _norm(o)).ratio(), o) for o in options), reverse=True
    )
    if scored and scored[0][0] >= 0.92 and (len(scored) == 1 or scored[0][0] - scored[1][0] >= 0.05):
        return scored[0][1]
    return None


class HierarchicalPrompts:
    def __init__(self, taxonomy: Taxonomy):
        self.taxonomy = taxonomy
        self.usable = {i for i in taxonomy.selectable_ids if i not in taxonomy.clones}
        self.level1 = {taxonomy.label(i): i for i in self.usable if taxonomy.by_id[i].nivel == 1}
        lines = []
        for label in sorted(self.level1):
            children = [taxonomy.by_id[c].titulo for c in taxonomy.children[self.level1[label]] if c in self.usable]
            lines.append(f"- {label}" + (f"  (subtemas: {'; '.join(children)})" if children else ""))
        self.step1 = (
            "Você classifica questões de concursos jurídicos (Direito Penal, Processo Penal, Legislação Penal "
            "Especial, Criminologia).\nEscolha o TEMA da lista que a questão realmente cobra (o assunto que o aluno "
            "precisa dominar). Use o conteúdo; disciplina/assunto de origem podem estar errados.\n"
            "Tipo penal ou pena -> Penal; procedimento, prova, prisão, recurso -> Processo Penal; lei extravagante "
            "(drogas, Maria da Penha, abuso de autoridade, LEP...) -> Legislação Especial.\n"
            "Se nenhum tema servir (questão de outra área do Direito), responda FORA.\n"
            f"{FORMAT_RULES}\nTEMAS:\n" + "\n".join(lines)
        )

    def children_options(self, node: int) -> dict[str, int]:
        return {self.taxonomy.by_id[c].titulo: c for c in self.taxonomy.children[node] if c in self.usable}

    def step2(self, theme_label: str, options: list[str]) -> str:
        return (
            f"A questão é do tema '{theme_label}'. Escolha o subtema que ela cobra; se cobrir vários subtemas ou o "
            f"tema em geral, escolha '{GENERAL_OPTION}'.\n{FORMAT_RULES}\nOPÇÕES:\n"
            + "\n".join(f"- {o}" for o in options)
        )


def user_message(question: dict[str, Any]) -> str:
    return (
        "<questao>\n" + question_text(question) + "\n</questao>\n\n"
        "Tarefa: NÃO resolva a questão acima e NÃO escolha alternativa. Diga apenas a qual opção da lista "
        "de temas ela pertence, copiando o nome da opção no campo \"tema\"."
    )


class OllamaClient:
    def __init__(self, base_url: str | None = None, model: str | None = None,
                 timeout_seconds: int | None = None, max_attempts: int = 3, num_ctx: int | None = None):
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")
        self.model = model or os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
        self.timeout_seconds = timeout_seconds or int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "180"))
        self.max_attempts = max_attempts
        self.num_ctx = num_ctx or int(os.getenv("OLLAMA_NUM_CTX", "8192"))

    def health(self) -> dict[str, Any]:
        """Falha explicitamente se o servidor não responde ou o modelo não foi baixado."""
        response = requests.get(f"{self.base_url}/api/tags", timeout=10)
        response.raise_for_status()
        names = {m.get("name") for m in response.json().get("models", [])}
        if self.model not in names:
            raise RuntimeError(f"Modelo {self.model} não encontrado no Ollama ({sorted(names)})")
        version = requests.get(f"{self.base_url}/api/version", timeout=10).json().get("version")
        return {"ollama_version": version, "model": self.model}

    def _ask(self, system: str, user: str, options: list[str],
             aliases: dict[str, str] | None = None) -> tuple[str, dict[str, Any], int]:
        last_error: Exception | None = None
        attempt_log: list[dict[str, Any]] = []
        for attempt in range(1, self.max_attempts + 1):
            payload = {
                "model": self.model, "stream": False, "format": "json", "keep_alive": "30m",
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                # Retentativa com leve temperatura: com temperatura 0 a mesma resposta inválida se repetiria.
                "options": {"temperature": 0.0 if attempt == 1 else 0.3, "seed": 7,
                            "num_ctx": self.num_ctx, "num_predict": 300},
            }
            try:
                response = requests.post(f"{self.base_url}/api/chat", json=payload, timeout=self.timeout_seconds)
                response.raise_for_status()
                content = response.json().get("message", {}).get("content", "")
                try:
                    raw = json.loads(content)
                except json.JSONDecodeError as exc:
                    raise LLMResponseError(f"JSON inválido: {content[:150]}", content) from exc
                choice = match_option(str(raw.get("tema", "")), options, aliases)
                if choice is None:
                    raise LLMResponseError(f"tema fora das opções: {str(raw.get('tema'))[:120]}", content)
                return choice, raw, attempt
            except (requests.RequestException, LLMResponseError) as exc:
                last_error = exc
                attempt_log.append({"tentativa": attempt, "erro": f"{type(exc).__name__}: {exc}",
                                    "resposta_bruta": getattr(exc, "raw_content", None)})
                time.sleep(min(2.0 * attempt, 5.0))
        assert last_error is not None
        message = str(last_error) if isinstance(last_error, LLMResponseError) \
            else f"{type(last_error).__name__}: {last_error}"
        failure = LLMResponseError(message, getattr(last_error, "raw_content", None))
        failure.tentativas = attempt_log
        raise failure from last_error

    def classify(self, question: dict[str, Any], prompts: HierarchicalPrompts) -> dict[str, Any]:
        started = time.perf_counter()
        user = user_message(question)
        try:
            theme, raw1, attempts1 = self._ask(prompts.step1, user, sorted(prompts.level1) + ["FORA"])
        except LLMResponseError as exc:
            exc.passo = 1
            raise
        trace: dict[str, Any] = {"passo1": raw1}
        attempts2 = 0
        if theme == "FORA":
            central = None
        else:
            central = prompts.level1[theme]
            options = prompts.children_options(central)
            if options:
                try:
                    sub, raw2, attempts2 = self._ask(prompts.step2(theme, sorted(options)), user,
                                                     sorted(options) + [GENERAL_OPTION], {theme: GENERAL_OPTION})
                except LLMResponseError as exc:
                    exc.passo, exc.parcial = 2, {"tema_nivel_1": central, **trace}
                    raise
                trace["passo2"] = raw2
                central = options.get(sub, central)
        return {
            "tema_central_id": central,
            "extras_ids": [],
            "fora": central is None,
            "confianca": 0.5,  # modelos locais não dão confiança útil; a política não usa este valor
            "justificativa": str(trace["passo1"].get("assunto_cobrado") or "")[:300],
            "raw": trace,
            "attempts": attempts1 + attempts2,
            "latency_s": round(time.perf_counter() - started, 2),
        }
