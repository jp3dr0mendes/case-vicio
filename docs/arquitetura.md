# Arquitetura

```
data/input/ (anexos oficiais, somente leitura)
        │
        ├─► audit ──────────────────────────────► artifacts/data_audit.json
        │
        ├─► [classificador principal] Claude Opus 5.5 (sessão Claude Code, protocolo em
        │        prompts/anotador_forte.md) ─────► data/anotacoes/claude_opus_5_5.psv
        │
        ├─► run-llm --model qwen2.5:7b  ┐  Ollama (nativo ou serviço do compose),
        ├─► run-llm --model llama3.1:8b ┘  hierárquico tema→subtema ─► artifacts/llm/<modelo>.jsonl
        │
        └─► classify --mode ensemble
                 │  annotations.py  normaliza e valida os 3 votos (inválido ≠ descartado)
                 │  decisions.py    política v3 (config/politica.json + clones + grupos ambíguos)
                 │  estimation.py   acurácias latentes por faixa de confiança, r, posterior
                 │  forecast.py     previsao.txt (com ajustes declarados em config/previsao.json)
                 │  data.py         validação do contrato do CSV (falha = não grava)
                 │  db.py           PostgreSQL append-only (se DATABASE_URL)
                 ▼
          artifacts/: publicacao.csv, previsao.txt, decision_audit.json,
                      estimativa.json, run_metadata.json
          raiz do repo (--deliver-dir .): cópias idênticas de publicacao.csv e previsao.txt
```

## Módulos

| Módulo | Responsabilidade |
|---|---|
| `data.py` | leitura do JSONL/CSV, limpeza de HTML, validação do contrato de saída |
| `taxonomy.py` | árvore, ancestrais, regra oficial (mesmo nó/pai/filho; irmão = erro), clones |
| `retrieval.py` | TF-IDF lexical: só sugestão de último recurso e modo `baseline` (não é probabilidade) |
| `llm.py` | cliente Ollama hierárquico, retries, casamento estrito da resposta |
| `runner.py` | execução retomável por modelo, uma linha JSON por questão (nas falhas: passo, resultado parcial e resposta bruta de cada tentativa) |
| `annotations.py` | formato único dos votos e validação contra a árvore |
| `decisions.py` | política publicar/revisar/fora, determinística e testada |
| `estimation.py` | estimativa de precisão sem gabarito |
| `forecast.py` | texto do `previsao.txt` |
| `pipeline.py` | orquestração, artefatos, metadados, hashes |
| `verification.py` | folha de auditoria cega e medição da precisão (Clopper-Pearson) contra rótulos humanos ou o gabarito |
| `db.py` | trilha de auditoria no PostgreSQL |
| `cli.py` | `audit`, `run-llm`, `classify`, `folha-auditoria`, `medir-precisao` |

## Política de decisão (v3)

1. Voto do principal inválido/ausente → **revisar** (sugestão do primeiro voto válido).
2. Principal diz "fora": **fora** só se confiança ≥ 0,90 e algum verificador também disser fora;
   senão **revisar** ("possível fora"). Dúvida nunca vira fora.
3. Tema escolhido é clone vazio → **revisar** com o nó original sugerido.
4. **Veto**: os dois verificadores concordam entre si num ramo diferente → **revisar**.
5. Confiança do principal < 0,75 → **revisar**.
6. Algum verificador concorda no ramo (mesmo nó, pai ou filho) → candidato a publicar, no nó mais
   geral dos dois (correto pela régua se o gabarito estiver em qualquer um deles).
   Sem concordância: publica só se confiança ≥ 0,90 e pelo menos um verificador respondeu
   validamente; senão **revisar**.
7. Ramo com nó concorrente (`grupos_ambiguos.json`) → exige confiança ≥ 0,90 e concordância de
   **todos** os verificadores; senão **revisar**.
8. **Portão final**: publicada só se a probabilidade estimada de acerto (posterior, coluna
   `confianca`) ≥ 0,95; abaixo disso → revisar. Na rodada final isso removeu todas as
   publicações "só por confiança alta", então toda publicada tem concordância de um verificador.
9. `extras_ids` só com temas do principal que não sejam do mesmo ramo do central nem clones.

Irmãos nunca contam como concordância. A coluna `confianca` é a posterior estimada com o
desconto de critério (docs/estimativa_precisao.md, seção 4), nunca a confiança declarada pelo LLM.

## Infraestrutura

- `db` PostgreSQL 16 (healthcheck, volume, porta só em 127.0.0.1).
- `app` (perfil `run`): imagem Python 3.12, usuário sem privilégio (UID configurável para
  escrever em `./artifacts`), dados/config montados somente leitura.
- `ollama` (perfil `local-llm`): servidor em container (porta 127.0.0.1:11435). No macOS o
  container não usa a GPU; as rodadas reais usaram o Ollama nativo (Metal) via
  `OLLAMA_BASE_URL=http://host.docker.internal:11434`. Ambos os caminhos foram testados.
- `adminer` (perfil `ops`) para inspeção do banco.

Sem Kafka, Airflow ou banco vetorial: o volume (359 questões) não justifica.
