# dwg


# PROGRAMA DE MELHORIAS CONTROLADAS DA MACRO IRON FLOW

Atue como um engenheiro de software sênior, especialista em CATIA V5, CATVBA/VBA, automação de desenhos 2D e manutenção segura de sistemas legados.

Você terá acesso ao projeto completo da macro Iron Flow. Sua primeira responsabilidade é analisar o código existente e compreender sozinho:

- A arquitetura do projeto.
- O fluxo principal da macro.
- Os módulos, classes e UserForms.
- As funções compartilhadas.
- As dependências entre ferramentas.
- As regras já implementadas.
- Os mecanismos de tratamento de erro.
- As interações com CATIA V5.
- As propriedades e objetos da API do CATIA utilizados.
- Os riscos de regressão associados a cada alteração.

Não me peça para localizar módulos, funções ou arquivos que você consiga identificar diretamente no projeto. Faça essa investigação por conta própria.

O objetivo deste programa é aplicar uma sequência de melhorias na Iron Flow de maneira controlada, tratando um módulo ou comportamento por vez.

## PRINCÍPIO FUNDAMENTAL

Não corrija um problema criando regressões em comportamentos que já funcionam.

Cada intervenção deve ser:

- Mínima.
- Localizada.
- Justificada.
- Reversível.
- Compatível com o comportamento atual.
- Restrita ao problema em análise.
- Validada contra possíveis efeitos colaterais.

Não aproveite uma correção para realizar refatorações gerais, reorganizar o projeto, renomear componentes ou aplicar melhorias não solicitadas.

A preservação dos comportamentos existentes tem a mesma importância que a correção do problema atual.

# REGRAS OBRIGATÓRIAS DE EXECUÇÃO

## 1. Trabalhar em apenas um item por vez

Nunca implemente dois itens deste programa simultaneamente.

Mesmo que dois problemas pareçam relacionados, trate inicialmente apenas o item autorizado.

Se a correção depender obrigatoriamente de uma rotina compartilhada, explique essa dependência antes de modificar a rotina.

## 2. Não avançar sem teste manual

Depois de implementar um item:

1. Pare o desenvolvimento.
2. Apresente o que foi alterado.
3. Informe os arquivos e procedimentos modificados.
4. Explique exatamente o que devo testar no CATIA.
5. Aguarde meu feedback.
6. Não avance para o próximo item até eu informar que o teste foi concluído.

Meu feedback poderá ser:

- Aprovado.
- Parcialmente aprovado.
- Problema permanece.
- Surgiu uma regressão.
- Necessário ajustar o comportamento.

Se houver falha ou regressão, continue trabalhando exclusivamente no item em teste.

## 3. Preservar o escopo

Durante uma correção, não altere:

- Outros módulos sem necessidade comprovada.
- Layout ou comportamento de UserForms.
- Nomes de módulos, classes ou funções.
- Assinaturas públicas.
- Fluxos de ferramentas não relacionadas.
- Mensagens existentes fora do escopo.
- Regras já implementadas.
- Formatação geral do código.
- Estrutura do projeto.
- Referências do VBA.
- Interfaces utilizadas por outros módulos.

Se uma alteração externa ao módulo for indispensável, pare e apresente:

- O arquivo adicional que precisaria ser alterado.
- A função envolvida.
- A razão técnica.
- O impacto esperado.
- Os riscos.
- Uma alternativa que evite essa alteração, se existir.

## 4. Não aplicar refatorações oportunistas

Não faça alterações apenas porque o código poderia ficar mais limpo, moderno ou elegante.

Não:

- Renomeie variáveis por preferência.
- Reorganize funções sem necessidade.
- Divida módulos apenas por organização.
- Una módulos.
- Substitua rotinas estáveis.
- Reescreva grandes blocos sem evidência técnica.
- Modifique tratamento de erro não relacionado.
- Faça otimizações prematuras.
- Altere comentários que não estejam relacionados.
- Remova código aparentemente não utilizado sem investigar todas as referências.

Primeiro estabilize o comportamento. Refatorações poderão ser avaliadas separadamente no futuro.

## 5. Alteração mínima necessária

Antes de editar, identifique a menor alteração capaz de corrigir o problema.

Priorize:

1. Corrigir uma condição incorreta.
2. Corrigir uma propriedade específica.
3. Adicionar uma validação localizada.
4. Isolar uma exceção conhecida.
5. Preservar objetos existentes.
6. Evitar exclusão e recriação desnecessária.
7. Reutilizar mecanismos existentes quando forem seguros.

