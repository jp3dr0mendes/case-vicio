# Diagnóstico dos dados fornecidos

Auditoria dos arquivos `questoes.jsonl` e `temas.csv` do ZIP original.

## Contagens verificadas

| Item | Resultado |
|---|---:|
| Questões | 359 |
| IDs duplicados de questão | 0 |
| Nós da taxonomia | 377 |
| Nós ativos | 375 |
| Nós inativos | 2 |
| Nós raiz (nível 0) | 4 |
| Temas/subtemas ativos selecionáveis pelo pipeline | 371 |
| Questões sem `comando` | 94 (26,2%) |
| Questões sem `assunto_origem` | 18 (5,0%) |
| Questões sem `disciplina_origem` preenchida | 1 |

Temas inativos identificados: `5078` (“Direito penal econômico”) e `5234` (“Tratados e convenções em matéria criminal”). O pipeline os exclui dos candidatos, mesmo que apareçam por semelhança lexical.

## Disciplinas de origem

| Disciplina de origem | Questões |
|---|---:|
| Processo Penal | 131 |
| Direito Penal | 129 |
| Direito Penal - Legislação Especial | 32 |
| Criminologia | 31 |
| Penal | 27 |
| Outras disciplinas, vazio ou variantes | 9 |

A origem não é uma classificação confiável; há variantes (`Direito Processual Penal`) e registros fora das quatro áreas-alvo, como Constitucional, Civil - Legislação Especial, Tributário e Ambiental. Essas linhas precisam de interpretação do conteúdo, não devem ser descartadas automaticamente só pelo campo de origem.

## Problemas semânticos da árvore

- Há nomes muito próximos ou redundantes, como `Provas em Espécie`/`Provas em Espécies`, `Recursos em Espécies` e temas de sentença/competência partidos por “Parte 1/2”.
- Alguns rótulos/títulos têm ruído de grafia, por exemplo `Estaturo de Idoso - Crimes` e `Escolas Crimonológicas`.
- Descrições incluem contagens históricas (“X questões no source”), que ajudam pouco a distinguir conceitos e podem contaminar busca textual.
- A árvore combina temas substantivos de Direito Penal, temas processuais e legislação especial; termos como Lei de Execução Penal aparecem em ramos diferentes. O contexto do enunciado precisa resolver ambiguidades.
- HTML cru contém quebras de linha e tags simples (`br`, `i`, `b`, `u`, `span`, `sup`). Limpar visualmente o HTML antes da inferência reduz ruído sem eliminar palavras.

## Questões difíceis

1. Enunciados com diversas assertivas podem cobrir mais de um instituto; `extras_ids` deve ser conservador.
2. Questões sobre leis especiais podem aparecer com metadado da disciplina `Direito Penal`, `Direito Penal - Legislação Especial` ou disciplina externa.
3. Assuntos de origem vazios ou errados não podem controlar a classificação.
4. Rótulos genéricos/introdutórios competem com subtemas específicos; o modelo deve escolher o tópico central mais específico realmente sustentado, mas não descer para um subtema irmão só por uma palavra parecida.
5. O pacote não inclui rótulos de referência nem gabarito da classificação. A precisão não pode ser calculada a partir apenas dos próprios outputs.

## Tratamentos implementados

- Checagem de cardinalidade, IDs únicos, campos obrigatórios e integridade da taxonomia.
- Limpeza de HTML e concatenação de enunciado, comando e alternativas.
- Metadados de origem com peso fraco e apenas como contexto.
- Exclusão de tema inativo da seleção.
- Validador de relação pai/filho e teste explícito de que temas irmãos não equivalem.
- Falha fechada para revisão em erros de modelo e respostas malformadas.
