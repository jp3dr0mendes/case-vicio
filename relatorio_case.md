# Relatório — Case de classificação de tópicos (Vício · Método VDE)

João Pedro Mendes Albuquerque · 18/10/2026 · repositório: https://github.com/jp3dr0mendes/case-vicio

**Resultado em uma linha:** publiquei **100 das 359 questões (28%)** com precisão prevista de **0,95** (intervalo 0,85–0,98); 258 vão para revisão com sugestão e motivo; 1 é "fora" (Direito Tributário). Precisão **prevista**, não medida: o pacote não tem gabarito.

## a) Como pensei

**A pergunta certa não é "qual tema?", é "quando posso confiar no tema?"** Um LLM acerta a
maioria das questões; o problema é que não sabemos *quais*. Por isso desenhei o sistema em
torno de três coisas: (1) um classificador forte; (2) sinais **independentes** que permitam
estimar quando ele erra; (3) uma política que só publica onde a evidência sustenta ≥ 95%,
mandando o resto para o professor **com a sugestão**.

**Hipóteses que guiaram o trabalho**
1. Os metadados de origem são ruidosos. Confirmada: das 43 questões marcadas "Concurso de
   Crimes", só 2 tratam disso (é a "lixeira" descrita no enunciado).
2. A maior fonte de erro não é o assunto, é **qual nó** da árvore. Confirmada: a árvore tem 20
   nós-clone vazios e assuntos repetidos em ramos diferentes; a régua pune o "irmão".
3. Sem gabarito, a única forma honesta de prever precisão é **comparar classificadores que erram
   de forma diferente**. Daí três votos de famílias distintas e um modelo de acurácias latentes.

**O que testei e descartei (becos sem saída, todos registrados no repositório)**
- *Baseline lexical (TF-IDF)* da implementação anterior: útil para testar o contrato, inútil para
  publicar (similaridade não é probabilidade). Mantido só como `--mode baseline`.
- *Restringir o LLM ao top-12 lexical*: o tema certo muitas vezes nem entrava na lista (a
  similaridade lexical é enganada justamente pelos metadados ruidosos). Substituído pela árvore
  inteira.
- *qwen2.5:7b com a árvore inteira respondendo `tema_id`*: o modelo **trocava dígitos** (Lei
  Antiterrorismo 4706 → Estatuto do Idoso 4696). Concordância de ramo com o principal ≈ 25%.
  Parcial em `artifacts/experimentos/`.
- *Decodificação restrita (enum com os 371 caminhos)*: enviesou para as primeiras opções em ordem
  alfabética ("Criminologia > …").
- *Pedir "escolha"*: o modelo **respondia a questão de concurso** ("B: I e III"). Corrigido com
  instrução explícita e a questão delimitada.
- *qwen2.5:14b*: não cabe na GPU da máquina (16 GB; 18% em CPU, swap esgotado).
- *Verificador que vê a proposta do principal*: descartado por deferência — mata a independência
  que a estimativa exige.
- *Publicar por confiança alta do LLM sem concordância de ninguém* (desde que não houvesse
  veto): testei para ganhar cobertura. A calibração mostrou que essas questões têm probabilidade
  estimada de acerto ~0,3–0,7 — a confiança autodeclarada quase não discrimina. O portão final
  (probabilidade estimada ≥ 0,95) eliminou todas elas: na prática, **publicar exige que um modelo
  independente concorde no ramo**.

**O pipeline final**
1. *Classificador principal*: Claude Opus 5.5 (rodando na própria sessão do Claude Code)
   anotou as 359 questões em lotes, com a árvore completa e o mesmo regulamento do prompt local,
   antes de ver as respostas dos verificadores. Saída versionada sem edição manual.
2. *Verificadores*: qwen2.5:7b e llama3.1:8b via Ollama, em dois passos (tema → subtema), com
   casamento estrito da resposta (resposta ambígua vira inválida, nunca palpite).
3. *Política* (`config/politica.json`, `decisions.py`, testada): regras duras (nunca em
   nó-clone; ramo com nó concorrente exige confiança ≥ 0,90 e concordância de todos; veto quando
   os dois verificadores concordam entre si contra o principal; confiança < 0,75 → revisar;
   falha/resposta inválida → revisar) e, por cima, o **portão de probabilidade estimada ≥ 0,95**
   (posterior por questão, item 4). Tudo o que não passa vai para revisão com sugestão e motivo.
   "Fora" só com consenso.
4. *Estimativa* (`docs/estimativa_precisao.md`): acurácias latentes por faixa de confiança,
   erro coincidente medido, posterior por questão (é a coluna `confianca`), desconto declarado
   por divergência de critério.

## Resultados