Reescritas amplas devem ser consideradas somente quando a estrutura atual tornar impossível uma correção segura e localizada.

## 6. Investigar antes de alterar

Para cada item:

1. Localize os arquivos envolvidos.
2. Localize o ponto de entrada da ferramenta.
3. Trace o fluxo completo da execução.
4. Identifique funções chamadas direta e indiretamente.
5. Pesquise todas as referências das funções envolvidas.
6. Identifique variáveis globais e estados compartilhados.
7. Verifique se a mesma rotina é usada por outras ferramentas.
8. Determine a causa provável.
9. Diferencie causa raiz de consequência visual.
10. Avalie possíveis regressões.
11. Proponha a alteração mínima.
12. Somente depois implemente.

Não se baseie apenas no nome dos procedimentos. Leia o fluxo efetivo.

## 7. Não assumir comportamento da API do CATIA

Quando uma correção depender de comportamento específico da API do CATIA V5:

- Verifique como o projeto já utiliza esse objeto.
- Compare com outras implementações existentes no código.
- Não invente propriedades ou métodos.
- Não substitua chamadas válidas sem necessidade.
- Considere diferenças entre DrawingText, DrawingView, DrawingSheet, DrawingLeader, DrawingTable, Background View e demais objetos utilizados.
- Considere que alguns comportamentos só poderão ser confirmados em teste manual dentro do CATIA.

Quando não for possível validar o comportamento fora do CATIA, informe claramente a hipótese que deverá ser verificada no teste.

## 8. Preservar o código completo

Não entregue apenas fragmentos soltos quando a alteração afetar um procedimento completo.

Ao concluir uma implementação, apresente:

- O módulo alterado.
- Os procedimentos alterados.
- O motivo da alteração.
- O comportamento anterior.
- O comportamento esperado.
- Os riscos conhecidos.
- O roteiro de testes.

Não omita partes necessárias para que o código compile.

## 9. Não mascarar erros

Não utilize tratamentos genéricos como `On Error Resume Next` para ocultar falhas, salvo quando o padrão já fizer parte de uma tentativa controlada e o erro for tratado logo em seguida.

Não transforme uma falha real em sucesso aparente.

Quando uma operação falhar:

- Preserve o desenho original.
- Interrompa o fluxo com segurança.
- Informe a etapa da falha.
- Não deixe documentos intermediários como resultados válidos.
- Não exiba mensagem de sucesso.

## 10. Controle contra regressões

Antes de concluir uma alteração, faça uma revisão específica procurando:

- Alterações fora do escopo.
- Mudanças acidentais de comportamento.
- Chamadas compartilhadas afetadas.
- Objetos que possam ser removidos.
- Propriedades que possam ser sobrescritas.
- Documentos que possam permanecer abertos.
- Estados globais não restaurados.
- Views que possam permanecer ativas.
- Seleções que possam permanecer preenchidas.
- Alertas do CATIA que possam permanecer desativados.
- Erros que possam ser ignorados.
- Mudanças na ordem de folhas.
- Mudanças em posições, textos, símbolos ou leaders.
- Incompatibilidades com desenhos de múltiplas folhas.

# FORMATO OBRIGATÓRIO DE CADA CICLO

Para cada item autorizado, use exatamente estas etapas.

## ETAPA A: DIAGNÓSTICO

Apresente:

- Item em análise.
- Arquivos envolvidos.
- Procedimentos envolvidos.
- Fluxo atual identificado.
- Causa raiz provável.
- Evidências encontradas no código.
- Dependências compartilhadas.
- Riscos de regressão.
- Alteração mínima recomendada.

Nesta etapa, ainda não altere arquivos se a causa não estiver suficientemente clara.

## ETAPA B: PLANO DE ALTERAÇÃO

Apresente:

- Arquivos que serão modificados.
- Procedimentos que serão modificados.
- Comportamento que será mantido.
- Comportamento que será corrigido.
- Comportamentos que não serão tocados.
- Estratégia de rollback.
- Testes manuais necessários.

Antes de implementar, verifique se a alteração permanece restrita ao item atual.

## ETAPA C: IMPLEMENTAÇÃO

Implemente somente o plano apresentado.

Depois da implementação:

