# Relatório — Case de classificação de tópicos (Vício · Método VDE)

João Pedro Mendes Albuquerque · 18/10/2026 · https://github.com/jp3dr0mendes/case-vicio

**Resultado:** publiquei **100 das 359 questões (28%)**, com precisão **prevista** de **0,95**
(intervalo 0,85–0,98); 258 vão para revisão com sugestão e motivo; 1 é "fora" (Direito
Tributário). A precisão não foi medida: o pacote não tem gabarito (como medir: seção b).

## a) Como pensei

**A pergunta certa não é "qual tema?", é "quando posso confiar no tema?"** Um LLM acerta a maioria
das questões, mas não sabemos *quais*. Desenhei o sistema em torno de: (1) um classificador forte;
(2) sinais **independentes** para estimar quando ele erra; (3) uma política que só publica onde a
evidência sustenta ≥ 95% e manda o resto ao professor **com a sugestão**.

**Hipóteses** (todas confirmadas): (1) metadados de origem são ruidosos — das 43 questões
marcadas "Concurso de Crimes", só 2 tratam disso; (2) o erro mais caro é **qual nó**, não o assunto
— 20 nós-clone vazios e assuntos repetidos em ramos diferentes, e a régua pune o "irmão"; (3) sem
gabarito, prever precisão exige **classificadores que erram de forma diferente**.

**Becos sem saída** (registrados em `prompts/classificacao.md` e `artifacts/experimentos/`):
TF-IDF da implementação anterior (similaridade não é probabilidade); LLM restrito ao top-12 lexical
(o tema do principal só estava na lista em 78% das questões); qwen2.5:7b respondendo `tema_id` (**trocava dígitos**: 4706 → 4696);
decodificação restrita às 371 opções (viés alfabético); pedir "escolha" (o modelo **respondia a
questão**: "B: I e III"); qwen2.5:14b (não coube em 16 GB); verificador que vê a proposta
(deferência); publicar por confiança alta sem concordância (só ~0,3–0,7 de acerto estimado).

**Pipeline final**
1. *Classificador principal*: Claude Opus 5.5, rodando na sessão do Claude Code, anotou as 359
   questões com a árvore completa e o mesmo regulamento do prompt local, antes de ver os
   verificadores. Saída versionada, sem edição manual (`prompts/anotador_forte.md`).
2. *Verificadores*: qwen2.5:7b e llama3.1:8b (Ollama), em dois passos (tema → subtema), com
   casamento estrito da resposta: ambígua vira inválida, nunca palpite.
3. *Política* (`decisions.py`, testada): nunca em nó-clone; ramo com nó equivalente em outro lugar
   da árvore exige confiança ≥ 0,90 e concordância de todos; veto quando os dois verificadores
   concordam entre si contra o principal; confiança < 0,75 ou falha → revisar; e o **portão**:
   publica só se a probabilidade estimada de acerto da questão for ≥ 0,95. "Fora" só com consenso.
4. *Estimativa* (`docs/estimativa_precisao.md`): acurácias latentes com três anotadores
   (concordância_ij ≈ p_i·p_j), por faixa de confiança; erro coincidente `r` medido; posterior por
   questão; desconto declarado por divergência de critério. A coluna `confianca` é a posterior
   descontada: sua média nas publicadas é a precisão prevista.

**Resultados**

| Decisão | Questões | Detalhe |
|---|---|---|
| publicar | 100 | 73 com concordância exata de um verificador; 27 pai/filho |
| revisar | 258 | 123 principal inseguro; 42 nó equivalente em outro ramo; 32 probabilidade < 0,95; 28 divergência; 26 veto; 5 sem verificação válida; 2 possível "fora" |
| fora | 1 | Q0142 (ITCD, Direito Tributário) |

**Calibração.** A concordância com os verificadores cresce com a confiança declarada pelo
principal (dois concordando: 10% das questões com confiança ≤ 0,35, 32% das ≥ 0,90), mas o modelo
atribui parte disso aos verificadores (questão difícil é difícil para todos): acurácia estimada do
principal ~0,78 (0,74–0,83 por faixa), qwen ~0,50, llama ~0,69, `r` = 0,25. Publicar "porque o LLM
disse 0,95" daria ~0,8; o que separa as seguras é a **concordância independente**. Portão 0,95 →
100 publicadas, posterior média 0,985 (sem portão: 132 com 0,884; portão 0,98: 65 com 0,997).

**Previsão** (`previsao.txt`): 0,985 × (1 − 4% de divergência de critério) = **0,95**; intervalo
0,85–0,98 (bootstrap das acurácias, `r` de metade ao dobro, desconto de 2–7%); cobertura 0,28. Reli
as 100 publicadas: nenhum erro de assunto, ~5 com nó alternativo defensável. **Risco declarado
fora do intervalo**: 23 publicadas estão em nós de Legislação Especial que têm cópia vazia em Penal;
se o gabarito usar as cópias, a precisão cai para ~0,73. Verificadores: 295 (qwen) e 335 (llama)
votos válidos de 359; os inválidos contam como "sem voto".

## b) Diagnóstico (detalhes em `docs/diagnostico_dados.md`)

1. **A árvore se contradiz**: 20 nós ativos, sem descrição nem subtemas, duplicam nós com conteúdo
   ("Teoria da Pena (Parte 2)", "Competência (Parte 1)", leis especiais copiadas em Penal).
