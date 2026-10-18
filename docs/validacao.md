# Validação executada (18/10/2026)

Ambiente: macOS 15 (Darwin 24.6), Apple M2 Pro, 16 GB; Python 3.15 local (venv) e 3.12 no
container; Docker 28.4 / Compose 2.39; Ollama 0.40.6 nativo (Metal) e em container.

## Comandos e resultados

| Comando | Resultado |
|---|---|
| `python -m compileall -q src tests` | OK |
| `PYTHONPATH=src pytest -q` (local) | OK — 29 passed (inclui `test_entrega.py` sobre o CSV final) |
| `python -m vicio_case.cli audit` | OK — 359 questões, 377 nós, 375 ativos, 371 selecionáveis, 20 clones |
| `python -m vicio_case.cli classify --mode baseline` | OK — 359 revisar (teste de contrato) |
| `python -m vicio_case.cli run-llm --model qwen2.5:7b` | OK — 295/359 válidas após 1ª passada + retentativas (64 inválidas registradas: nome ambíguo ou fora das opções) |
| `python -m vicio_case.cli run-llm --model llama3.1:8b` | OK — 335/359 válidas após 1ª passada + retentativa com casamento corrigido |
| `python -m vicio_case.cli classify --mode ensemble --deliver-dir .` | OK — 100 publicar / 258 revisar / 1 fora; CSV validado pelo contrato |
| `docker compose config --quiet` | OK |
| `docker compose build app` | OK |
| `docker compose up -d db` / `docker compose ps` | OK — `db` healthy, porta só em 127.0.0.1:5433 |
| `docker compose --profile run run --rm app audit` | OK |
| `docker compose --profile run run --rm --entrypoint python app -m pytest -q` | OK — 25 passed, 3 skipped (compose e entrega não estão na imagem) |
| `docker compose --profile run run --rm app classify` (ensemble e baseline) | OK — runs gravados no PostgreSQL (última: 100/258/1; mesma saída sha `ed9e4fef…` no Python 3.15 local e 3.12 no container) |
| `docker compose --profile local-llm up -d ollama` | OK — healthy, Ollama 0.40.6 |
| `docker compose exec ollama ollama pull qwen2.5:0.5b` + `app run-llm --model qwen2.5:0.5b --limit 2` | OK — 2/2 respostas válidas pela rede interna do compose |
| `app run-llm` com `OLLAMA_BASE_URL=http://host.docker.internal:11434` | OK — container usando o Ollama nativo |
| Ollama indisponível (`OLLAMA_BASE_URL=http://localhost:9`) | falha explícita antes de processar (nenhuma linha gravada) |

## Não executado / limitado (com motivo)

- `docker compose exec ollama ollama pull qwen2.5:7b` + rodada completa **no container**:
  não executado. No macOS o container não acessa a GPU; a VM do Docker tem 8 GB e o host já
  estava com swap esgotado ao carregar modelos de 7–8B. As rodadas completas usaram o Ollama
  nativo (mesmo código, mesma API). O caminho do container foi provado com um modelo pequeno.
- qwen2.5:14b: testado e abandonado (não cabe na GPU; 18% em CPU).
- **Precisão real: não medida** — não há gabarito no pacote do case.

## Checagens de contrato automatizadas (tests/test_entrega.py, data.py)
359 linhas, IDs = conjunto original, sem duplicatas; decisões ∈ {publicar, revisar, fora};
tema central obrigatório e selecionável (ativo, não-raiz) em publicar/revisar e vazio em fora;
extras válidos, sem repetir o central; confiança numérica em [0,1]; motivo obrigatório em
revisar/fora; nenhum clone publicado; cópia da raiz idêntica a `artifacts/`.

## Checagem de transcrição do classificador principal
Para as 359 anotações, o rótulo do `tema_central_id` gravado foi comparado com a justificativa
escrita: nenhum ID trocado.