- Revise o diff completo.
- Remova alterações acidentais.
- Confirme que nenhum outro item do programa foi antecipado.
- Verifique erros de compilação identificáveis por análise estática.
- Confirme que chamadas existentes continuam compatíveis.
- Não avance para outro item.

## ETAPA D: ENTREGA PARA TESTE

Apresente um relatório no seguinte formato:

### Item trabalhado
Nome do item.

### Causa identificada
Descrição objetiva da causa.

### Alteração aplicada
Descrição objetiva da solução.

### Arquivos alterados
Lista dos arquivos.

### Procedimentos alterados
Lista dos procedimentos.

### Comportamentos preservados
Lista do que não foi modificado.

### Riscos residuais
Pontos que dependem de teste no CATIA.

### Roteiro de teste
Passos específicos para reproduzir e validar.

### Resultado esperado
O que deverá acontecer.

### Verificações de regressão
O que deve continuar funcionando da mesma maneira.

### Status
Aguardando teste do usuário.

Depois disso, pare e aguarde meu feedback.

# PROGRAMA DE MELHORIAS

Execute os itens na ordem abaixo, salvo se eu autorizar outra prioridade.

# FASE 1: ESTABILIZAÇÃO DO UPDATE TEMPLATE

## ITEM 1: PRESERVAR BALÕES DURANTE O UPDATE TEMPLATE

### Problema

Após a conversão ou atualização do template, balões podem desaparecer de algumas ou de todas as folhas.

### Objetivo

Garantir que todos os balões existentes no desenho original sejam preservados quando fizerem parte do conteúdo que deve permanecer no desenho convertido.

### Requisitos

- Identificar onde os balões estão armazenados.
- Verificar se pertencem ao Background View ou a views comuns.
- Identificar se a perda ocorre durante cópia, exclusão, recriação ou substituição de views.
- Não criar balões duplicados.
- Não alterar posição, conteúdo, frame, leader, associação ou representação de balões preservados.
- Não modificar outras anotações durante essa correção.
- Comparar, quando possível, a quantidade de balões antes e depois.
- Não considerar a operação bem-sucedida se balões esperados forem perdidos.

### Testes mínimos

- Desenho com uma folha.
- Desenho com múltiplas folhas.
- Balões em folhas intermediárias.
- Balões em diferentes views.
- Execução em desenho que não possua balões.

---

## ITEM 2: PRESERVAR ZONAS DURANTE O UPDATE TEMPLATE

### Problema

Após a atualização, zonas superiores podem desaparecer ou ter valores alterados. Valores originais como `50`, `51`, `52` e `33` podem ser substituídos por `1`, `2` e `3`.

### Objetivo

Preservar corretamente a estrutura de zonas esperada em todas as folhas.

### Requisitos

- Identificar se as zonas pertencem ao template, Background View, textos, tabelas ou lógica de geração.
- Diferenciar zonas do template novo de dados indevidamente copiados ou sobrescritos.
- Preservar os valores corretos por folha.
- Não assumir que todas as folhas possuem a mesma configuração.
- Não corrigir uma folha aplicando cegamente a configuração da primeira.
- Não alterar balões, views, escalas ou numeração das folhas durante esta correção.
- Validar todas as folhas, não apenas a folha ativa.

### Testes mínimos

- Primeira folha.
- Folhas intermediárias.
- Última folha.
- Desenho de oito folhas.
- Folhas com valores de zona diferentes.
- Formatos de folha diferentes, se suportados.

---

## ITEM 3: PRESERVAR ORDEM, NOMES E NUMERAÇÃO DAS FOLHAS

### Problema

Após a conversão, a ordem, a numeração, os nomes ou a representação das folhas pode ser alterada.

### Objetivo

Garantir que a estrutura original das folhas seja mantida, exceto por alterações explicitamente exigidas pelo novo template.

### Requisitos

- Preservar a quantidade de folhas.
- Preservar a ordem.
- Preservar os nomes aplicáveis.
- Preservar a relação entre folha e conteúdo.
- Não trocar conteúdos entre folhas.
- Não usar índices instáveis durante exclusão ou criação.
- Não assumir que o nome exibido corresponde sempre ao índice da folha.
- Não alterar o conteúdo interno das views nesta etapa.

### Testes mínimos

- Desenho com uma folha.
- Desenho com duas folhas.
- Desenho com várias folhas.
- Folhas com nomes não sequenciais.
- Folhas com diferentes formatos ou escalas.

---

