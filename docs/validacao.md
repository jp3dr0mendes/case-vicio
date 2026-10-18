# Validação executada (18/10/2026)

Ambiente: macOS 15 (Darwin 24.6), Apple M2 Pro, 16 GB; Python 3.15 local (venv) e 3.12 no
container; Docker 28.4 / Compose 2.39; Ollama 0.40.6 nativo (Metal) e em container.

## Código
| Checagem | Resultado |
|---|---|
| `ruff check src tests` | OK, sem avisos (imports mortos removidos; `except` amplos só onde a falha precisa virar registro, anotados) |
| `python -m compileall -q src tests` | OK |
| `PYTHONPATH=src pytest -q` (local) | OK, 39 passed |
| Dependências | `scipy` passou a ser declarado (era usado diretamente e vinha só por tabela do scikit-learn) |

Os 39 testes cobrem: contrato dos dados e do CSV entregue; regra da árvore (pai/filho certo,
irmão errado, clones); política (12 cenários, inclusive falhas e "fora"); estimador de acurácias
em dados sintéticos; posterior; casamento estrito de texto; cliente Ollama com respostas simuladas
(dois passos, resposta à questão de concurso → falha auditável com resposta bruta, falha no passo 2
preserva o passo 1); reinterpretação dos 630 votos versionados com o código atual (idêntica);
medição (Clopper-Pearson, regra oficial, folha cega sem vazar decisões).

## Dados e entrega
| Checagem | Resultado |
|---|---|
| `data/input/*` × ZIP oficial (`anexos-case-ia.zip`) | 4/4 arquivos idênticos byte a byte |
| `python -m vicio_case.cli audit` | 359 questões, 377 nós, 375 ativos, 371 selecionáveis, inativos 5078/5234, 20 clones, 94 sem comando, 18 sem assunto, 1 sem disciplina |
| Contrato do `publicacao.csv` (validador do projeto e checagem independente sem o código do projeto) | OK: 359 linhas, IDs = originais, decisões válidas, temas ativos e não-raiz, nenhum clone publicado, "fora" sem tema, confiança `0.00`–`1.00`, motivo nas revisões |
| `previsao.txt` | 4 linhas no formato exato; cobertura declarada (0,28) = 100/359 |
| Determinismo | `classify` local (Python 3.15) e no container (3.12) → mesmo `publicacao.csv` (sha `0cc3a3cb…`); `folha-auditoria` idêntica |
| Páginas (PDF A4, fonte 11, gerado do Markdown) | relatório 3 páginas + memo 1 página = 4 (limite: 5) |
| `classify --mode baseline` | OK: 359 revisar (teste de contrato) |

## LLMs locais
| Checagem | Resultado |
|---|---|
| `run-llm --model qwen2.5:7b` (rodada completa) | 295/359 votos válidos; 64 inválidos registrados |
| `run-llm --model llama3.1:8b` (rodada completa) | 335/359 válidos; 24 inválidos registrados |
| Prompt | todos os 949 registros com a mesma versão e o mesmo sha de prompt (`ec5d05502fab`) |
| Ensaio com o código atual (nativo) | qwen e llama: 1/1 válida cada |
| Container → Ollama nativo (`host.docker.internal`) | 1/1 válida |
| Serviço `ollama` do Compose (perfil `local-llm`) | healthy; com qwen2.5:0.5b, 2 válidas e 2 falhas registradas com passo, 3 tentativas e resposta bruta |
| Ollama indisponível | falha explícita antes de processar; nenhum arquivo gravado |

## Docker e PostgreSQL
| Comando | Resultado |
|---|---|
| `docker compose config --quiet` / `build app` | OK |
| `docker compose up -d db` / `ps` | healthy; porta só em 127.0.0.1:5433 |
| `docker compose --profile run run --rm app audit` | OK (mesmos números) |
| `docker compose --profile run run --rm --entrypoint python app -m pytest -q -p no:cacheprovider` | 36 passed, 3 skipped (compose e entrega não vão para a imagem) |
| `docker compose --profile run run --rm app classify` | OK: run gravado; cada execução gera um novo registro (append-only) com 359 decisões, sem sobrescrever as anteriores; "fora" sem tema e demais com tema (constraint) |

## Medição da precisão
| Checagem | Resultado |
|---|---|
| `folha-auditoria` | 130 questões (100 publicadas + 30 controles), sem a decisão do sistema; testada no navegador |
| `medir-precisao` | mecânica testada (testes + ensaio pela CLI com rótulos artificiais); nenhuma medição real feita, porque não há rótulos humanos nem gabarito |

## Não executado / limitado (com motivo)
- Rodada completa de 7–8B dentro do container do Ollama: no macOS o container não usa a GPU e
  a máquina de 16 GB não comporta com folga; o caminho foi provado com um modelo pequeno e as
  rodadas reais usaram o Ollama nativo (mesmo código e API).
- Retentativa das falhas antigas com o casamento de texto atual: não refeita (mudaria votos sem
  necessidade); as falhas antigas guardam só a mensagem de erro.
- Precisão real: não medida (ver `docs/verificacao_precisao.md`).
