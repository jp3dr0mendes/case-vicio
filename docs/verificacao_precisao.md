# Como checar a precisão real (≥ 95%) — e o que já foi revalidado

## 1. O que dá e o que não dá para afirmar hoje

A régua da Vício compara as publicadas com os **rótulos da equipe de especialistas**, que não
vêm no pacote do case. Portanto:

- **Não é possível comprovar ≥ 95% só com o que está neste repositório.** O `previsao.txt` é uma
  previsão (0,95; intervalo 0,85–0,98), não uma medição.
- É possível **medir** com rótulos humanos independentes e cegos. As ferramentas para isso estão
  prontas e testadas (`tests/test_verification.py`).

## 2. Caminhos para medir, do mais ao menos definitivo

| # | Caminho | Quem rotula | Mede o quê | Custo | Status |
|---|---|---|---|---|---|
| A | Gabarito da equipe da Vício | especialistas da Vício | **exatamente** a régua da avaliação | zero (o arquivo já existe do lado deles) | depende da Vício |
| B | Auditoria cega pelo professor | especialista | precisão "de especialista", inclui a escolha de nó | ~1,5–2 h para 130 questões | ferramenta pronta |
| C | Auditoria cega pelo candidato | não especialista com formação jurídica | proxy; não captura o critério da equipe | ~2 h | ferramenta pronta |
| D | Segundo LLM forte de outra família, cego | modelo | independência parcial; não mede critério | minutos | não executado (pede autorização para usar outro modelo/serviço) |
| E | Estimativa sem rótulos (feita) | — | teto estatístico + desconto declarado | feito | `docs/estimativa_precisao.md` |

### Como rodar A, B ou C

```bash
PYTHONPATH=src .venv/bin/python -m vicio_case.cli folha-auditoria
```

Gera `auditoria/folha_auditoria.html`: as 100 publicadas misturadas a 30 controles de revisão,
em ordem aleatória (semente 2026), **sem mostrar a decisão do sistema**. Quem audita abre o
arquivo no navegador (funciona offline), escolhe o tema de cada questão (busca por nome),
pode marcar `fora` ou `nao_sei`, e exporta `rotulos_auditoria.csv`. Depois:

```bash
PYTHONPATH=src .venv/bin/python -m vicio_case.cli medir-precisao --rotulos rotulos_auditoria.csv
```

Saída: precisão das publicadas pela régua oficial (mesmo nó, pai ou filho; irmão = erro),
intervalo exato de Clopper-Pearson, limite inferior unilateral de 95%, se a meta foi
comprovada/refutada, se a medição caiu dentro do intervalo previsto, a lista dos erros e a
acurácia das sugestões nos controles de revisão. Com o gabarito da Vício (formato `id,tema_id`),
o mesmo comando dá a precisão oficial.

**Regra de decisão** (calculada pelo próprio comando): auditando as 100 publicadas, **até 1
erro** ainda permite afirmar precisão ≥ 95% com 95% de confiança (limite inferior unilateral
0,953); com 2 erros o limite cai para ~0,938. Amostras de 30 nunca bastam para comprovar 95%.

Cuidados para a auditoria valer:
- Cega: o auditor não abre `publicacao.csv` nem `decision_audit.json` antes de exportar.
- Uma pessoa que não participou da classificação (por isso o candidato é só proxy — caminho C).
- Registrar a regra usada nos casos de nó duplicado (ex.: Maria da Penha em Penal ou em
  Legislação Especial): a folha mostra as cópias vazias marcadas "(cópia vazia)" justamente para
  medir esse cenário.

## 3. Quanto a própria medição da Vício oscila

Com ~100 publicadas, a precisão **medida** tem ruído de ±4 pontos. Probabilidade de a medição
dar ≥ 95% para cada precisão real (binomial, n = 100):

| precisão real | 0,93 | 0,95 | 0,96 | 0,97 | 0,98 |
|---|---|---|---|---|---|
| P(medida ≥ 95%) | 0,29 | 0,62 | 0,79 | 0,92 | 0,98 |

