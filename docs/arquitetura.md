# Arquitetura técnica

## Princípios

- **Segurança por abstenção:** erro de inferência ou divergência resulta em `revisar`, nunca em publicação implícita.
- **Classificação fechada:** o modelo escolhe somente IDs fornecidos pela taxonomia e candidatos recuperados.
- **Separação de responsabilidades:** recuperação lexical não decide publicação; decisão e exportação são módulos distintos.
- **Auditabilidade:** cada questão gera uma trilha JSON, além do resultado CSV; o PostgreSQL registra as execuções.
- **Reprodutibilidade:** hash dos dois arquivos de entrada, nome do modelo, limiares e decisões são associados ao run.

## Componentes

### 1. Ingestão e validação

`data.py` faz leitura linha a linha do JSONL, garante campos obrigatórios e IDs únicos, carrega a taxonomia e limpa HTML de enunciado/alternativas. O HTML é conteúdo, não código a executar. Ausências de metadados de origem são aceitas, pois o case explicita que os dados têm defeitos.

### 2. Taxonomia

`taxonomy.py` carrega IDs, pais, níveis e status. Verifica ciclos e pais inexistentes, expõe apenas temas ativos para seleção e implementa a regra de ramo: igualdade ou relação ancestral/descendente. Irmãos são diferentes. Os quatro nós raiz são contexto de disciplina e não são candidatos selecionáveis; candidatos são temas/subtemas ativos.

### 3. Recuperação de candidatos

`retrieval.py` combina TF-IDF de palavras/bigramas e n-gramas de caracteres. Isso ajuda com variações ortográficas e termos jurídicos recorrentes. `disciplina_origem` e `assunto_origem` dão um reforço pequeno, nunca são tratados como verdade. A lista de candidatos é limitada por `TOP_K_CANDIDATES`. A similaridade é uma medida de recuperação e não é gravada como confiança.

### 4. Classificação e verificação

`llm.py` chama Ollama com resposta JSON estruturada. A primeira inferência sugere decisão, tema central, extras, motivo e confiança. A segunda inferência julga a proposta independentemente, com acesso à questão e à lista de candidatos. O modelo recebe instrução explícita para não usar `fora` só por incerteza e para considerar que subtemas irmãos não são equivalentes.

### 5. Política de decisão

`decisions.py` valida IDs e aplica gates: publicação exige proposta `publicar`, verificador também `publicar`, concordância, temas ativos no conjunto de candidatos, relação do mesmo ramo e limiares de confiança. `fora` exige dois votos concordantes. Qualquer outro caso cai em revisão. Limiares são parâmetros, não promessa de precisão. A confiança autoatribuída precisa de calibração antes de uso real.

### 6. Persistência e artefatos

`pipeline.py` produz:

- `publicacao.csv`: contrato exato solicitado.
- `previsao.txt`: previsão derivada das confianças das publicadas (ou aviso de não estimável em baseline).
- `decision_audit.json`: candidatos, saídas dos estágios e erros por questão.
- `run_metadata.json`: hash da entrada, modelo, limiares, duração, chamadas concluídas e flag de precisão medida.
- `data_audit.json`: diagnóstico dos dados.

`db.py` grava `classification_runs` e `classification_decisions` em PostgreSQL, incluindo hash do dataset e trilha JSON. O CSV permanece o artefato de entrega; o banco é para acompanhamento e auditoria.

## Docker / serviços

- `app`: imagem Python imutável por build, execução one-shot para audit/classificação.
- `db`: PostgreSQL 16 com volume persistente e healthcheck.
- `ollama` (perfil `local-llm`): inferência local, armazenamento do modelo em volume.
- `adminer` (perfil `ops`): ferramenta opcional de inspeção do banco.

Não há serviço de fila ou API web nesta primeira versão, porque o case é batch/offline. Para produção com 50 mil questões semanais, adicionar fila apenas se latência/volume exigir; primeiro implementar loteamento, cache por hash da questão+taxonomia+modelo, retry com limite, métricas e painel da fila humana.

## Decisões que ainda precisam ser confirmadas

- Modelo/quantização e capacidade do hardware local.
- Se o verificador deve ser o mesmo modelo com prompt distinto ou um modelo independente menor.
- Limiar final após amostra humana e matriz de erro.
- Como o produto armazena extras e como um tema pai é apresentado na interface.
- SLA e responsável pela fila de revisão.
