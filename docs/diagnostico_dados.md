# Diagnóstico dos dados e da árvore de temas

Números conferidos na cópia real dos anexos (`artifacts/data_audit.json`, gerado por
`python -m vicio_case.cli audit`). Os anexos em `data/input/` são idênticos byte a byte aos do
ZIP oficial (`anexos-case-ia.zip`, sha1 `d627c8f8…`).

## Contagens

| Item | Valor |
|---|---|
| Questões | 359 (IDs Q0001–Q0359, únicos) |
| Nós na árvore | 377 (4 raízes/disciplinas) |
| Ativos | 375 · inativos: **5078** "Direito penal econômico" e **5234** "Tratados e convenções" |
| Temas selecionáveis (ativos, não-raiz) | 371 |
| Nós sem descrição | 20 — exatamente os 20 "clones" abaixo |
| Questões sem `comando` | 94 |
| Questões sem `assunto_origem` | 18 · sem `disciplina_origem`: 1 |
| Questões Certo/Errado (2 alternativas) | 58 · 4 alternativas: 46 · 5: 255 |

Todos os números do diagnóstico anterior foram confirmados; nenhuma divergência.

## O que atrapalha uma máquina (ou um humano)

### 1. Nós-clone vazios (20) — decisão manual em `config/nos_duplicados.json`
IDs 6716–6738: nós de nível 1, ativos, **sem descrição e sem subtemas**, que duplicam um nó
original com conteúdo:
- "(Parte 1)", "(Parte 2)": Teoria da Pena (6726/6727 → 5199), Competência (6732/6733 → 5480),
  Sentença Penal (6737/6738 → 5572), Crimes contra o Patrimônio (6720/6721 → 5157),
  Administração Pública (6718/6719 → 5087), "Provas em Espécie" (6735 → 5543),
  "Recursos (Parte 03)" (6736 → 5560);
- cópias em *Penal* de leis especiais: Abuso de Autoridade, Meio Ambiente, Idoso, Lavagem,
  Maria da Penha, Organizações Criminosas, Tráfico (e LEP copiada em Processo Penal).

Como a régua pune "irmão" como erro, publicar no clone quando o especialista escolheu o original
(ou vice-versa) é erro. **A política nunca publica em clone**; se o classificador escolhe um, a
questão vai para revisão com o nó original sugerido.

### 2. Mesmo assunto em ramos diferentes — `config/grupos_ambiguos.json`
Exemplos: "Ação Penal" existe em Penal (5063) e Processo Penal (5466) e conversa com
Punibilidade (decadência, perempção, renúncia); Juizado Especial Criminal (4701) × Procedimento
Sumaríssimo (5539); Interceptação Telefônica (4700) × (5555); regime de pena em Penal (5201) ×
fixação do regime na Sentença (5576); efeitos da condenação (5209 × 5577); finalidade da pena em
Criminologia (4384) × Penal (5200); LEP (4703) × livramento/indulto/medida de segurança. Uma
questão desses assuntos tem duas respostas defensáveis e a régua só aceita uma. Publicar nesses
ramos exige confiança ≥ 0,90 **e** concordância de todos os verificadores.

### 3. Temas inativos deixam assuntos sem casa
Com "Direito penal econômico" inativo, questões sobre cartel, ordem tributária/econômica e
sistema financeiro (ex.: Q0039, Q0181, Q0297, Q0298) caem em temas vizinhos imperfeitos
(Crimes Tributários, Economia Popular, CDC). Vão para revisão.

### 4. "Lixeiras" visíveis nos metadados de origem
O `assunto_origem` concorda pouco com o conteúdo (comparação com a classificação do
classificador principal):

| assunto_origem | questões | no mesmo ramo do tema atribuído |
|---|---|---|
| Concurso de Crimes | 43 | **2** |
| Ação Penal (Parte 02) | 17 | **0** |
| Ação Penal (Parte 01) | 19 | 4 |
| Comunicação dos atos processuais | 13 | 1 |
| Lesão Corporal | 9 | 0 |
| Teoria da Pena (Parte 02) | 18 | 8 (o resto é LEP, execução) |

As descrições dos nós antigos mostram o mesmo padrão ("Teoria da Pena: 453 questões no source",
"Administração Pública: 368", "Patrimônio: 325"). A disciplina de origem é melhor (302 de 349
comparáveis caem na mesma disciplina), mas 7 questões vêm de fora do recorte (Constitucional,
Civil, Tributário, Ambiental, "Disciplina Unificada").

### 5. Defeitos de texto
- **Comandos gerados/inconsistentes**: 11 questões Certo/Errado com comando "Explique…"
  (ex.: Q0008, Q0028, Q0088) — o comando não corresponde às alternativas.
- Enunciado que cita contexto ausente: Q0219 ("na situação descrita", sem situação), Q0329
  ("situação hipotética 1A12-I").
- Texto corrompido por OCR: Q0078 ("EM oossstomnioconcunsos come…").
- Erros de digitação nos títulos: "Comeptência Territorial", "Estaturo de Idoso",
  "Escolas Crimonológicas", "Caractéristas", "Dos Crimescontra", prefixos numéricos
  ("12 Disposições Gerais…", "2 Oferecimento…").

### 6. Questões "colcha de retalhos"
~20 questões têm 4–5 assertivas de capítulos diferentes (ex.: Q0020, Q0068, Q0126, Q0288,
Q0333). Não existe "o" tema central; publicar qualquer um é aposta. Recebem confiança baixa e
vão para revisão — e são o principal pedido ao professor: aceitar tema geral ou criar regra.

## Tratamento no pipeline
- HTML removido com BeautifulSoup preservando o texto; `\n` literais das alternativas mantidos
  como espaço.
- Campos de origem ausentes são tratados como string vazia; nenhuma questão é descartada.
- Validações automáticas (`data.py`, `tests/`): esquema, unicidade, pais existentes, ciclos,
  inativos/raízes/clones nunca publicados, contrato do CSV.
