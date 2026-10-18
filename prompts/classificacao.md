# Prompts do classificador local (Ollama), versão hierárquica v3

Usados por `src/vicio_case/llm.py`. A mesma regra de negócio orientou a anotação do
classificador forte (ver `prompts/anotador_forte.md`).

## Passo 1: tema (nível 1)

```
Você classifica questões de concursos jurídicos (Direito Penal, Processo Penal, Legislação Penal Especial, Criminologia).
Escolha o TEMA da lista que a questão realmente cobra (o assunto que o aluno precisa dominar). Use o conteúdo; disciplina/assunto de origem podem estar errados.
Tipo penal ou pena -> Penal; procedimento, prova, prisão, recurso -> Processo Penal; lei extravagante (drogas, Maria da Penha, abuso de autoridade, LEP...) -> Legislação Especial.
Se nenhum tema servir (questão de outra área do Direito), responda FORA.
Responda em JSON: {"assunto_cobrado": "frase curta dizendo qual instituto jurídico a questão cobra", "escolha": "copie exatamente uma das opções listadas"}.
NUNCA responda a questão de concurso nem escolha alternativa A/B/C/D/E: sua tarefa é só CLASSIFICAR o assunto.
TEMAS:
{{TEMAS_NIVEL_1_COM_SUBTEMAS}}
```

## Passo 2: subtema (só quando o tema escolhido tem filhos)

```
A questão é do tema '{{TEMA}}'. Escolha o subtema que ela cobra; se cobrir vários subtemas ou o tema em geral,
escolha '(o tema como um todo / vários subtemas)'.
(mesmas instruções de formato e a proibição de responder a questão)
OPÇÕES:
{{SUBTEMAS}}
```

Mensagem do usuário nos dois passos:

```
QUESTÃO A CLASSIFICAR (não responda; só diga o assunto):
{{ENUNCIADO + COMANDO + ALTERNATIVAS, HTML limpo}}
```

## Decisões de desenho (e becos sem saída)

- v2 (descartada): taxonomia inteira (371 linhas `id | caminho`) e resposta com `tema_central_id`.
  O qwen2.5:7b trocava dígitos dos IDs (ex.: Terrorismo 4706 -> Estatuto do Idoso 4696);
  concordância de ramo com o classificador principal 32% (29 de 90 respostas válidas), contra 38%
  (qwen) e 52% (llama) na versão hierárquica final. Parcial guardado em `artifacts/experimentos/`.
- enum com os caminhos (descartada): decodificação restrita enviesou para as primeiras opções
  em ordem alfabética ("Criminologia > ...").
- "escolha" sem instrução explícita (descartada): o modelo respondia a questão ("B: ...").
- qwen2.5:14b (descartado): não cabe na GPU da máquina (18% em CPU, swap esgotado).
- Nomes de nós-clone vazios não são oferecidos ao modelo; inativos e raízes também não.
- Resposta que não corresponde a uma opção é inválida; não há "palpite" por similaridade de
  texto. O casamento (`llm.match_option`) aceita: texto igual; mesmo último segmento do caminho
  quando ele é único (nome repetido em ramos diferentes, como "Ação Penal", é rejeitado);
  sufixo "(subtemas: …)" copiado da lista; no passo 2, repetir o nome do tema = "tema como um
  todo"; e erro de digitação com similaridade ≥ 0,92 e vencedor isolado (a própria árvore tem
  erros como "Caractéristas").
- Essas tolerâncias foram adicionadas durante as rodadas (três versões, todas estritas). Os 630
  votos válidos versionados foram reinterpretados com a versão final e dão exatamente o mesmo
  tema (`tests/test_llm_outputs.py` garante isso). As falhas antigas guardam só a mensagem de erro;
  a partir desta versão, cada falha registra passo, resultado parcial e a resposta bruta de cada
  tentativa.
