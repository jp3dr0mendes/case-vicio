# Entendimento do case e critérios de aceite

## Objetivo

Classificar 359 questões de concursos dentro de uma taxonomia disponível de 377 nós, com uma decisão de `publicar`, `revisar` ou `fora` por questão. Publicar errado é o custo mais alto; encaminhar para revisão consome tempo de especialista; `fora` retira a questão do recorte quando não há tema compatível.

## Requisitos duros

1. Cada questão do JSONL precisa aparecer exatamente uma vez no CSV final.
2. `publicar`/`revisar` devem conter tema central existente e ativo; `fora` deve deixar tema central vazio.
3. `extras_ids` é opcional e só deve conter temas adicionais que a questão cobre materialmente.
4. Confiança numérica entre 0 e 1. Não confundir similaridade lexical com probabilidade de acerto.
5. `motivo` obrigatório para revisão e exclusão.
6. Precisão real nas publicadas de pelo menos 95%; sob esta condição, maximizar a cobertura publicada.
7. Tema central igual ao rótulo de referência ou ancestral/descendente no mesmo ramo é correto; subtema irmão conta como erro.
8. Entregar CSV, previsão anterior ao gabarito, relatório de até cinco páginas, memo para professor e código reprodutível.

## Estratégia proposta

A melhor solução para este lote é um pipeline de classificação hierárquica com abstenção, não um agente autônomo amplo: (a) validação/normalização; (b) recuperação de candidatos pela árvore; (c) LLM com saída estruturada para julgar questão versus candidatos; (d) verificação independente; (e) decisão por política conservadora; (f) revisão humana dos casos duvidosos; (g) trilha para auditoria e recalibração. A seleção de candidatos diminui o espaço de resposta do modelo, e a validação de ID/ramo impede que texto livre invente temas.

## Critério de aceite para a solução

- Integridade: 359 linhas; nenhum ID faltante ou duplicado.
- Taxonomia: nenhum tema inativo ou inexistente publicado.
- Segurança: sem resposta do modelo, resposta inválida, divergência ou baixa confiança, a questão nunca é publicada automaticamente.
- Precisão: precisa ser verificada em amostra rotulada ou conjunto guardado; não pode ser inferida apenas pela autoconfiança do LLM.
- Cobertura: medir fração de `publicar` e aumentar apenas sem degradar o limite de precisão validado.
- Reprodutibilidade: registrar modelo, prompt/versão, limiares, hash dos dados, latência, erros e IDs de candidatos.

## Limitação importante

O arquivo recebido não contém os rótulos de referência guardados pela equipe. Portanto, é possível auditar contrato, estrutura dos dados e consistência do código, mas não calcular localmente a precisão real do classificador nem demonstrar que já alcançou 95%.
