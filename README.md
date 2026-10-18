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
  justificados na seção de decisões tomadas à mão.

## Próximos passos (com mais tempo)

A ordem que eu seguiria é: medir a precisão com a conferência cega das 100 publicadas, consertar a
árvore de temas com o professor, montar um conjunto de avaliação para testar modelos e prompts,
colocar o pipeline em produção em modo sombra numa disciplina e só depois liberar com revisão humana
e monitoramento. O detalhe de cada parte está abaixo.

### Arquitetura para deploy

O volume do problema (cerca de 50 mil questões por semana) cabe numa arquitetura simples, sem
Kafka ou orquestrador dedicado. A imagem Docker deste repositório vira a base de um worker, e o
PostgreSQL, que já guarda execuções e decisões, também serve de fila.

```
importação de questões (lote semanal ou cadastro avulso)
        |
        v
fila de jobs no PostgreSQL (SELECT ... FOR UPDATE SKIP LOCKED)
        |
        v
worker de classificação (container)
   1. normalização e deduplicação (hash do enunciado + embeddings)
   2. candidatos por embeddings (top-20)
   3. classificador treinado com as revisões do professor
   4. LLM só nas questões incertas (API, com cache por hash da questão)
   5. política e probabilidade de acerto (decisions.py / estimation.py)
        |
        +--> publicar: entra no ar
        +--> revisar:  fila do professor, com sugestão e motivo
        +--> fora:     lista de temas a criar
        |
        v
registro de cada decisão (classification_runs / classification_decisions)
```

Os componentes seriam:

- Uma API pequena (por exemplo FastAPI) para classificar uma questão nova na hora do cadastro, e o
  mesmo worker em lote para as importações grandes, ambos a partir da imagem atual.
- PostgreSQL gerenciado, com as tabelas que já existem mais uma tabela de revisões humanas.
- LLM por API com chaves num gerenciador de segredos, limite de requisições e cache; um servidor
  próprio em GPU (vLLM ou Ollama) só se custo ou privacidade justificarem.
- Containers num serviço gerenciado (Cloud Run, ECS Fargate ou equivalente), com agendamento
  semanal para os lotes e disparo na importação.
- CI rodando os testes atuais e a avaliação no conjunto rotulado antes de promover qualquer versão
  nova de prompt, modelo ou política.

Para colocar no ar com segurança, eu começaria em modo sombra: o pipeline classifica, mas não
publica, e as decisões são comparadas com a classificação atual da plataforma e com as revisões do
professor. Depois liberaria por disciplina, com a versão da política como chave de ativação, de
forma que voltar atrás seja só trocar a versão. O painel de acompanhamento mostraria cobertura,
tamanho da fila de revisão, precisão medida na amostra semanal (com intervalo de confiança), custo
por questão, latência, taxa de respostas inválidas do LLM e mudança na distribuição de temas por
lote importado.

### Revisão humana no circuito

- Uma tela de revisão com a questão, o tema sugerido, as duas alternativas mais prováveis e o
  motivo da dúvida, com atalhos para confirmar, corrigir, marcar como fora ou propor um tema novo.
- A fila ordenada por impacto e incerteza: primeiro os temas e bancas mais estudados e as questões
  com menor probabilidade de acerto.
- Cada correção vira rótulo. Toda semana, as acurácias e os limiares são recalibrados, o
  classificador é retreinado e os exemplos usados nos prompts são atualizados.
- O botão de "tema errado" para o aluno tira a questão do ar e a coloca na fila com prioridade.
- Dupla revisão em cerca de 10% das questões, para medir a concordância entre especialistas. Esse
  número é o teto realista de precisão e substitui o desconto de critério que hoje é declarado (4%).
- Conferência cega mensal de uma amostra das publicadas, com a folha e o comando que já existem
  (`folha-auditoria` e `medir-precisao`).
- Curadoria da árvore com o professor: fundir os temas duplicados, criar temas a partir das
  questões "fora" e escrever descrições úteis (hoje 20 temas não têm descrição e muitos só têm um
  texto genérico do tipo "Subtema de X").
- Acompanhar o tempo médio de revisão e a taxa de sugestões confirmadas; se a confirmação passar de
  90% numa faixa, é sinal de que dá para publicar mais nela.

### Testar outros modelos

- Montar um conjunto de avaliação congelado e versionado a partir da conferência cega e das
  revisões do professor (500 a 1.000 questões rotuladas).
- Criar um comando de avaliação que, para cada combinação de modelo e prompt, informe a precisão
  pela régua oficial, a cobertura possível mantendo 95%, o custo, a latência e a taxa de respostas
  inválidas. O `run-llm` já aceita `--model` para qualquer modelo do Ollama; um modelo por API
  entraria como outro cliente com a mesma interface.
- Candidatos a comparar: verificadores locais maiores em GPU (qwen2.5:32b, Llama de 70B), modelos
  por API de custo menor (Claude Haiku 5.5 e Sonnet 5.5) contra o Claude Opus 5.5, ao menos um
  modelo de outra família para manter os votos independentes, embeddings multilíngues para a etapa
  de candidatos e o classificador treinado como linha de base barata.
- Regra para trocar de modelo: só promover se aumentar a cobertura mantendo o limite inferior do
  intervalo de confiança da precisão em 95% ou mais.

### Engenharia de prompt

- Continuar versionando cada prompt (o código já registra versão e hash) e guardar o resultado de
  cada experimento no conjunto de avaliação.
- Incluir no prompt as descrições dos temas, depois de reescritas com o professor.
- Usar exemplos para os pares que mais confundem (ação penal em Penal ou Processo Penal, Juizado
  Especial, regime de pena), com o motivo de cada escolha, tirados das revisões reais.
- Escrever regras de desempate explícitas para os assuntos que existem em dois ramos, assim que o
  professor definir onde cada um fica.
- Pedir a justificativa, com o dispositivo legal cobrado, antes do tema.
- Testar autoconsistência (várias respostas por questão, usando a concordância entre elas como
  sinal de confiança).
- Criar um passo inicial que identifique questões que misturam capítulos e as mande direto para
  revisão.
- Nos modelos locais, trocar nomes longos de opção por códigos curtos, para reduzir respostas que
  não batem com a lista.
- Tratar mudança de prompt como mudança de código: toda versão passa pelo conjunto de avaliação, e
  testes como `tests/test_llm_outputs.py` acusam quando uma mudança altera votos já registrados.
