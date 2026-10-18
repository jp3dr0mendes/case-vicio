# Case Vício — Classificação de tópicos

Implementação inicial, reproduzível e auditável para o case de classificação de 359 questões. O repositório separa **geração de candidatos**, **decisão semântica**, **verificação independente**, **política de publicação**, **trilha de auditoria** e **exportação**.

> **Importante — status honesto da entrega:** o modo `baseline` é uma triagem lexical e encaminha as 359 questões para `revisar`. Ele comprova o contrato de dados e gera sugestões de tópico, mas **não é uma publicação final para o aluno** e não afirma ter atingido precisão de 95%. Para gerar decisões semânticas, é necessário subir/configurar um modelo no Ollama e executar o modo `ollama`; mesmo assim, a precisão real precisa ser validada contra uma amostra rotulada/revisada por especialista, que não veio no ZIP.

## 1. O que o case pede

Para cada ID Q0001–Q0359, gerar `publicacao.csv` com exatamente uma linha e as colunas `id`, `decisao`, `tema_central_id`, `extras_ids`, `confianca`, `motivo`. As decisões permitidas são `publicar`, `revisar` e `fora`. Tema central é obrigatório nas duas primeiras, vazio em `fora`, e o motivo é obrigatório para `revisar`/`fora`. O objetivo é maximizar a cobertura publicada sem ficar abaixo de 95% de precisão. A regra de avaliação aceita nós pai/filho do mesmo ramo, mas não subtemas irmãos.

## 2. Stack

- Python 3.12, pandas e scikit-learn para carga, limpeza e recuperação lexical dos candidatos.
- Ollama opcional para inferência local com saída JSON estruturada, sem dependência de API paga.
- PostgreSQL 16 para histórico de execução, resultados e rastreabilidade.
- Docker Compose para subir os serviços; Adminer é opcional e fica atrás do perfil `ops`.
- pytest para testes unitários, integração local e contrato dos arquivos.

A infraestrutura é deliberadamente pequena. Não há necessidade de Kafka, Airflow, vector database ou arquitetura de agentes para uma taxonomia de 377 nós e um lote de 359 questões. Para 50 mil questões semanais, ampliar primeiro loteamento, cache e monitoramento antes de adicionar componentes distribuídos.

## 3. Pré-requisitos

- Docker Engine e Docker Compose v2 instalados.
- Para classificação semântica local, memória/CPU compatíveis com o modelo escolhido; GPU é opcional e não é pressuposta.

Crie seu `.env` a partir do exemplo:

```bash
cp .env.example .env
```

No Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Em Linux/macOS, ajuste `APP_UID` e `APP_GID` para os IDs do usuário que deve gravar a pasta `artifacts` (por exemplo, `id -u` e `id -g`). Altere `POSTGRES_PASSWORD` e mantenha `DATABASE_URL` coerente com as mesmas credenciais. Não comite `.env`.

## 4. Subir infraestrutura e executar a baseline

```bash
docker compose up -d db
docker compose --profile run run --rm app audit
docker compose --profile run run --rm app classify --mode baseline
```

A baseline deve gerar:

- `artifacts/publicacao.csv`: 359 sugestões; todas em `revisar` por segurança.
- `artifacts/previsao.txt`: aviso explícito de que a precisão não é estimável sem questões publicadas.
- `artifacts/decision_audit.json`: candidatos lexicais e dados de auditoria por questão.
- `artifacts/run_metadata.json`: hash de entrada, versão Python, modelo, limiares, duração, contagem de chamadas e status da medição de precisão.
- `artifacts/data_audit.json`: estatísticas de qualidade do lote.

## 5. Executar com LLM local (Ollama)

Primeiro, suba o servidor local e baixe o modelo configurado em `.env`:

```bash
docker compose --profile local-llm up -d ollama
docker compose exec ollama ollama pull qwen2.5:7b
```

Depois, execute a classificação com o segundo estágio de verificação:

```bash
docker compose --profile run run --rm app classify --mode ollama
```

Para inspecionar o PostgreSQL pela interface opcional, suba `docker compose --profile ops up -d adminer` e abra `http://localhost:8080`; use `db` como servidor, a base/usuário/senha configurados em `.env`.

O pipeline tenta duas chamadas por questão: (1) classificar dentro da lista fechada de candidatos e (2) verificar a proposta. Só pode publicar quando ambos os estágios recomendam publicação, concordam no mesmo ramo hierárquico e ultrapassam os limiares configurados (`PUBLISH_THRESHOLD=0.95`, `VERIFY_THRESHOLD=0.90`). Divergências, erros de rede/modelo, temas inativos ou IDs inválidos viram revisão. `fora` também exige concordância dos dois estágios.

A confiança produzida pelo LLM ainda é autoavaliada e não equivale a uma probabilidade calibrada. Ajuste o limiar apenas após análise de erros e validação humana; não trate os valores padrão como garantia de 95%.

## 6. Rodar e testar sem Docker

```bash
python -m venv .venv
# ative o ambiente virtual e instale as dependências:
pip install -r requirements.txt
PYTHONPATH=src python -m vicio_case.cli audit --data-dir data/input --artifacts-dir artifacts
PYTHONPATH=src python -m vicio_case.cli classify --mode baseline --data-dir data/input --artifacts-dir artifacts
PYTHONPATH=src pytest -q
```

Para execução local com Ollama, defina `OLLAMA_BASE_URL` e `OLLAMA_MODEL` no ambiente e use `--mode ollama`.

## 7. Arquitetura e limites

```text
questoes.jsonl + temas.csv
          |
          v
 validação e limpeza HTML
          |
          v
 recuperação de candidatos (TF-IDF palavra + caracteres)
          |
          +---- baseline: todos em revisão
          |
          v
 LLM classificador (Ollama, JSON fechado)
          |
          v
 verificador independente
          |
          v
 política conservadora + validação da árvore
          |
          +---- publicacao.csv / previsao.txt
          +---- trilha JSON de decisão
          +---- PostgreSQL: execução e decisões
```

A similaridade lexical serve para busca de candidatos, não como confiança final. O LLM só vê uma lista limitada de temas ativos. A política final faz validação adicional de IDs e da hierarquia. A interface com especialista ainda é uma etapa futura, não está implementada nesta versão.

## 8. Arquivos de documentação

- `docs/entendimento_case.md`: requisitos e interpretação da régua.
- `docs/arquitetura.md`: componentes, fluxo e decisões técnicas.
- `docs/plano_controle.md`: gates de qualidade, critérios e respostas a falhas.
- `docs/diagnostico_dados.md`: análise do material recebido.
- `docs/relatorio_case.md`: relatório técnico em formato Markdown.
- `docs/memo_professor.md`: memo não técnico de uma página.
- `docs/roadmap.md`: próximos passos priorizados.
- `docs/validacao.md`: testes executados e limitações do ambiente.

## 9. O que falta antes de entregar o case

1. Executar o modo Ollama com um modelo definido e registrar exatamente a versão, tempo e configuração.
2. Revisar manualmente amostra estratificada de publicações sugeridas; conferir especialidade, subtema e árvore pai/filho.
3. Rever falsos positivos/falsos negativos e ajustar política/recuperação.
4. Definir previsão de precisão e cobertura em `previsao.txt` após a rodada final; confirmar que a política tem cobertura maior que zero e evidência suficiente para sustentar a previsão.
5. Publicar o repositório GitHub com os artefatos finais e registrar qualquer ajuste manual.

**Não publique o artefato `baseline` como resposta final do case.** Ele é o fallback seguro, não a solução semântica final.
