# Próximos passos priorizados

## P0 — antes de qualquer entrega final

1. Construir imagem e subir serviços com `docker compose`; executar audit e testes em ambiente com Docker.
2. Configurar/baixar versão do modelo Ollama; registrar tag e digest, parâmetros e tempo de cada rodada.
3. Rodar inferência semântica de ponta a ponta; verificar se as 359 questões aparecem exatamente uma vez e se nenhuma saída usa tema inativo.
4. Auditar manualmente amostra estratificada, com ênfase em publicações de confiança alta, disciplina de origem divergente e temas com nomes semelhantes.
5. Ajustar threshold pela curva precisão-cobertura; gerar `previsao.txt` final sem rótulo conhecido e guardar versão do pipeline.

## P1 — melhorar recuperação e avaliação

- Comparar TF-IDF atual com embeddings locais via Ollama ou modelo multilíngue específico; avaliar recall@k de candidatos com rótulos da amostra.
- Criar suíte de casos difíceis/regressão: pai vs filho, irmãos, legislação especial, questão multitema, metadado errado, tema inativo e questão fora da árvore.
- Calibrar confiança (por faixa ou modelo de calibração) somente com rótulos e separação treino/validação; não calibrar usando a previsão autoatribuída do próprio LLM.
- Medir precisão e cobertura por disciplina, nível e família de temas, além da métrica geral.

## P2 — prontidão para produção

- Interface de fila humana: questão, alternativas, candidatos, justificativas, diff entre classificadores, aprovar/corrigir e registrar rótulo.
- Painel de métricas: precisão auditada, cobertura, taxa de revisão, taxa `fora`, acordo dos estágios, drift, latência e custo.
- Cache por hash normalizado da questão + hash da taxonomia + versão do modelo/prompt.
- Retry com backoff e dead-letter para erros persistentes; idempotência para reprocessar lote sem duplicar histórico.
- Versionar taxonomia, prompt, limiares e modelo; rollback para último conjunto aprovado.
- Integrar com importação de questões e reportes de alunos, mantendo o humano como controle final em casos de risco.

## P3 — escala semanal de 50 mil questões

- Fazer piloto de volume para medir tokens, latência e memória antes de dimensionar hardware.
- Executar classificação em lotes controlados e limitar concorrência; não criar microserviços adicionais até que métricas indiquem gargalo.
- Adicionar fila (por exemplo, Redis/Celery ou equivalente) somente se for necessário desacoplar a importação e a revisão.
- Fazer reavaliação periódica com amostra rotulada e gatilho para reduzir publicação automática quando o limite de precisão cair.