2. **O mesmo instituto mora em dois ramos**: ação penal (Penal × Processo Penal × Punibilidade),
   Juizado Especial (Legislação Especial × Sumaríssimo), regime de pena (Penal × Sentença),
   execução (LEP × livramento × indulto). Duas respostas defensáveis; a régua aceita uma.
3. **Temas inativos deixam órfãos**: sem "Direito penal econômico", cartel, ordem tributária e
   sistema financeiro não têm casa natural.
4. **Questões "colcha de retalhos"** (~20): assertivas de capítulos diferentes; não existe tema
   central. É a classe mais difícil, para humano e máquina, junto com o item 2 e a criminologia
   crítica (labeling × criminalização × teorias da pena), onde os nomes dos temas se sobrepõem.
5. **Texto defeituoso**: comandos gerados que não batem com a questão ("Explique…" em itens
   Certo/Errado), enunciado que cita situação ausente (Q0219), OCR corrompido (Q0078).
6. **Metadados de origem enganam** (as "lixeiras"): pista fraca de disciplina, nunca de tema.

**Como checar a precisão real** (`docs/verificacao_precisao.md`): `folha-auditoria` gera uma folha
HTML offline com as 100 publicadas + 30 controles, **sem mostrar a decisão do sistema**;
`medir-precisao` aplica a régua oficial com intervalo exato de Clopper-Pearson e aceita também o
gabarito da Vício. Auditando as 100, até 1 erro ainda comprova ≥ 95%. Atenção: com ~100 publicadas
a própria medição oscila ±4 pontos; com 95% reais, ela só dá ≥ 95% em ~62% das vezes (97% → ~92%).

## c) Produção — 50 mil questões por semana

**Momento da empresa.** A Vício leva o Método VDE da OAB ao *VDE Carreiras Jurídicas*
(Magistratura, MP, Defensoria, Procuradorias, Delegado), com "+50 mil questões" e a vic.IA. O case é
o gargalo dessa expansão: importação em massa, "lixeiras" e árvore em reestruturação. Quem paga
R$ 2,5–4,3 mil/ano estuda por tema; errar o tema custa confiança.

**Camadas (o custo cresce só onde há dúvida)**: (1) normalização e deduplicação (hash + embeddings;
repetidas herdam a classificação revisada); (2) embeddings de enunciados e descrições → top-20
candidatos, com meta de recall > 98% medida no conjunto rotulado (o TF-IDF daqui chega a 81%; ~US$
0,00002/questão); (3) classificador treinado
(logística/LightGBM sobre embeddings) com as decisões revisadas pelo professor — barato e calibrável,
resolve os fáceis; (4) LLM forte só no restante (~30–40%), com a árvore restrita aos candidatos (~US$
0,003–0,01/questão), e dois LLMs de famílias diferentes nos casos de risco; (5) política calibrada
como a deste repositório; (6) revisão humana priorizada por impacto (questões mais vistas e mais
incertas primeiro; sugestão pré-preenchida, um clique). **Agentes** ficam fora do caminho crítico
(caros e difíceis de auditar por questão); entram na curadoria da árvore — propor fusão de clones,
detectar novas "lixeiras" pelos reportes —, sempre com aprovação humana. **Custo**: ~US$ 0,002–0,005/questão →
US$ 100–250 por semana, mais o tempo do professor.

**Qualidade contínua**: amostra-ouro semanal de 200 publicadas revisada às cegas (limite inferior
do IC < 95% → limiares sobem); curva de confiabilidade da `confianca`; botão "tema errado" por
questão (não existe na página pública) que tira a questão do ar e vira rótulo; drift de temas por
lote importado e de "fora" por banca/ano.

**Fluxo**: importação → classificação em minutos → publicadas no ar; revisar vai à fila do professor;
fora, a um backlog de "temas a criar"; toda decisão é registrada (hash de entrada, modelo, prompt,
política), como no `db.py` deste case.

**Com mais tempo**: auditoria cega das 100 publicadas pelo professor; verificadores de 30B+ ou via
API (mais cobertura com a mesma precisão); consolidar os clones antes de reclassificar em massa.

## d) Memo para o professor: `memo_professor.md` (1 página)

## Decisões tomadas à mão, modelos, custo e tempo

| Decisão | Onde | Por quê |
|---|---|---|
| Mapa dos 20 nós-clone → original | `config/nos_duplicados.json` | nunca publicar em nó vazio duplicado |
| 18 grupos de nós equivalentes em ramos diferentes | `config/grupos_ambiguos.json` | evidência reforçada onde há duas respostas defensáveis |
| Limiares 0,75 / 0,90; portão 0,95 | `config/politica.json` | portão pela curva cobertura × precisão |
| Desconto de critério 4% (2–7%) | `config/previsao.json` | risco que nenhum modelo enxerga |
| Anotação do principal | `data/anotacoes/` | saída de LLM, sem edição posterior |

**Modelos, custo e tempo**: Claude Opus 5.5 (assinatura do Claude Code; ~20 min); qwen2.5:7b e
llama3.1:8b via Ollama num M2 Pro de 16 GB (custo marginal zero; ~35–40 min cada, mais retentativas).
