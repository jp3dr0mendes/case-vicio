# Relatório de validação da implementação

## Resultado executado nesta sessão

| Checagem | Resultado | Evidência |
|---|---|---|
| Compilação de módulos e testes (`compileall`) | Passou | Sem erros de sintaxe nos módulos de `src/` e `tests/` |
| Testes automatizados | **18 passaram** | `PYTHONPATH=src pytest -q` — `18 passed` |
| Cardinalidade do conjunto | Passou | 359 questões; 377 nós na taxonomia; IDs de questões únicos |
| Auditoria de metadados | Passou | 94 sem `comando`; 18 sem `assunto_origem`; 1 sem disciplina preenchida |
| Contrato baseline CSV | Passou | Exatamente 359 linhas e as seis colunas solicitadas |
| Regras de publicação | Passou nos testes unitários | Gate duplo; limiares; discordância entre irmãos; exclusão com dupla concordância |
| Falha de modelo | Passou no teste simulado | Timeout encaminha o lote para revisão, sem publicação |
| Docker Compose como YAML | Passou | Parseado com PyYAML; serviços `db`, `app`, `ollama` e `adminer` presentes |
| Runtime Docker | **Não executado** | O executável `docker` não está instalado neste ambiente; build real, healthcheck e rede entre containers precisam ser validados no host de destino |
| Inferência semântica Ollama | **Não executada** | Não há servidor/modelo Ollama disponível nesta sessão |
| Precisão real nas publicadas | **Não mensurável aqui** | O ZIP não fornece os rótulos de referência guardados pela equipe |

## Artefatos gerados

- `artifacts/data_audit.json`: auditoria de dados.
- `artifacts/publicacao.csv`: baseline estrutural, uma linha por questão; todas são `revisar`.
- `artifacts/previsao.txt`: estado não final; precisão indefinida porque não há publicação.
- `artifacts/decision_audit.json`: candidatos lexicais da baseline e trilha por questão.
- `artifacts/run_metadata.json`: hash da entrada, configuração executada, duração e chamadas concluídas.

## Interpretação

Os testes garantem consistência estrutural e funcionamento dos gates determinísticos. Eles não comprovam acurácia jurídica. A saída baseline é deliberadamente conservadora e não deve ser enviada como resultado final; é preciso executar a inferência semântica, revisar amostra e produzir a previsão definitiva. Também não foi possível afirmar que o Docker sobe realmente, porque o runtime não existe nesta máquina.