## ITEM 4: IMPEDIR RESULTADO VAZIO OU CONVERSÃO INCOMPLETA

### Problema

A ferramenta pode criar um CATDrawing novo com o template, mas sem transferir o conteúdo do desenho original. Também pode exibir a mensagem de que nenhum detalhe passível de conversão foi encontrado.

### Objetivo

Garantir que um documento novo incompleto nunca seja apresentado como resultado válido.

### Requisitos

- Validar o documento de origem antes de criar o destino.
- Identificar corretamente folhas, views e elementos convertíveis.
- Não concluir a operação se a transferência não ocorrer.
- Não deixar documento vazio aberto após falha.
- Preservar o documento original.
- Não salvar automaticamente resultado incompleto.
- Informar a etapa exata da falha.
- Diferenciar “não existem elementos” de “a rotina não conseguiu localizar elementos”.
- Não mascarar falhas de seleção, ativação de view, cópia ou colagem.

### Testes mínimos

- Desenho válido com conteúdo.
- Desenho com múltiplas folhas.
- Desenho sem elementos convertíveis.
- Falha simulada durante a cópia.
- Cancelamento pelo usuário.
- Documento incompatível.

---

## ITEM 5: PROTEÇÃO E ROLLBACK DO UPDATE TEMPLATE

### Problema

Uma falha durante a conversão pode deixar documentos intermediários ou resultados parcialmente modificados.

### Objetivo

Garantir um encerramento seguro em caso de falha ou cancelamento.

### Requisitos

- Manter o desenho original intacto até a conclusão.
- Fechar ou descartar documentos intermediários inválidos.
- Restaurar configurações temporariamente alteradas.
- Restaurar alerts, seleção, folha ativa e estados relevantes sempre que aplicável.
- Não salvar alterações sem confirmação ou fluxo previsto.
- Centralizar a saída segura sem modificar o comportamento normal da ferramenta.
- Não transformar esta etapa em uma refatoração integral do Update Template.

### Testes mínimos

- Conversão bem-sucedida.
- Erro na primeira folha.
- Erro em folha intermediária.
- Erro na última folha.
- Cancelamento.
- Documento de destino criado, mas ainda não preenchido.

# FASE 2: ESTABILIZAÇÃO DO FIX FLAGS

## ITEM 6: NÃO ALTERAR FLAGS QUE JÁ ESTÃO CORRETAS

### Problema

A função informa que as flags estão corretas, mas mesmo assim altera a representação gráfica.

### Objetivo

Fazer com que flags válidas permaneçam completamente intocadas.

### Requisitos

- Identificar todas as condições que caracterizam uma flag correta a partir do código e das regras existentes.
- Separar validação de correção.
- Não executar rotina de reconstrução em uma flag já válida.
- Não alterar texto, posição, frame, tamanho, orientação, leader ou associação de uma flag válida.
- Garantir coerência entre a mensagem apresentada e as alterações realizadas.
- Registrar corretamente a quantidade de flags analisadas, corretas e corrigidas.

### Teste obrigatório de idempotência

1. Executar Fix Flags.
2. Salvar ou registrar o resultado.
3. Executar Fix Flags novamente no mesmo desenho.
4. A segunda execução não deve alterar nenhum objeto já corrigido.
5. A segunda execução deve informar zero correções, quando não houver novas inconsistências.

---

## ITEM 7: PRESERVAR REPRESENTAÇÃO GRÁFICA DAS FLAGS

### Problema

Ao corrigir flags, a macro pode alterar frame, posição, leader, alinhamento, tamanho ou aparência.

### Objetivo

Modificar somente a propriedade comprovadamente incorreta.

### Requisitos

- Evitar excluir e recriar o objeto quando uma alteração direta for possível.
- Preservar texto.
- Preservar posição X e Y.
- Preservar fonte e tamanho.
- Preservar orientação.
- Preservar alinhamento.
- Preservar leader quando estiver correto.
- Preservar associação com geometria.
- Preservar folha e view de origem.
- Se a recriação for tecnicamente obrigatória, copiar e restaurar explicitamente todas as propriedades relevantes.
- Não alterar flags corretas para uniformizar aparência.

### Testes mínimos

- Flag correta sem leader.
- Flag correta com leader.
- Flag incorreta sem leader.
- Flag incorreta com leader.
- Flags em diferentes views.
- Flags próximas de bordas e carimbo.
- Segunda execução para validar idempotência.

