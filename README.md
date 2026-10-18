# Case Vício: classificação de questões por tópico

Classificação de 359 questões de concurso (Penal, Processo Penal, Legislação Penal Especial e
Criminologia) na árvore de temas da plataforma, decidindo para cada uma entre publicar, revisar ou
fora, com a meta de pelo menos 95% de precisão nas publicadas e a maior cobertura possível. Enunciado original: [`docs/enunciado_case_vicio.pdf`](docs/enunciado_case_vicio.pdf).

## Entregáveis (raiz do repositório)

| Arquivo | Conteúdo |
|---|---|
| [`publicacao.csv`](publicacao.csv) | decisão para as 359 questões no formato do `entrega_modelo.csv` |
| [`previsao.txt`](previsao.txt) | precisão e cobertura previstas, com intervalo e metodologia |
| [`relatorio_case.md`](relatorio_case.md) | relatório (raciocínio, diagnóstico, produção) |
| [`memo_professor.md`](memo_professor.md) | memo de 1 página para o professor |

`publicacao.csv` e `previsao.txt` da raiz são cópias byte a byte de `artifacts/` (o teste
`tests/test_entrega.py` garante isso).

## Resultado

| | |
|---|---|
| publicar | 100 (28%) |
| revisar | 258 (todas com tema sugerido e motivo) |
| fora | 1 |
| precisão prevista | 0,95 (intervalo 0,85–0,98), prevista e não medida, porque não há gabarito |
| cobertura prevista | 0,28 (0,26–0,30) |

Modelos: Claude Opus 5.5 via Claude Code (classificador principal) e qwen2.5:7b e llama3.1:8b
(verificadores, Ollama 0.40.6 local). Custo: nada além da assinatura do Claude Code. Tempo: cerca de
20 minutos de classificação pelo modelo principal, 75 minutos de inferência local na primeira
passada dos dois modelos e mais 1 hora de novas tentativas (Apple M2 Pro, 16 GB); a política roda em
segundos.

## Como a classificação é feita

1. Classificador principal: o Claude Opus 5.5, via Claude Code, classificou as 359 questões com a
   árvore completa (protocolo em
   [`prompts/anotador_forte.md`](prompts/anotador_forte.md); saída versionada em
   `data/anotacoes/claude_opus_5_5.psv`, sem edição manual).
2. Verificadores independentes: qwen2.5:7b e llama3.1:8b via Ollama, em dois passos (tema e
   depois subtema), com os prompts em [`prompts/classificacao.md`](prompts/classificacao.md)
   (inclui as versões descartadas e por quê).
3. Política determinística ([`docs/arquitetura.md`](docs/arquitetura.md),
   `config/politica.json`): concordância de ramo (mesmo nó, pai ou filho; irmão não conta), veto,
   temas vazios duplicados nunca publicados e mais evidência em assuntos que existem em outro ramo.
   Falha ou dúvida vão para revisão com sugestão.
4. Estimativa sem gabarito ([`docs/estimativa_precisao.md`](docs/estimativa_precisao.md)):
   acurácias latentes com três classificadores, probabilidade de acerto por questão (que decide a
   publicação) e desconto declarado para divergência de critério; a coluna `confianca` é essa
   probabilidade já descontada.

## Decisões tomadas à mão

| Decisão | Onde | Motivo |
|---|---|---|
| 20 temas duplicados ligados ao original | `config/nos_duplicados.json` | não publicar em tema vazio |
| 18 grupos de assuntos em mais de um ramo | `config/grupos_ambiguos.json` | mais evidência onde há duas respostas defensáveis |
| Limiares de 0,75, 0,90 e 0,95 | `config/politica.json` | o de 0,95 veio da curva de cobertura × precisão estimada |
| Desconto de 4% (2% a 7%) para divergência de critério | `config/previsao.json` | risco que nenhum modelo enxerga |
| Anotação do classificador principal | `data/anotacoes/` | saída do modelo, sem edição posterior |

## Uso de IA

O enunciado libera o uso de IA e pede que os modelos sejam informados. Usei o Claude Opus 5.5 em
dois papéis. No primeiro, ele é um dos classificadores do pipeline: classificou as 359 questões, e a
saída está versionada sem edição em `data/anotacoes/`. No segundo, usei o Claude Code como
assistente para implementar o código, os testes e a infraestrutura e para redigir a documentação,
seguindo as minhas orientações (os commits registram essa coautoria). As decisões e os resultados
são de minha responsabilidade, e tudo o que é afirmado aqui pode ser reproduzido com os comandos
abaixo.

