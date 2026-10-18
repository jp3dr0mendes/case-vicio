# Relatório: case de classificação de tópicos

João Pedro Mendes Albuquerque · 18/10/2026 · https://github.com/jp3dr0mendes/case-vicio

Das 359 questões, 100 (28%) foram publicadas, 258 foram para revisão com tema sugerido e motivo,
e 1 ficou como "fora" (é de Direito Tributário). A precisão prevista para as publicadas é 0,95,
com intervalo de 0,85 a 0,98. É uma previsão, porque o pacote não traz gabarito; na seção b
explico como medir.

## a) Como pensei

Um LLM classifica a maior parte dessas questões corretamente, mas não avisa em quais erra. Por isso
o trabalho girou em torno de saber quando confiar: um classificador forte, sinais independentes
para estimar quando ele erra e uma política que só publica onde essa estimativa sustenta 95%. O
resto vai para o professor, já com uma sugestão.

Parti de três hipóteses, todas confirmadas: os metadados de origem são ruidosos (das 43 questões
marcadas como "Concurso de Crimes", só 2 tratam do assunto); o erro mais caro está no nó da árvore,
mais do que na matéria, porque há temas vazios duplicados e assuntos repetidos em ramos diferentes
e a régua conta o "irmão" como erro; e, sem gabarito, prever a precisão exige comparar
classificadores que erram de jeitos diferentes.

Várias tentativas ficaram pelo caminho (registradas em `prompts/classificacao.md` e
`artifacts/experimentos/`). Similaridade de TF-IDF não é probabilidade de acerto, e restringir o
LLM aos 12 candidatos do TF-IDF não serviu, porque o tema escolhido pelo classificador principal só
estava nessa lista em 78% das questões. Respondendo por `tema_id`, o qwen2.5:7b trocava dígitos (a
Lei Antiterrorismo, 4706, virava Estatuto do Idoso, 4696); com a decodificação restrita às 371
opções, preferia as primeiras em ordem alfabética; e, quando eu pedia uma "escolha", respondia a
própria questão ("B: I e III"). O qwen2.5:14b não coube na memória da máquina. Também descartei um
verificador que lê a proposta do principal, porque ele tende a concordar, e publicar só com confiança
alta, sem concordância de ninguém, porque esses casos ficaram com 0,3 a 0,7 de acerto estimado.

O pipeline que ficou:

1. Classificador principal: o Claude Opus 5.5, via Claude Code, classificou as 359 questões com a
   árvore completa e as mesmas regras do prompt local, antes de ver os verificadores. A saída está
   versionada e não foi editada (protocolo em `prompts/anotador_forte.md`).
2. Verificadores: qwen2.5:7b e llama3.1:8b, via Ollama, em dois passos (primeiro o tema, depois o
   subtema). Resposta ambígua é descartada, nunca adivinhada.
3. Política (`decisions.py`, com testes): nunca publica em tema vazio duplicado, exige mais
   evidência em assunto que existe em outro ramo, manda para revisão quando os verificadores vetam,
   quando a confiança do principal fica abaixo de 0,75 ou quando algo falha, e só publica com
   probabilidade estimada de acerto de pelo menos 0,95. "Fora" exige consenso.
4. Estimativa (`docs/estimativa_precisao.md`): a acurácia de cada classificador sai da concordância
   entre pares (com três anotadores, concordância ≈ p_i·p_j); com ela e a taxa `r` de erro
   coincidente, medida nos dados, sai a probabilidade de acerto de cada questão, com um desconto
   para divergência de critério. A coluna `confianca` traz essa probabilidade, e a média dela nas
   publicadas é a precisão prevista.

| Decisão | Questões | Detalhe |
|---|---|---|
| publicar | 100 | 73 concordância exata com um verificador, 27 concordância pai/filho |
| revisar | 258 | 123 confiança baixa, 42 assunto em outro ramo, 32 probabilidade abaixo de 0,95, 28 divergência, 26 veto, 5 sem verificação, 2 talvez "fora" |
| fora | 1 | Q0142 (ITCD, Direito Tributário) |

A concordância com os verificadores aumenta com a confiança declarada pelo classificador principal
(os dois concordam em 10% das questões abaixo de 0,35 e em 32% a partir de 0,90), mas o modelo
atribui parte disso aos verificadores, já que questão difícil é difícil para todos. A acurácia
estimada do principal fica perto de 0,78, a do qwen perto de 0,50 e a do llama perto de 0,69, com
`r` = 0,25. Ou seja, confiar só na confiança declarada pelo LLM daria
algo perto de 0,8 de precisão; o que separa as questões seguras é a concordância independente.
Com o limiar de 0,95 ficam 100 publicadas, com probabilidade média de 0,985 (sem o limiar seriam
132, com 0,884).