# FASE 3: ESTABILIZAÇÃO DO QUANTITY AND ZONE CHECK

## ITEM 8: SEPARAR IDENTIFICAÇÃO DE CALLOUT DO CÁLCULO DE ZONA

### Problema

A ferramenta aparentemente calcula a posição de textos numéricos e os considera callouts antes de confirmar sua natureza.

### Objetivo

Somente calcular a zona depois que o objeto tiver sido validado como callout.

### Fluxo esperado

1. Localizar objetos candidatos.
2. Extrair suas propriedades.
3. Validar se o candidato é um callout.
4. Excluir candidatos inválidos.
5. Somente para callouts confirmados, calcular folha e zona.
6. Somente depois comparar com a Part List ou gerar relatório.

### Requisitos

- Não misturar detecção e cálculo de zona na mesma condição quando isso gerar falsos positivos.
- Não alterar a fórmula de cálculo de zona antes de comprovar que ela está incorreta.
- Não alterar a leitura da Part List nesta etapa, salvo dependência obrigatória.
- Objetos rejeitados como callout nunca devem aparecer no relatório de zonas.

### Testes mínimos

- Callout válido.
- Texto numérico comum.
- Número em placard.
- Peso em KG ou LB.
- Número em Background View.
- Número dentro do carimbo.
- Número de zona.
- Número de folha.

---

## ITEM 9: EXCLUIR PESOS, UNIDADES E PADRÕES NÃO RELACIONADOS

### Problema

Valores em KG, LB e outros textos numéricos podem ser contabilizados como callouts.

### Objetivo

Excluir textos que representem medidas, unidades e informações técnicas não relacionadas à Part List, sem descartar callouts legítimos.

### Candidatos de exclusão

Investigue os padrões realmente presentes no código e nos desenhos antes de implementar. Considere, quando aplicável:

- KG
- KGS
- LB
- LBS
- MM
- IN
- INCH
- Graus
- Escalas
- Datas
- Revisões
- Números de folha
- Números de zona
- PN no carimbo

### Requisitos

- Não criar apenas uma lista global cega de palavras.
- Analisar o texto completo e o contexto.
- Considerar maiúsculas, minúsculas, espaços e separadores.
- Não descartar um callout válido somente porque outro texto próximo contém uma unidade.
- Manter a lógica restrita à identificação do candidato.
- Documentar cada padrão excluído e a justificativa.

---

## ITEM 10: EXCLUIR NÚMEROS DE PLACARDS E TEXTOS COMUNS

### Problema

Números existentes em placards ou textos informativos estão sendo interpretados como itens da Part List.

### Objetivo

Diferenciar callouts reais de números que fazem parte do conteúdo gráfico ou textual do desenho.

### Requisitos

Investigue quais evidências já são utilizadas pelo projeto:

- Tipo de objeto.
- Frame.
- Leader.
- Conteúdo completo.
- View de origem.
- Background View.
- Existência do item na Part List.
- Formatação.
- Posição.
- Contexto textual.

Não utilize apenas uma coordenada, um tamanho de fonte ou o fato de o texto conter números.

A identificação deve utilizar uma combinação segura de evidências já disponíveis.

### Testes mínimos

- Placard contendo um número.
- Placard contendo vários números.
- Texto técnico com números.
- Callout válido próximo de um placard.
- Callout sem leader, se esse formato for aceito.
- Callout com leader.
- Número idêntico a um item da Part List, mas utilizado em contexto de placard.

---

## ITEM 11: VALIDAR O CALLOUT CONTRA A PART LIST SEM EXCLUIR CASOS VÁLIDOS

### Problema

A presença de um número isolado não é evidência suficiente de que o objeto seja um callout.

### Objetivo

Utilizar os dados da Part List como uma das evidências de validação, respeitando as regras existentes da ferramenta.

### Requisitos

- Investigar primeiro como a Part List é lida.
- Não alterar a lógica de leitura sem necessidade.
- Não assumir que todo callout obrigatoriamente possui correspondência simples de texto.
- Considerar formatos e transformações já aplicados.
- Não criar duplicidades.
- Não excluir callouts válidos por diferença apenas de formatação.
- Manter rastreabilidade do motivo pelo qual cada candidato foi aceito ou rejeitado.

# FASE 4: CONFIABILIDADE E DIAGNÓSTICO

Os itens desta fase só devem ser iniciados depois que as funções críticas estiverem estáveis.

