# Protocolo do classificador principal (Claude Opus 5.5 via Claude Code)

Saída: `data/anotacoes/claude_opus_5_5.psv` (uma linha por questão, separador `|`):
`id|tema_central_id|extras_ids|confianca|fora|justificativa`.

## Como foi executado

- Modelo: Claude Opus 5.5 (`claude-opus-5-5`), dentro de uma sessão do Claude Code em 18/10/2026.
- Entrada: as 359 questões com HTML limpo (enunciado + comando + alternativas), em 12 lotes de
  30, mais a disciplina/assunto de origem marcados como pista fraca; e a lista completa dos 371
  temas selecionáveis no formato `tema_id | caminho`.
- Independência (premissa da estimativa de precisão): antes de anotar, o modelo só viu as respostas
  de um teste rápido do qwen (versão de prompt descartada) para Q0001–Q0004 — nenhuma das 4
  anotações coincide com elas — e, durante a anotação, 3 respostas daquela versão para questões
  já anotadas (Q0007–Q0009). As respostas da versão hierárquica usada na política (v3) só foram
  geradas depois de as 359 anotações estarem gravadas.
- Não houve correção manual posterior das anotações: o arquivo versionado é a saída original.
- Custo: coberto pela assinatura do Claude Code do candidato (sem custo de API separado).
  Tempo: ~20 minutos de parede para as 359 questões.

## Instruções seguidas (mesma regra de negócio de `prompts/classificacao.md`)

1. Classificar pelo conteúdo cobrado, não pela disciplina/assunto de origem (frequentemente
   errados: ex. 43 questões marcadas "Concurso de Crimes" que tratam de furto, peculato, etc.).
2. Escolher um único tema central ativo e não-raiz; preferir o subtema mais específico que cubra
   a questão inteira; se a questão mistura vários subtemas do mesmo tema, escolher o tema (nível 1).
3. Nós-clone vazios (IDs 67xx, ver `config/nos_duplicados.json`) só como último recurso — a
   política nunca os publica.
4. Ramo pelo conteúdo: tipo penal/pena → Penal; procedimento/prova/prisão/recurso → Processo
   Penal; lei extravagante → Legislação Especial; teoria criminológica → Criminologia.
5. `extras_ids`: só temas materialmente cobertos além do central.
6. `fora=1` só quando nenhum tema serve (ex.: Direito Tributário puro); dúvida ≠ fora.
7. `confianca`: chance subjetiva de o tema central estar certo **segundo a régua** (mesmo nó,
   pai ou filho). Questões "colcha de retalhos" (várias assertivas de capítulos diferentes)
   recebem confiança baixa de propósito: não existe um tema central defensável.

## O que este arquivo NÃO é

Não é gabarito. É a saída de um modelo, sujeita a erro, e é tratada como um voto entre três.
A precisão real só pode ser medida com os rótulos da equipe da Vício.