A previsão (`previsao.txt`) é 0,985 × (1 − 0,04) = 0,95. Os 4% (faixa de 2% a 7%) cobrem o risco de
o especialista ter escolhido outro nó defensável, algo que nenhum dos modelos enxerga. O intervalo
de 0,85 a 0,98 vem do bootstrap das acurácias, de variar `r` e da faixa do desconto. As 100
publicadas foram relidas uma a uma pelo classificador principal: nenhum erro de assunto apareceu, e
em cerca de 5 delas outro nó também seria defensável; por ser o mesmo modelo, isso serve para achar
deslizes, não para medir. Um risco ficou fora do intervalo e está declarado à parte: 23 publicadas
estão em temas de Legislação Especial que têm uma cópia vazia dentro de Penal, e, se o gabarito usar
as cópias, a precisão cai para cerca de 0,73.

## b) Diagnóstico

O que mais atrapalha (detalhes em `docs/diagnostico_dados.md`):

1. A árvore se contradiz. Há 20 temas ativos, sem descrição nem subtemas, que duplicam temas com
   conteúdo: "Teoria da Pena (Parte 2)", "Competência (Parte 1)" e leis especiais copiadas em Penal.
2. O mesmo instituto aparece em dois ramos, como ação penal (Penal e Processo Penal), Juizado
   Especial e regime de pena. São duas respostas defensáveis, e a régua aceita só uma.
3. Temas inativos deixam questões órfãs: sem "Direito penal econômico", cartel, ordem tributária e
   sistema financeiro ficam sem lugar natural.
4. Cerca de 20 questões juntam assertivas de capítulos diferentes e não têm tema central. Com as do
   item 2 e as de criminologia crítica, de nomes de tema parecidos, são as mais difíceis.
5. Há texto com defeito: comandos que não combinam com a questão ("Explique…" em itens de Certo ou
   Errado), enunciado que cita uma situação ausente (Q0219) e OCR corrompido (Q0078).
6. Os metadados de origem (as "lixeiras") ajudam a indicar a disciplina, mas não o tema.

Para medir a precisão de verdade (`docs/verificacao_precisao.md`), `folha-auditoria` gera uma página
HTML, que funciona sem internet, com as 100 publicadas misturadas a 30 questões de revisão e sem
mostrar a decisão do sistema; `medir-precisao` compara as respostas com a régua oficial, com
intervalo exato de Clopper-Pearson, e aceita também o gabarito da Vício. Se houver no máximo um erro
nas 100, fica comprovado que a precisão passa de 95%. Com cerca de 100 publicadas a própria medição
oscila uns 4 pontos: com 95% reais, ela só mostra 95% ou mais em 62% das vezes.

## c) Produção, com 50 mil questões por semana

A Vício está levando o Método VDE da OAB para as carreiras jurídicas, com mais de 50 mil questões.
O problema do case vem dessa expansão: importação em massa, "lixeiras" e uma árvore em
reestruturação. Como o aluno estuda por tema, errar o tema afeta direto a confiança na plataforma.

Eu montaria camadas, de forma que o custo cresça só onde há dúvida:

1. Deduplicação (hash e embeddings), para que questões repetidas herdem a classificação revisada.
2. Embeddings para chegar a 20 candidatos, com meta de recall acima de 98% (o TF-IDF daqui chega a
   81%), a cerca de US$ 0,00002 por questão.
3. Um classificador treinado com as decisões já revisadas pelo professor (regressão logística ou
   LightGBM sobre os embeddings), barato e fácil de calibrar, para os casos fáceis.
4. Um LLM forte só no restante (30% a 40%), de US$ 0,003 a US$ 0,01 por questão, com dois LLMs de
   famílias diferentes nos casos de risco, e a política calibrada como a deste repositório.
5. Revisão humana priorizada pelas questões mais vistas e mais incertas, com sugestão pronta.

Agentes ficariam fora da classificação, por serem caros e difíceis de auditar, e ajudariam na
curadoria da árvore, com aprovação humana. O custo médio ficaria entre US$ 0,002 e US$ 0,005 por
questão, de US$ 100 a US$ 250 por semana, além do tempo do professor.

No fluxo, cada lote importado é classificado em minutos: as publicadas entram no ar, as dúvidas vão
para a fila do professor com sugestão e as "fora" para uma lista de temas a criar, com cada decisão
registrada como no `db.py`. A qualidade é acompanhada por uma amostra semanal de 200 publicadas
revisada às cegas (se o limite inferior do intervalo cair abaixo de 95%, os limiares sobem) e por um
botão de "tema errado" em cada questão, que tira a questão do ar e vira rótulo. Com mais tempo, eu
pediria a conferência das 100 publicadas ao professor e testaria verificadores maiores.

## d) Memo para o professor

Está em `memo_professor.md` (uma página).

## Uso de IA, decisões manuais e custo

Além de usar o Claude Opus 5.5 como um dos classificadores, usei o Claude Code como assistente para
implementar o código, os testes e a infraestrutura e para redigir a documentação, seguindo as minhas
orientações. As decisões e os resultados são de minha responsabilidade e podem ser conferidos no
repositório. As decisões tomadas à mão, os modelos, o custo (nada além da assinatura do Claude Code)
e o tempo (cerca de 2,5 horas) estão no README.
