# Roadmap

O plano para depois da entrega (arquitetura de deploy, revisão humana, testes de outros modelos e
engenharia de prompt) está na seção "Próximos passos" do README. Aqui fica o estado de cada parte.

## Implementado e testado (neste repositório)
- Leitura/validação dos anexos, limpeza de HTML, auditoria (`audit`), com testes automáticos.
- Árvore com regra oficial (mesmo nó/pai/filho; irmão = erro), inativos, raízes e clones, com testes.
- Classificador principal (Claude Opus 5.5) para as 359 questões, com o arquivo versionado.
- Verificadores locais qwen2.5:7b e llama3.1:8b (Ollama nativo, Metal), com rodadas completas,
  retomáveis, com retentativas; falhas registradas.
- Política v3 determinística e testada; estimativa sem gabarito; previsão; entrega na raiz.
- PostgreSQL append-only via Docker; perfis `run`, `local-llm`, `ops` do Compose testados.

## Implementado, mas só parcialmente verificado
- Ollama em container: testado com um modelo pequeno (qwen2.5:0.5b) e o app conectado; as
  rodadas de 7–8B usaram o Ollama nativo, porque no macOS o container não tem GPU e a máquina
  (16 GB) não comporta o modelo em CPU dentro da VM com folga.
- Reprodutibilidade dos LLMs locais: temperatura 0 e seed fixa, mas sem garantia bit a bit
  entre versões do Ollama; as respostas usadas estão versionadas.

## Depende do especialista / da Vício
- Auditoria cega das 100 publicadas (`auditoria/folha_auditoria.html` → `medir-precisao`):
  até 1 erro comprova ≥ 95%; é o passo que transforma previsão em medição.
- Gabarito: só com rótulos da equipe a precisão passa de prevista a medida. Pedido: 100
  questões rotuladas às cegas para recalibrar as faixas de confiança e o desconto de critério.
- Regras da árvore: consolidar os 20 clones, escolher o ramo "oficial" dos assuntos repetidos,
  reativar ou substituir "Direito penal econômico", decidir o destino das questões "colcha de
  retalhos".
- Revisão da fila `revisar` (cada item já traz sugestão e motivo).

## Depende de modelo/infraestrutura
- Verificador mais forte (30B+ local ou API) → mais concordâncias, mais cobertura com a mesma
  precisão. A política e a estimativa não mudam; só entra mais um `--model`.
- Classificador treinado sobre embeddings com os rótulos revisados (camada barata para produção).
- Pipeline semanal de 50 mil questões descrito no relatório (seção c).