| Decisão | Questões | Estrato (motivo) |
|---|---|---|
| publicar | 100 | 73 concordância exata com verificador; 27 concordância pai/filho |
| revisar | 258 | 123 confiança baixa do principal; 42 ramo com nó concorrente; 32 probabilidade estimada < 0,95; 28 divergência; 26 veto dos verificadores; 5 sem verificação válida; 2 possível "fora" |
| fora | 1 | Q0142 (ITCD, Direito Tributário) |

**Calibração (o que mais me surpreendeu).** A concordância bruta com os verificadores cresce
com a confiança declarada pelo principal (dois verificadores concordando: 10% das questões com
confiança ≤ 0,35 contra 32% das com ≥ 0,90), então essa confiança discrimina. Mas o modelo de
acurácias latentes atribui boa parte dessa diferença aos *verificadores* (questão difícil é
difícil para todos): a acurácia estimada do principal fica ~0,78 no geral (0,83 alta · 0,74
média · 0,80 baixa, com intervalos largos). Consequência prática: publicar "porque o LLM disse
0,95" daria ~0,80; o que separa as questões seguras é a **concordância de modelos
independentes**. Com o portão de probabilidade estimada ≥ 0,95, as 100 publicadas têm média
estimada de 0,985 antes do desconto de critério. Verificadores: qwen2.5:7b ~0,50 e llama3.1:8b
~0,69; r (erro coincidente) medido = 0,25.

| Portão (probabilidade estimada) | Publicadas | Precisão média estimada |
|---|---|---|
| nenhum (só política) | 132 | 0,884 |
| 0,90 | 101 | 0,984 |
| **0,95 (escolhido)** | **100** | **0,985** |
| 0,98 | 65 | 0,997 |

**Previsão** (`previsao.txt`): 0,985 do modelo estatístico × (1 − 4% de divergência de critério)
= **0,95**; intervalo 0,85–0,98 (bootstrap das acurácias, r entre metade e o dobro, desconto
2–7%). Cobertura 0,28. Reli as 100 publicadas: nenhum erro de assunto encontrado, ~5 com nó
alternativo defensável (sustenta o desconto). **Risco declarado fora do intervalo:** 23
publicadas estão em nós originais de Legislação Especial que têm cópia vazia em Penal; se o
gabarito usar as cópias, a precisão cairia para ~0,73.

**Execução**: verificadores locais com 295 (qwen) e 335 (llama) respostas válidas de 359 — as
inválidas (nome ambíguo, resposta fora das opções) contam como "sem voto", nunca como palpite.


## b) Diagnóstico — o que atrapalha a classificação

Detalhes e contagens em `docs/diagnostico_dados.md`. Em resumo:

1. **A árvore se contradiz.** 20 nós ativos sem descrição nem subtemas duplicam nós com conteúdo
   ("Teoria da Pena (Parte 2)", "Competência (Parte 1)", cópias de leis especiais dentro de
   Penal). Um especialista e uma máquina podem escolher "o mesmo assunto" em nós irmãos, e a régua
   conta como erro.
2. **O mesmo instituto mora em dois ramos.** Ação penal (Penal × Processo Penal × Punibilidade),
   Juizado Especial (Legislação Especial × Procedimento Sumaríssimo), regime de pena (Penal ×
   Sentença), execução penal (LEP × livramento × indulto). Essas questões têm duas respostas
   defensáveis.
3. **Temas inativos deixam órfãos.** Sem "Direito penal econômico", questões de cartel, ordem
   tributária e sistema financeiro não têm casa natural.
4. **Questões "colcha de retalhos"** (~20): quatro ou cinco assertivas de capítulos diferentes.
   Não existe tema central; é a classe mais difícil, para humano e máquina.
5. **Texto defeituoso:** comandos gerados que não batem com a questão ("Explique…" em itens
   Certo/Errado), enunciados que citam situação ausente (Q0219), OCR corrompido (Q0078).
6. **Metadados de origem enganam** (as "lixeiras"): servem como pista fraca de disciplina, nunca
   de tema.

**Questões difíceis**: as dos itens 2 e 4, e as de criminologia crítica (labeling × processos de
criminalização × teorias da pena), em que os nomes dos temas se sobrepõem.

**Como checar a precisão real.** Sem gabarito ela não pode ser comprovada, só prevista. Deixei
pronta uma auditoria cega (`folha-auditoria` → HTML offline com as 100 publicadas + 30 controles,
sem mostrar a decisão do sistema) e a medição (`medir-precisao`, régua oficial + intervalo exato
de Clopper-Pearson), que também aceita o gabarito da Vício. Auditando as 100, até 1 erro ainda
comprova ≥ 95%. Atenção ao ruído da própria régua: com ~100 publicadas, mesmo um sistema com
95% reais só "mede" ≥ 95% em ~62% das vezes (97% reais → ~92%). Detalhes, sensibilidade e a
alternativa conservadora (58 publicadas, previsão ~0,96) em `docs/verificacao_precisao.md`.

## c) Produção — 50 mil questões por semana

