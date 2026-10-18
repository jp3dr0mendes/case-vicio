# Plano de controle de qualidade e governança

O plano é preventivo e detectivo: impede saídas estruturalmente inválidas, reduz publicação automática quando existe dúvida e cria evidências para recalibrar a política.

| Etapa | Controle | Critério / gate | Ação em caso de falha | Evidência |
|---|---|---|---|---|
| Entrada | JSONL e esquema | Todos os campos obrigatórios presentes; IDs únicos | Interromper lote, corrigir arquivo sem adivinhar valores | Erro de validação/log |
| Entrada | Taxonomia | IDs únicos, pais válidos, grafo sem ciclos | Interromper lote | Testes e `data_audit.json` |
| Entrada | Metadados | Campos ausentes contados; origem não é rótulo de verdade | Prosseguir e reduzir peso de metadados | Relatório de diagnóstico |
| Candidatos | Estado e ramo | Só temas ativos e nível >= 1; top-k registrado | Rejeitar ID inválido e mandar para revisão | `decision_audit.json` |
| LLM primário | Resposta estruturada | JSON válido; decisão enum; ID pertence aos candidatos | Retry limitado; se persistir, `revisar` | Erro por questão |
| Verificação | Consenso | Verificador confirma publicação e mesmo ramo | `revisar` | Votos e IDs gravados |
| Publicação | Confiança | Primário >= 0,95 e verificador >= 0,90 (valores iniciais) | `revisar`; recalibrar com rótulos | Confianças e versão da política |
| Exclusão (`fora`) | Dupla concordância | Dois estágios indicam ausência real de tema compatível | Caso contrário, `revisar` | Justificativa obrigatória |
| Exportação | Contrato CSV | 359 linhas exatas; IDs sem perda/duplicidade; valores válidos | Falhar build, não publicar arquivo | Teste de contrato |
| Métricas | Precisão | Limite inferior do intervalo de confiança em amostra de publicação >= 0,95 antes de automatizar | Aumentar limiar/revisão; suspender publicação se abaixo | Relatório de avaliação |
| Métricas | Cobertura | Maximizar cobertura apenas entre políticas que passam o gate de precisão | Manter thresholds conservadores | Série temporal por versão |
| Produção | Drift | Alteração em distribuição de temas, assuntos ou taxa de revisão | Revisar amostra e reavaliar candidatos/modelo | Dashboard/logs |
| Segurança | Prompt/data injection | Texto da questão é dado não confiável, nunca comando do sistema | Prompt fixo; sem ferramentas/agentes com ações externas | Testes adversariais |
| Operação | Falha de serviço | Timeout, indisponibilidade, formato inválido | Retry limitado; fallback `revisar`; não perder a questão | `decision_audit.json` + PostgreSQL |

## Indicadores operacionais

- **Precisão nas publicadas** = publicadas corretas segundo a regra hierárquica / total publicadas revisadas.
- **Cobertura** = `publicar` / 359 (ou total do lote ativo).
- **Taxa de revisão** = `revisar` / total; deve ser separada por motivo.
- **Taxa fora** = `fora` / total; monitorar para detectar excesso de exclusão.
- **Acordo primário-verificador** = questões em que concordam no ramo / questões avaliadas.
- **Taxa de correção pós-publicação** = questões publicadas corrigidas após reporte/auditoria / questões publicadas auditadas.
- **Latência/custo** = tempo por questão, tokens de entrada/saída e erro por componente.

## Calibração sem gabarito no lote

O lote entregue não contém rótulos. A autoconfiança não deve ser tomada como verdade. Antes de otimizar cobertura, o especialista precisa rotular uma amostra estratificada por disciplina, nível, confiança e tipo de decisão. Com essa amostra: calcular precisão por faixa de confiança; construir curva precisão-cobertura; escolher o limiar cujo limite inferior de confiança sustente 95%; separar conjunto de validação do lote usado para ajustar prompts. A amostra não deve ser usada para declarar resultado do conjunto secreto.

## Plano de rollback

Toda saída tem hash de entrada, modelo, limiares e data. Se auditoria encontrar precisão abaixo da régua, suspender auto-publicação, reprocessar as últimas questões da mesma versão para `revisar`, restaurar o último prompt/modelo validado e recalcular os indicadores. Não apagar a trilha anterior.
