# Relatório técnico — Case de classificação de tópicos

## 1. Como pensei e o que escolhi

O erro relevante não é simplesmente uma resposta semanticamente próxima, mas colocar o aluno em outro ramo da taxonomia. Por isso, a solução usa uma taxonomia fechada, recuperação de candidatos, julgamento semântico e um gate de publicação separado. O campo de origem é tratado como indício ruidoso. A similaridade lexical ajuda a reduzir a lista de 371 temas/subtemas ativos; não é interpretada como probabilidade.

Evitei começar por treinamento supervisionado: o ZIP não contém os rótulos da equipe e o lote é pequeno para um classificador de tópicos de alta granularidade. Evitei um agente com ferramentas e banco vetorial dedicado: são componentes sem benefício comprovado para 359 questões e uma árvore de 377 nós. Para o case, a opção simples e auditável é mais fácil de reproduzir e explicar. Um modelo local via Ollama permite testar sem custo de API; o custo operacional passa a ser principalmente hardware/tempo/energia.

O fluxo semântico proposto chama o LLM para classificar apenas dentro de candidatos e outro estágio para verificar a proposta. Ambos precisam concordar para publicação ou para declarar `fora`. A política exige limiares altos e usa revisão para qualquer ambiguidade. A autoconfiança do modelo é registrada, mas o relatório não a confunde com precisão empírica.

## 2. Diagnóstico

O pacote contém 359 questões e 377 nós. Há 375 nós ativos (4 raízes e 371 temas/subtemas selecionáveis) e dois temas inativos. Noventa e quatro questões estão sem comando; 18 não têm assunto de origem; existe um registro sem disciplina de origem preenchida e nove registros com disciplina vazia, variantes ou fora do grupo principal esperado. Os enunciados têm HTML simples. A árvore apresenta títulos muito próximos, divisões por parte e grafias ruidosas. Há assuntos diferentes com palavras compartilhadas, então texto superficial pode levar a subtema irmão incorreto.

A principal limitação de validação é estrutural: o arquivo não traz o rótulo de referência usado pela equipe. Não é possível afirmar precisão real de 95% com base nesses dados. Essa limitação foi tratada como uma restrição de evidência, não preenchida com uma estimativa inventada.

## 3. Pipeline e controles

1. Validar JSONL, CSV e árvore; registrar hash do conjunto.
2. Limpar tags HTML e montar o texto com enunciado, comando e alternativas.
3. Recuperar candidatos por TF-IDF de palavras e caracteres, com um reforço pequeno dos metadados de origem.
4. Solicitar classificação JSON estruturada ao Ollama, com lista de candidatos, decisão, ID central, extras, confiança e motivo.
5. Solicitar verificação independente, reapresentando o conteúdo sem tratar a primeira resposta como verdade.
6. Aplicar regras determinísticas: ID ativo e pertencente aos candidatos; publicação só com os dois estágios votando `publicar`, alta confiança e mesmo ramo; `fora` só com dupla concordância; todo o restante vira revisão.
7. Validar o contrato final e gerar CSV, previsão e trilha de auditoria. PostgreSQL mantém histórico técnico do run.

A baseline não chama LLM e envia 359/359 para revisão. Esse resultado garante que a infraestrutura e o contrato funcionam sem inventar precisão, mas não maximiza cobertura e não deve ser submetido como a resposta final do case. A classificação semântica final exige execução do modo Ollama e revisão dos resultados.

## 4. Previsão, custo e produção

A previsão final de precisão deve ser preenchida depois da rodada semântica, antes de receber o rótulo de referência. A confiança por questão e o intervalo mínimo-máximo são um registro subjetivo inicial, não intervalo estatístico. A decisão definitiva do limiar deve vir de amostra estratificada rotulada por especialista, curva precisão-cobertura e limite inferior da estimativa de precisão de pelo menos 95%.

Para 50 mil questões semanais, manter o mesmo desenho lógico e otimizar: deduplicação por hash de texto, cache de candidatos por versão da taxonomia, chamadas em lotes, limite de concorrência, retry com backoff e rate limit. Use embeddings multilíngues ou jurídicos apenas se teste de recuperação demonstrar ganho sobre TF-IDF; usar um classificador treinado só depois de acumular rótulos aprovados. O LLM é reservado para escolher entre candidatos e lidar com casos semanticamente difíceis; revisão humana cobre os casos de baixo acordo/confiança. Reports de aluno alimentam triagem prioritária, mas nunca reclassificam automaticamente sem validação.

Sem fornecedor de API selecionado, não há preço unitário honesto para citar. Para API, custo esperado é `(tokens_entrada / 1.000.000 × preço_entrada) + (tokens_saída / 1.000.000 × preço_saída)`, multiplicado por passagens e pelo volume. Como ordem de grandeza de planejamento, duas passagens com 2–3 mil tokens de entrada e algumas centenas de saída por questão dariam cerca de 100–150 milhões de tokens de entrada em 50 mil questões; a contagem real deve ser medida em um piloto. Em Ollama não há cobrança por token, mas há custo e limite de hardware, energia e latência.

## 5. Próxima etapa necessária

Subir o modelo local, produzir uma rodada semântica, revisar amostra estratificada e analisar divergências por disciplina/nível. Ajustar recuperação e limiares, congelar versão de modelo/prompt/política, registrar custo/tempo e só então gerar a previsão definitiva. A precisão real só será conhecida após comparação com os rótulos que a equipe guardou.