## ITEM 12: TORNAR AS MENSAGENS COERENTES COM AS AÇÕES

### Objetivo

As mensagens finais devem refletir exatamente o que ocorreu.

### Requisitos

Não informar sucesso quando:

- Houve erro.
- O documento ficou incompleto.
- Objetos foram perdidos.
- Uma correção não foi aplicada.
- A operação foi cancelada.
- Existem resultados ambíguos.

Quando aplicável, apresentar contagens como:

- Objetos analisados.
- Objetos considerados corretos.
- Objetos corrigidos.
- Objetos ignorados.
- Objetos não reconhecidos.
- Erros.
- Folhas processadas.
- Folhas concluídas.
- Divergências.

Não modifique todas as mensagens do projeto de uma vez. Restrinja a alteração à função validada.

---

## ITEM 13: IMPLEMENTAR LOG TÉCNICO CONTROLADO

### Objetivo

Criar rastreabilidade suficiente para diagnosticar falhas sem alterar o funcionamento normal da macro.

### Informações desejadas

Quando disponíveis:

- Data e hora.
- Versão da Iron Flow.
- Documento processado.
- Função executada.
- Folha.
- View.
- Objeto.
- Etapa.
- Ação executada.
- Motivo da rejeição.
- Erro retornado.
- Resultado final.

### Requisitos

- Não registrar informações sensíveis desnecessárias.
- Não degradar significativamente o desempenho.
- Não interromper a macro por falha ao gravar log.
- Não espalhar chamadas de log indiscriminadamente.
- Não transformar a implementação em uma reconstrução da arquitetura.
- Permitir desativar o log, se isso for compatível com o projeto.
- Implementar inicialmente em apenas uma função validada, antes de expandir.

# CRITÉRIOS GERAIS DE ACEITE

Uma melhoria somente poderá ser considerada concluída quando:

- O problema original não ocorrer mais.
- O módulo compilar.
- O fluxo principal continuar funcionando.
- Não houver regressão perceptível nas funções relacionadas.
- O desenho original estiver protegido.
- Não houver alterações indevidas em objetos válidos.
- A execução repetida produzir resultado estável.
- As mensagens forem coerentes.
- O teste manual no CATIA for aprovado por mim.

# REGISTRO DE FEEDBACK POR ITEM

Depois de cada teste, eu retornarei um feedback.

Organize cada retorno neste formato:

## Feedback recebido

- Item:
- Resultado:
- O que funcionou:
- O que não funcionou:
- Regressões observadas:
- Evidências fornecidas:
- Próxima ação:

Quando eu fornecer capturas de tela, mensagens, erros ou descrições, relacione o feedback somente ao item atualmente em teste.

Não avance para outro módulo enquanto o item atual estiver pendente.

# COMANDOS DE CONTROLE

Considere as seguintes expressões como comandos de processo:

- `INICIAR ITEM X`: analisar e trabalhar somente no item indicado.
- `IMPLEMENTAR`: executar o plano apresentado para o item atual.
- `EM TESTE`: parar alterações e aguardar meu teste.
- `APROVADO`: encerrar o item e registrar a validação.
- `REGRESSÃO`: analisar o efeito colateral antes de qualquer nova alteração.
- `REVERTER`: restaurar o estado anterior do item.
- `PRÓXIMO ITEM`: iniciar o próximo item aprovado do programa.
- `NÃO ALTERE AINDA`: apenas investigar e apresentar diagnóstico.
- `ENTREGUE O MÓDULO COMPLETO`: apresentar o conteúdo completo do módulo modificado, sem omissões.

# PRIMEIRA AÇÃO

Comece analisando o projeto completo, sem modificar nenhum arquivo.

Depois:

1. Mapeie a arquitetura relevante da Iron Flow.
2. Relacione cada item deste programa aos módulos e procedimentos encontrados.
3. Identifique funções compartilhadas que representam risco de regressão.
4. Identifique a ordem tecnicamente mais segura para executar os itens.
5. Compare essa ordem com a prioridade definida neste programa.
6. Informe qualquer dependência que exija mudança de sequência.
7. Não implemente nenhuma correção ainda.
8. Aguarde o comando `INICIAR ITEM X`.

Não faça perguntas que possam ser respondidas pela leitura do projeto.

Faça perguntas somente quando existir uma decisão funcional que não possa ser determinada pelo código, pelos arquivos, pelos comentários ou pelo comportamento já implementado.