**Momento da empresa.** A Vício está expandindo do Método VDE para a OAB para o *VDE Carreiras
Jurídicas* (Magistratura, MP, Defensoria, Procuradorias, Delegado), com "+50 mil questões
comentadas" organizadas por banca, tema e nível e um assistente de IA (vic.IA). Esse é o
contexto do problema: importação em massa de questões de outras fontes, classificação
automática que gerou "lixeiras" e uma árvore em reestruturação (os nós "(Parte 1/2)" e as cópias
vazias). O desenho abaixo aproveita o que já existe (a vic.IA já usa LLM e o acervo comentado
da casa) e prioriza o que protege a confiança de quem paga R$ 2,5–4,3 mil por ano.

**Arquitetura em camadas (custo cresce só onde há dúvida):**
1. *Normalização + deduplicação* (hash do enunciado; embeddings para quase-duplicatas): questões
   repetidas herdam a classificação revisada.
2. *Recuperação semântica*: embeddings (ex.: modelo multilíngue pequeno, ~US$ 0,00002/questão)
   dos enunciados e das descrições dos temas → top-20 candidatos com **recall medido** (> 98%) no
   conjunto rotulado.
3. *Classificador treinado* (regressão logística/LightGBM sobre embeddings + metadados) treinado
   com as decisões já revisadas pelo professor: barato, rápido e calibrável. Resolve os casos
   fáceis.
4. *LLM forte* só para o que o classificador não resolve com confiança (estimo 30–40%), com a
   árvore restrita aos candidatos e saída estruturada: ~US$ 0,003–0,01 por questão; dois LLMs
   de famílias diferentes nos casos de risco.
5. *Política calibrada* como neste repositório, com limiares recalibrados a cada semana.
6. *Revisão humana* priorizada por impacto: questões mais vistas por alunos e com maior incerteza
   primeiro; o professor confirma ou corrige com um clique (sugestão já preenchida).

**Custo estimado**: ~US$ 0,002–0,005 por questão em média (a maior parte cai nas camadas
baratas) → US$ 100–250 por semana para 50 mil questões, mais o tempo do professor na fila.

**Qualidade contínua**:
- *Amostra-ouro semanal*: 200 publicações sorteadas (estratificadas por tema e confiança)
  revisadas às cegas → precisão medida com IC; se o limite inferior cair abaixo de 95%, os
  limiares sobem automaticamente.
- *Calibração*: curva de confiabilidade por faixa; a coluna `confianca` precisa "valer" o que
  diz.
- *Reportes de alunos* viram rótulos (a página pública do produto não mostra um botão de
  "tema errado" por questão; criá-lo é a fonte mais barata de rótulos): questão reportada sai do ar (revisar) até decisão do
  professor; reportes por tema detectam novas "lixeiras".
- *Drift*: distribuição de temas por lote importado e taxa de "fora" por banca/ano.

**Fluxo**: importação → classificação (minutos) → publicadas entram no ar; revisar entra na fila
do professor com sugestão e motivo; fora vai para um backlog de "temas a criar". Toda decisão é
registrada (banco com hash de entrada, modelo, prompt e política), como no `db.py` deste case.

**O que faria com mais tempo**: pedir ao professor a auditoria cega das 100 publicadas (a
ferramenta está pronta) para transformar a previsão em medição; rodar os verificadores com um modelo de 30B+ (ou API) para elevar
a cobertura; pedir ao professor 100 questões rotuladas para medir (e não só prever) a precisão e
recalibrar os limiares; consolidar os clones da árvore antes de qualquer reclassificação em massa.

## d) Memo para o professor

Em `memo_professor.md` (1 página, linguagem não técnica).

## Decisões tomadas à mão (e por quê)

| Decisão | Onde | Por quê |
|---|---|---|
| Mapa dos 20 nós-clone → original | `config/nos_duplicados.json` | nunca publicar em nó vazio duplicado |
| 18 grupos de nós concorrentes em ramos diferentes | `config/grupos_ambiguos.json` | exigir evidência reforçada onde há duas respostas defensáveis |
| Limiares 0,75 / 0,90 (regras duras) e portão 0,95 | `config/politica.json` | portão escolhido pela curva cobertura × precisão estimada (seção de resultados); 0,75/0,90 são filtros conservadores fixados antes |
| Desconto de 4% (2–7%) por divergência de critério | `config/previsao.json` | risco que nenhum modelo enxerga |
| Anotação do classificador principal | `data/anotacoes/` | é saída de LLM, não correção humana; nenhuma linha editada depois |

**Modelos, custo e tempo**: Claude Opus 5.5 (assinatura do Claude Code; sem custo de API à
parte; ~20 min para 359 questões); qwen2.5:7b e llama3.1:8b via Ollama 0.40.6 numa máquina Apple
M2 Pro de 16 GB (custo marginal zero; ~35–40 min por modelo na 1ª passada, mais retentativas). PostgreSQL 16 e Docker para a trilha
de auditoria.