Leitura: com a previsão pontual de 0,95, a chance de passar na régua é ~60%. Para passar com
folga (~90%), a precisão real precisaria ser ~0,97. Publicar menos não resolve sozinho, porque
o ruído é quase o mesmo para n = 60–100.

## 4. Sensibilidade das 100 publicadas

| Subconjunto | n | Posterior média (modelo) | × (1 − 4% critério) |
|---|---|---|---|
| todas | 100 | 0,985 | 0,95 |
| dois verificadores concordam | 58 | 0,997 | 0,96 |
| um verificador concorda | 42 | 0,968 | 0,93 |
| nó de nível 1 (tema) | 58 | 0,988 | 0,95 |
| nó de nível 2 (subtema) | 42 | 0,980 | 0,94 |
| original com cópia vazia em Penal | 23 | 0,990 | 0,95 (ou **0** se o gabarito usar as cópias) |

**Alternativa conservadora** (não adotada): publicar só as 58 com dois verificadores concordando
→ cobertura 16%, previsão ~0,96. Não adotei porque o risco dominante é a divergência de critério
do especialista, que nenhum filtro baseado em modelos reduz; o ganho previsto (+1 ponto) não
compensa perder 42% da cobertura. Se a Vício preferir margem, é uma linha em
`config/politica.json` (`limiar_posterior_publicacao: 0.99` dá ~65 publicadas).

## 5. Revalidação contra o enunciado e o momento da empresa

**Contexto da empresa (pesquisa em 18/10/2026).** A Vício de uma Estudante nasceu em 2019 com o
Método VDE para a OAB e hoje vende também o *VDE Carreiras Jurídicas* (Magistratura, MP,
Defensoria, Procuradorias, Delegado), anunciando "+50 mil questões comentadas" organizadas "por
banca, tema e nível" e um assistente de IA (vic.IA). O case é exatamente o gargalo dessa
expansão: importação em massa de questões de outras fontes (os `assunto_origem` vêm de sites de
origem), classificação automática que criou "lixeiras" e uma árvore em reestruturação (os 20 nós
"(Parte 1/2)" e as cópias de leis especiais dentro de Penal, vazias e sem descrição). O aluno
paga R$ 2,5–4,3 mil/ano e estuda "por tema e incidência": tema errado é custo direto de
confiança — o que confirma a escolha de priorizar precisão e mandar a dúvida para revisão com
sugestão. A página pública não mostra um canal de reporte de erro por questão; o relatório
recomenda criá-lo, porque reportes são a fonte mais barata de rótulos.

| Exigência do enunciado | Onde | Status |
|---|---|---|
| `publicacao.csv` com as 359 questões no formato do LEIA-ME | raiz; `tests/test_entrega.py` | ✅ validado automaticamente |
| `confianca` = chance de o tema central estar certo | posterior × risco de critério; média nas publicadas 0,945 ≈ previsão | ✅ coerente com a previsão |
| `motivo` curto, obrigatório em revisar/fora | máx. 154 caracteres, linguagem do professor | ✅ |
| `previsao.txt` com 4 linhas + explicação | raiz | ✅ previsão declarada como previsão |
| Relatório ≤ 5 páginas com a) b) c) d) | `relatorio_case.md`: 3 páginas A4 + memo 1 página = 4 (medido renderizando em PDF A4, fonte 11) | ✅ |
| Memo de 1 página, não técnico | `memo_professor.md` (1 página A4 medida) | ✅ |
| Código: pipeline, prompts, chamadas, regras, estimativa | `src/`, `prompts/`, `config/` | ✅ |
| README: como rodar, que passos geram o CSV, decisões manuais, modelos, custo, tempo | `README.md`, relatório | ✅ |
| Repositório público no GitHub | jp3dr0mendes/case-vicio | ✅ público |
| Precisão ≥ 95% nas questões guardadas | — | ⚠️ **prevista**, não comprovada (caminhos A–C acima) |
| Envio do link por e-mail até 18/10 | — | ⏳ ação do candidato |