Diagnóstico dos dados: [`docs/diagnostico_dados.md`](docs/diagnostico_dados.md).
Como checar a precisão real e revalidação contra o enunciado:
[`docs/verificacao_precisao.md`](docs/verificacao_precisao.md).
Validação executada: [`docs/validacao.md`](docs/validacao.md). Próximos passos:
[`docs/roadmap.md`](docs/roadmap.md).

## Estrutura

```
src/vicio_case/   data, taxonomy, retrieval, llm, runner, annotations, decisions,
                  estimation, forecast, pipeline, verification, db, cli
tests/            contratos de dados, regra da árvore, política, estimador, entrega, medição
config/           politica.json, nos_duplicados.json, grupos_ambiguos.json, previsao.json
prompts/          prompts dos classificadores
data/input/       anexos oficiais (idênticos ao ZIP do case)
data/anotacoes/   votos do classificador principal
auditoria/        folha de auditoria cega (HTML offline) e amostra
artifacts/        saídas: llm/*.jsonl, publicacao.csv, previsao.txt, decision_audit.json,
                  estimativa.json, run_metadata.json, data_audit.json, experimentos/
```

## Como rodar

### Local (Python 3.12+)

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

```bash
PYTHONPATH=src .venv/bin/pytest -q
```

```bash
PYTHONPATH=src .venv/bin/python -m vicio_case.cli audit
```

Classificadores locais (precisa do [Ollama](https://ollama.com) com os modelos baixados; a
execução é retomável e grava `artifacts/llm/<modelo>.jsonl`):

```bash
ollama pull qwen2.5:7b && ollama pull llama3.1:8b
```

```bash
PYTHONPATH=src .venv/bin/python -m vicio_case.cli run-llm --model qwen2.5:7b
```

```bash
PYTHONPATH=src .venv/bin/python -m vicio_case.cli run-llm --model llama3.1:8b
```

Política + estimativa + entrega (gera `artifacts/*` e copia `publicacao.csv`/`previsao.txt`
para a raiz):

```bash
PYTHONPATH=src .venv/bin/python -m vicio_case.cli classify --mode ensemble --deliver-dir .
```

`--mode baseline` gera uma versão só lexical (tudo em revisar) para testar o contrato.

Medir a precisão real com rótulos humanos (auditoria cega) ou com o gabarito da Vício
(detalhes em [`docs/verificacao_precisao.md`](docs/verificacao_precisao.md)):

```bash
PYTHONPATH=src .venv/bin/python -m vicio_case.cli folha-auditoria
```

```bash
PYTHONPATH=src .venv/bin/python -m vicio_case.cli medir-precisao --rotulos rotulos_auditoria.csv
```

### Docker

```bash
cp .env.example .env
```

```bash
docker compose up -d db
```

```bash
docker compose --profile run run --rm app audit
```

```bash
docker compose --profile run run --rm app classify --mode ensemble
```

Testes dentro do container:

```bash
docker compose --profile run run --rm --entrypoint python app -m pytest -q -p no:cacheprovider
```

Ollama em container (perfil `local-llm`; no macOS roda só em CPU; para usar a GPU, rode o
Ollama nativo e defina `OLLAMA_BASE_URL=http://host.docker.internal:11434` no `.env`):

```bash
docker compose --profile local-llm up -d ollama
```

```bash
docker compose exec ollama ollama pull qwen2.5:7b
```

```bash
docker compose --profile run --profile local-llm run --rm app run-llm --model qwen2.5:7b
```

No Linux, defina `APP_UID`/`APP_GID` no `.env` com o seu `id -u`/`id -g` para o container
escrever em `./artifacts`. O banco recebe uma linha por execução (append-only) em
`classification_runs` e uma por questão em `classification_decisions`; o perfil `ops` sobe o
Adminer em `127.0.0.1:8080`.

## Reprodutibilidade

`artifacts/run_metadata.json` registra: SHA-256 de cada entrada (questões, temas, configs,
anotações, saídas dos LLMs), versão do prompt e da política, limiares, contagens por decisão e
estrato, falhas dos LLMs, `publicacao_sha256`, duração e o `run_id` no banco. A etapa
`classify` é determinística dadas as mesmas entradas. As chamadas aos LLMs locais usam
temperatura 0 e seed fixa (retentativas a 0,3), mas o Ollama não garante bit a bit entre
versões/hardware; por isso as respostas usadas estão versionadas em `artifacts/llm/`.

## Limitações

- Não há gabarito no pacote: a precisão é prevista, não medida.
- O classificador principal rodou de forma interativa no Claude Code; para refazer exatamente a
  classificação é preciso o mesmo modelo, e por isso o arquivo versionado é a entrada da política.
- Os verificadores locais são modelos pequenos (7–8B); com hardware maior, a cobertura subiria.
- Os parâmetros manuais (clones, grupos ambíguos, desconto) estão declarados em `config/` e
  justificados no relatório.
