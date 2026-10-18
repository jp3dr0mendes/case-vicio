# Como a precisão foi estimada sem gabarito

O pacote do case **não traz rótulos**. Tudo o que segue é previsão; a precisão real só será
conhecida quando a Vício comparar o `publicacao.csv` com os rótulos dos especialistas.

## 1. Três votos independentes

| Classificador | Papel | Como roda |
|---|---|---|
| Claude Opus 5.5 | principal | sessão do Claude Code; protocolo em `prompts/anotador_forte.md` |
| qwen2.5:7b | verificador | Ollama local, hierárquico tema→subtema (`prompts/classificacao.md`) |
| llama3.1:8b | verificador | idem, outra família de modelo |

"Concordar" = mesmo ramo pela régua oficial (mesmo nó, pai ou filho). Irmãos discordam.

## 2. Acurácias latentes (modelo de três anotadores)

Se os erros são independentes dado o acerto e dois erros raramente caem no mesmo ramo,
a taxa de concordância entre i e j é `a_ij ≈ p_i · p_j`. Com três classificadores:

```
p_i = sqrt(a_ij · a_ik / a_jk)
```

Calculado globalmente e **por faixa de confiança declarada pelo principal** (alta ≥ 0,90,
média 0,75–0,90, baixa < 0,75), com IC de 90% por bootstrap (`estimation.py`). O teste
`tests/test_estimation_llm.py` verifica que o estimador recupera acurácias conhecidas em dados
sintéticos (erro < 0,05 com 3.000 itens).

## 3. Erro coincidente (r)

Dois classificadores errados podem cair no mesmo ramo (armadilhas da árvore são as mesmas para
todos). `r` = P(dois erros no mesmo ramo) é estimado como a taxa de concordância entre os dois
verificadores nas questões em que ambos discordam do principal (proxy pessimista, porque parte
dessas concordâncias são acertos dos verificadores), limitado a [0,05; 0,5].

## 4. Posterior por questão (portão de publicação e coluna `confianca`)

```
P(certo | padrão) ∝ p_F · Π_i [ p_i se concordou ; (1 − p_i) se discordou ]
P(errado | padrão) ∝ (1 − p_F) · Π_i [ (1 − p_i)·r se concordou ; 1 − (1 − p_i)·r se discordou ]
```

com `p_F` e `p_i` da faixa de confiança da questão. Voto inválido não entra. A confiança
declarada pelo LLM **só escolhe a faixa**; nunca é usada como probabilidade.

- **Portão de publicação**: publica só se essa posterior for ≥ 0,95 (`config/politica.json`).
- **Coluna `confianca` do CSV** = posterior × (1 − 4% de divergência de critério), e × 0,5 nos
  ramos com nó equivalente em outro lugar da árvore (o especialista pode ter escolhido o outro nó).
  Com isso, a média da coluna nas publicadas (0,945) é a própria precisão prevista (0,95). A
  posterior sem desconto fica registrada em `decision_audit.json` (`trace.posterior_modelo`).

## 5. Precisão prevista

- Teto do modelo: média das posteriores nas publicadas.
- Intervalo do modelo: acurácias nos limites do IC90% e `r` entre metade e o dobro.
- **Desconto por divergência de critério** (`config/previsao.json`): o especialista pode ter
  escolhido outro nó defensável (clones, assuntos repetidos em ramos diferentes, questões
  "colcha de retalhos"). Esse risco é invisível para os três modelos, porque nenhum vê o critério
  da equipe. Valor declarado: 4% (faixa 2%–7%), justificado no relatório.

## 6. Limitações conhecidas

- Independência condicional é otimista para LLMs (erros correlacionados) → mitigado por `r`
  medido e pelo desconto.
- Os verificadores são fracos (7–8B); por isso a estimativa por faixa tem amostras pequenas e
  intervalos largos.
- O classificador principal é um LLM: seus votos não são gabarito e não são tratados como tal.
- A primeira avaliação com rótulos reais deve recalibrar `p_F` por faixa e substituir o desconto
  declarado por um valor medido.
