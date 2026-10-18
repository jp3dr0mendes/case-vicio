# Prompting e regras de saída

Os prompts do código são mantidos em `src/vicio_case/llm.py` para que uma mudança passe pela revisão de código. A regra essencial é uma taxonomia fechada e resposta JSON estruturada:

- O classificador deve escolher apenas `tema_id` que aparece na lista de candidatos.
- `disciplina_origem` e `assunto_origem` são pistas ruidosas e não ground truth.
- A seleção central deve representar o instituto jurídico efetivamente avaliado.
- `extras_ids` só registra outros temas materialmente avaliados.
- `fora` significa ausência de tema compatível, não simples dúvida.
- O revisor precisa avaliar a questão antes de decidir sobre a primeira resposta; subtemas irmãos não são equivalentes.
- Qualquer discordância ou erro de protocolo é encaminhado para revisão.

A confiança é autoavaliação do modelo e precisa ser calibrada. Não transformar um `0.98` emitido pelo LLM em garantia de 98% de acerto.
