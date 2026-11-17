# Migração do VBA para Python

Regra: cada ferramenta precisa funcionar igual ou melhor que o VBA, sem perder nada.
O VBA continua em uso até a versão Python passar pela comparação.

## De onde vem o código

`vba_referencia/` guarda, sem nenhuma alteração, os códigos do `dwg-main.zip` enviado pelo
usuário em 04/11/2026. A pasta `legacy_vba/` está **desatualizada** e não serve de base.

`tests/versoes_base.json` guarda a origem e a impressão digital de cada macro usada como base.
`tests/test_versoes_base.py` falha se uma macro já convertida mudar depois da conversão.

| Ferramenta | Base | Situação |
|---|---|---|
| Font Size Check | `sizedetect.txt`, `frmFontNav.txt` do CONSERTO-E1DWGVBA | Convertido |
| Update Template | `update.txt` do CONSERTO-E1DWGVBA (23/10) | Convertido |
| Fix Flags | `vba_referencia/fixflags` | Convertido |
| Position and Zone | `vba_referencia/poszone` (V3.5.1) | Convertido |
| Split 2D e 3D | `vba_referencia/SPLIT 2D`, `SPLIT 3D` | Convertido |
| Check de Flags | Mesmas regras do Fix Flags, sem gravar | Novo, na aba Check |
| Check de Template | Legenda real das fotos do desenho 171-54397-801 | Novo, na aba Check |
| Font Size Fix | Mesmas regras do Font Size Check, mudando o tamanho | Novo, na aba Design |
| Comparação no Excel | `vba_referencia/excel` | Continua no Excel |
| Painel | `vba_referencia/symbol shape` | Substituído pelo HUB |
| Symbol Shape | `vba/symbolconvert.txt` (`CATMain11`, colado pelo usuário em 11/11/2026) | Convertido, igual à macro em `rodar_paridade_symbol.py` |

Tudo abre por `main_qt.py`. `main.py` e `src/engine/update_template.py` são da interface antiga, com
a versão de 14/10 do Update Template, e não fazem parte da migração.

### Versões decididas pelo usuário (04/11/2026)

Dois arquivos do zip são mais antigos que os do CONSERTO-E1DWGVBA, e continua valendo o mais recente:

- **`update`**: mesmo texto de `legacy_vba/UPDATETEMPLATE.bas` (14/10), que copia as vistas para um
  documento novo. Vale o `update.txt` de 23/10, que troca o formato no próprio desenho.
- **`sizedetect`**: ainda pinta o desenho e pede o formato no combobox. Vale o `sizedetect.txt` de
  04/11, que não pinta e lê o formato no Background. As regras de tamanho são iguais nos dois.

Os acentos das mensagens de `vba_referencia/poszone` viraram espaços ("n o foi encontrado"). As
mensagens em Python saíram com os acentos certos.

## Telas

O visual segue o protótipo em `design/hub_prototipo.html`. Só aparece o que funciona de verdade:

- **Feito.** Sequência de aplicação, com a parada depois da etapa atual. Visão geral do Check, com
  os resultados e os contadores desta sessão. Prévia sem alterar o documento no Update Template e nos
  Splits. Correção do formato por folha no Update Template. Pendências do Position and Zone, com
  navegação até cada uma no CATIA. Tamanho real dos arquivos gerados, comparado a 200 MB.
- **Cada conferência tem a sua correção.** Fix Flags corrige e Check de Flags confere, com as mesmas
  regras. Font Size Fix corrige e Font Size Check confere. `tests/parity/testar_check_e_fix.py` prova
  que o Check aponta o que o Fix corrige e que, depois do Fix, o Check não aponta mais nada.
- **Fora, por falta de lógica.** PDF antes e depois, relatório em PDF e o Split por limite de 200 MB
  são recursos novos, que as macros não têm. Não aparecem, em vez de botões sem efeito.
- **Compare DWG.** É um programa externo, que o HUB só abre. O caminho é escolhido na tela e fica
  guardado em `%APPDATA%\\E1DWGTools\\config.json`, fora da pasta do HUB.
- **Font Size Fix não corrige cotas.** O V5R20 não lê o tamanho de cota, então não há como testar aqui.
- **Fora, por pedido do usuário.** Cronômetro e tempo estimado.
- **Trocado.** No Fix Flags, a tabela por folha do protótipo virou a lista de cada flag, com
  navegação, que mostra mais. O Symbol Shape roda na sequência depois do Update Template.

## Como cada ferramenta é convertida

Quem define onde cada coisa roda é o tipo de trabalho. Foi medido no CATIA V5R20:

- **Muitos textos ou geometrias: script dentro do CATIA** (`src/engine/catia_scripts`). Ler ou
  percorrer item por item é de 40 a 200 vezes mais rápido. Usado no Font Size Check, no Fix Flags
  e na leitura do Position and Zone.
- **Comandos de documento (abrir, copiar, colar, salvar): por COM, em Python.** Dentro de um script
  eles ficam 10 vezes mais lentos, e o comando seguinte a um script também. Usado no Update Template
  e nos Splits, com `RefreshDisplay = False`, que sozinho deixa a conversão duas vezes mais rápida.
- **Regras: em Python, sempre que possível**, para poderem ser testadas sem o CATIA.

Toda função de script embrulha a parte real com `On Error Resume Next` e devolve o erro como texto,
para nunca abrir janela de erro no CATIA. Toda rotina auxiliar com `On Error Resume Next` termina
com `Err.Clear`. Em VBScript, parâmetro que a rotina altera precisa de `ByVal`, ou altera o original.

Um teste de paridade roda a macro atual e a versão Python nos mesmos documentos e compara tudo o que
o usuário veria. O tempo é medido alternando quem roda primeiro, porque o CATIA fica mais lento ao
longo da sessão. A macro de referência roda pelo Excel, não dentro do CATIA.

## Testes

Sem CATIA:

```bat
python -m unittest discover -s tests
```

Com o CATIA aberto e sem desenhos importantes abertos, porque o teste fecha todos:

```bat
python tests\parity\rodar_paridade_font.py C:\Users\renan\Documents\E1DWGVBA
python tests\parity\rodar_paridade_flags.py
python tests\parity\rodar_paridade_update.py C:\Users\renan\Documents\E1DWGVBA
python tests\parity\rodar_paridade_splits.py
python tests\parity\rodar_paridade_poszone.py
```

As telas têm testes com cliques reais: `testar_tela_font.py`, `testar_tela_flags.py` e
`testar_tela_ferramentas.py`, que usam as pastas criadas pelos testes de paridade.

## Check de Template

Só lê. Não ativa folha, não seleciona e não escreve no desenho. `tests/parity/testar_check_template.py`
compara uma foto do desenho antes e depois.

- **Como acha os campos.** Pelo rótulo: `SCALE` e `SHEET / OF`, com o valor embaixo, na mesma célula. O
  nome dos textos não é usado. O número da folha também é procurado na Main View.
- **Numeração.** A primeira folha mostra `1/total`. As outras mostram só o próprio número. O parâmetro
  `No_of_Sheets`, se existir, precisa ser igual ao número de folhas.
- **Formato.** A etiqueta precisa bater com o papel. 3A0 e E3 são papel personalizado, sem medida de
  referência aqui: ficam em Conferir.
- **Escala.** O campo é comparado com as vistas da folha. Não contam as vistas com `ISOMETRIC`, `ISO`,
  `SECTION` ou `VIEW` no nome, nem as zonas. A exceção é `VIEW LOOKING` (FWD, AFT etc.), que conta.
  `PLAN VIEW` fica fora porque a escala dela não é garantida. Se todas baterem, Certo. Se nenhuma bater,
  Errado. Se só parte bater, Conferir.
- **Nome.** Não é conferido, a pedido.
- **Conferir.** É o que o programa não tem como afirmar: campo não achado, folha sem vista para comparar,
  escala que não é número (NTS). Não conta no selo da aba.
- **O que não foi testado.** Template real. O teste monta a legenda no arranjo das fotos, com as medidas
  estimadas pela régua da foto.

## Fix Flags: o que o teste cobre

- **Desenhos reais.** A macro e o Python rodam nos mesmos desenhos, duas vezes seguidas. Cada
  texto é fotografado depois: conteúdo, tipo da flag, cor e borda de cada letra, tamanho,
  posição, ângulo e leaders. O teste falha se o desenho não cobrir todos os tipos de flag.
- **Falhas sob encomenda.** O CATIA não falha quando se pede, e são esses caminhos que restauram
  o desenho. `tests/parity/texto_simulado.vbsinc` simula um texto com 19 tipos de falha, e a mesma
  definição roda no VBA e no script: 1000 casos. Defeitos plantados de propósito no script foram
  todos percebidos por essa simulação.
- **O que não foi testado.** Desenho real de produção. As flags do teste foram criadas por
  automação, não pela interface do CATIA. O VBA de referência roda pelo Excel, não dentro do CATIA.

## Fix Flags: fatos do CATIA V5R20 confirmados no teste

- `DrawingText.FrameType = x` aceita sem erro e não grava nada. Só `TextProperties.FrameType` grava.
- O índice das letras em `SetParameterOnSubString` começa em 1. A macro usa 0 ao aplicar a borda e
  ao validar letra por letra, então a última letra fica de fora. O Python usa 1.
- A borda por letra não aceita 57, 58 e 59: flag fixa com cadeado só existe no objeto inteiro.

## Fix Flags: diferenças conhecidas em relação ao VBA

- **Decisões do usuário (04/11/2026).** Flag já correta não é tocada: nem texto, nem frame, nem cor
  (item 6 de `vba_referencia/README.md`). Tirar um espaço externo de um código com 4 números conta
  como correção. Uma flag do Text Editor em só parte do texto agora é corrigida, em vez de falhar. A
  comparação aplica essas mudanças à macro de referência, e só elas, para provar que o resto é igual.
- **Melhorias.** Lista de cada flag, com o texto antes e depois e o resultado; navegação até ela
  no CATIA; barra de progresso; parada entre folhas; modo compacto. Depois de um erro, a tela
  mostra o que já tinha sido alterado, que no VBA só ficava no desenho.
- **Desenho trocado no meio.** O VBA guarda o documento; o Python procura pelo nome completo a
  cada folha e nunca segue para outro documento que tenha ficado ativo.
- **Janelas.** O resumo que o VBA mostrava numa mensagem agora fica na própria tela. A confirmação
  continua igual, com o Não como botão padrão. As mensagens ganharam os acentos.

- **Pedidos de 09/11/2026, no Python e em `vba/fixflags.txt`.** A flag não é mais pintada de verde nem de
  vermelho: o resultado fica só na tela. Texto com largura de quebra fixa não parte mais o código em duas
  linhas: depois da troca, a largura é ajustada ao texto, e a antiga volta se era maior. No HUB, clicar em
  Corrigir já corrige, sem janela de confirmação, e a navegação enquadra a flag junto com a ponta da seta.
  Texto com letras de cores misturadas fica com a cor da primeira letra ao ser regravado: é do CATIA.

## Font Size Check: diferenças conhecidas em relação ao VBA

- **Itens ocultos.** A macro antiga pintava os itens ocultos sem ninguém ver, e a macro do navegador
  os lista. O Python tira da lista os ocultos fora do padrão e informa quantos ignorou. Só esses
  são conferidos, um por um, porque conferir todos deixaria a leitura lenta em desenho grande.
- **Consulta ao CATIA.** O HUB lê o título da janela pelo Windows e só fala com o CATIA quando ele
  muda, para não atrapalhar o que estiver rodando lá, como a conexão do SmarTeam.
- **Item apagado ou renomeado.** O VBA guarda o objeto; o Python guarda o índice e o nome e
  procura de novo. Renomear um item depois da análise faz ele aparecer como não encontrado.
- **Zoom do navegador.** Mesma conta (8 vezes o zoom da folha inteira), mas o `Reframe` do
  CATIA muda conforme o estado da janela. Por isso o teste só compara a ordem de grandeza.
- **Empates exatos de arredondamento** (como 0,17055"). O `Round` do VBA no Excel e o do
  VBScript no CATIA discordam entre si em 12% desses casos. O Python segue o do CATIA. Em
  300 mil empates testados, só 4,34213, 4,92633 e 7,05993 mm mudam o resultado.
- **Melhorias.** Erro claro sem desenho ou com peça aberta, barra de progresso, parada entre
  folhas, lista também dos itens corretos e modo compacto.
- **Janela de pedido e aviso de fim.** O resumo que o VBA mostrava numa mensagem agora fica na
  própria tela. O painel VBA continua funcionando como antes.
- **Cotas.** Como no VBA, não são conferidas no V5R20, que não tem `DrawingDimValue.GetFontSize`.
- **Restaurar cores (`ResetColors`).** Convertido como está, mas nos testes o comando de busca
  falha nos dois lados, com o CATIA sem janela. Nenhum botão do painel chama essa rotina.

- **Pedidos de 09/11/2026.** Vista travada também é lida, no Python e em `vba/sizedetect.txt`: ler não altera
  nada. No Font Size Fix, a vista travada é destravada só na troca do tamanho e travada de novo, mesmo se a
  troca falhar. O botão de corrigir todos saiu. REMOVER ESTE TEXTO DA LISTA tira um item da lista, no Check
  e no Fix, sem alterar o desenho: ele volta na próxima análise. A Main View e o Background ficam fora da
  leitura, a pedido: só as vistas são conferidas. Notas soltas na Main View não são mais apontadas.

## Update Template: diferenças conhecidas em relação ao VBA

- **Template já aberto.** Depois de converter, o CATIA mantém o template carregado sem janela, porque
  o desenho convertido fica ligado a ele. Esse caso é normal: o `Documents.Open` volta a usá-lo e o
  `Close` só fecha a janela. Só é recusado o template aberto com janela, que a pessoa pode ter alterado.
  `doc.Saved` não serve para saber: no V5R20 ele é `True` até depois de mudar um parâmetro. O erro
  não diz que o desenho pode ter mudado, porque nesse ponto ele ainda não mudou.
- **Velocidade.** A tela não é redesenhada durante a conversão, só ao abrir o template, para uma
  janela do CATIA ou do SmarTeam não ficar invisível.
- **Confirmação do tamanho.** A tela mostra o tamanho detectado, com um botão para confirmar e outro
  para escolher manualmente.
- **Melhorias.** Progresso por folha na tela, lista das folhas e dos avisos no resultado, e o HUB
  continua respondendo. Não há botão de parar, porque o desenho ficaria parcialmente convertido.
- **Pasta dos templates fora do ar.** O Python mostra uma mensagem clara, com a pasta pesquisada.

- **Pedidos de 09/11/2026, no Python e em `vba/update.txt`.**
  - **Grade antiga.** Só eram apagadas as vistas `ZONE`, `ZONE[n]` e `ZONES_A1_SHT...`. As do desenho real se
    chamam `ZONE A0`, `ZONE A0[3]`, `ZONES_A0_SHT1`: a antiga ficava e a nova era colada por cima. Agora o
    nome com qualquer formato é reconhecido. Vista do usuário com ZONE no nome continua intacta.
  - **Margem.** Nas folhas 2 em diante, os números das colunas ganham a dezena da folha (29, 28, 27 na
    folha 2). São lidos uma vez no template. Só vale o número que aparece em cima e embaixo na mesma
    coluna, para um número solto da legenda nunca ser trocado.
  - **Grade.** Nas folhas 2 em diante, os rótulos das vistas de zona ganham a dezena (F6 vira F26, E005
    vira E025). A trava da vista é mantida.
  - **Tempo (10/11/2026, só no Python).** Medido no desenho de teste, 4 folhas e 2 templates: de 15,2 s para
    13,3 s na primeira conversão e 10,5 s nas seguintes. O resultado continua igual ao da macro.
    - A leitura dos vínculos e da margem do template fica guardada em
      `%APPDATA%\E1DWGTools\templates_lidos.json` e vale enquanto o arquivo do template tiver o mesmo
      tamanho e a mesma data. Sem ela, cada parâmetro do template é alterado e devolvido, um por um.
    - As vistas de zona do template são copiadas de uma vez, e não uma por uma: cada ida e volta entre
      as janelas do template e do desenho custa perto de meio segundo.
    - O que sobra é do CATIA: abrir e fechar o template, colar e atualizar a tela.
    - `%APPDATA%\E1DWGTools\update_tempos.txt` guarda quanto cada fase levou na última conversão. Não
      aparece na tela. Serve para achar a fase lenta no PC da empresa, que não foi medido.

## Position and Zone: diferenças conhecidas em relação ao VBA

- **Ordem.** O Excel só abre depois de ler o desenho, para não ficar aberto vazio se a leitura falhar.
- **Precisão.** As coordenadas chegam do CATIA como texto, com 15 dígitos. Só afetaria um empate
  exato entre duas zonas, que a comparação com a macro não encontrou.
- **Ordenação.** A planilha é ordenada pelo objeto `Sort` do Excel, porque `Range.Sort` por COM não
  recebe o parâmetro de cabeçalho. O resultado é o mesmo.
- **Melhorias.** Tabela e contagens também na tela, progresso por folha e mensagens com acentos.
- **A tabela agora fica no HUB.** Mapear não abre mais o Excel: ele só abre com o botão ABRIR NO
  EXCEL. `run_pos_zone` continua sendo o caminho da macro, usado no teste de paridade.
- **Part List dentro do HUB.** Porte de `ImportarDadosSAP`, `CompararPosicaoZona` e `LimparDadosSAP`
  (`vba_referencia/excel`), em `src/engine/part_list.py`. A leitura usa um Excel escondido, fechado no
  fim, e dá o mesmo resultado da macro (`rodar_paridade_part_list.py`). O desenho e o SAP aparecem
  lado a lado por posição, em vez de duas tabelas separadas.
- **De onde vem a zona.** Do balão sem sublinhado. O sublinhado só conta a quantidade. Um balão que
  também está sublinhado só dá a zona se a posição não tiver outro balão.
- **Diferente da macro, a pedido.** Com mais de uma zona, no desenho (`A005; A006`) ou no SAP, a posição
  fica verde se uma delas bater. A planilha deixava vermelho, porque comparava o texto inteiro com a
  primeira zona do SAP. Com isso, um balão fora do lugar não aparece se outro da mesma posição bater, e
  uma zona do SAP sem balão no desenho também não, desde que a quantidade total bata.
- **OK manual (novo).** Vale por posição e fica em `%APPDATA%\E1DWGTools\poszone_ok.json`, separado por
  desenho. Deixa de valer se a zona ou a quantidade mudarem, no desenho ou no SAP. Fica neste PC: não
  vai junto com o desenho para o PC de outra pessoa.
- **Margem conferida nos dois lados (17/11/2026, diferente da macro).** A grade vem dos números que
  aparecem em cima e embaixo e das letras que aparecem à esquerda e à direita, na mesma altura. Um
  número solto da legenda não quebra mais as colunas. Se a posição ou a escala lidas da Background
  View tiram a margem do lugar, vale a coordenada do texto como está. Com rótulo de um lado só, vale
  a regra da macro, mas a margem de cima ganha quando a de baixo vem mais curta.
- **Margem pela geometria (17/11/2026).** A grade sai dos pares da margem: a mesma letra nos dois
  lados, na mesma altura, e o mesmo número em cima e embaixo, na mesma coluna. Não depende mais do
  tamanho nem da orientação do papel lidos do CATIA. O papel só confere se a margem achada está dentro
  dele e ocupa quase toda a folha; se não ocupa, vale a coordenada do texto sem a posição e a escala
  da Background View. Um rótulo coberto de um lado (pela legenda) não tira a coluna da grade. A busca
  pela faixa da borda do papel ficou como reserva.
- **Nada fica sem zona em silêncio.** Callout cuja posição o CATIA não informa fica com zona N/A, em
  vez de cair no canto da folha. No fim do mapeamento, uma única mensagem lista vistas e callouts sem
  posição, folhas com balão e sem grade, folhas em que a zona saiu por um caminho de reserva e folhas
  com o mesmo nome.
- **Grade desenhada de todos os formatos.** `ZONE A0`, `ZONES_A0_SHT1`, `ZONE_E3_SHT1` etc. são
  reconhecidas, não só as do A1. Continuam sendo reserva: só valem se a margem não fechar.
- **Vista sem posição (erro "The method x failed").** O CATIA pode recusar a posição de uma vista.
  Ela não para mais o mapeamento: os callouts dela são contados, ficam com zona N/A e a tela avisa.
- **Arquivo de conferência.** Cada mapeamento grava `%APPDATA%\E1DWGTools\poszone_grade.txt`: de
  onde veio a grade de cada folha, a posição das colunas e linhas, a comparação com a grade desenhada
  e a posição de cada balão.
- **Desenho do VPM.** O nome vem sem extensão (`171-60466-803   1   1  --- CATDRAWING   1 ---`).
  `engine/documento.py` reconhece o desenho e tira o PN, para todas as ferramentas.
- **Mover o balão (novo, só no Design).** A zona vem do lugar do balão, então corrigir é mover. O balão
  vai para o ponto da zona pedida mais perto de onde está, com os textos encostados (flag, número,
  quantidade), e a tela avisa quais. A ponta do leader não sai do lugar. Lê de volta para conferir e
  tem DESFAZER. Se a posição já bate, não sugere mover os outros balões. Vista travada não move. O HUB não verifica se o novo lugar ficou em cima de outro
  desenho: quem confere é a pessoa, com o balão selecionado na tela.

## Fechar o HUB

Ao fechar, o HUB tira a seleção que deixou no CATIA e religa alertas, tela e interação. Depois de um
`ExecuteScript`, ler `RefreshDisplay` por fora do CATIA dá `False`, mas dentro de um script ele volta
`True`: o valor lido por fora não indica tela desligada.

Relato em aberto (05/11/2026): macros do CATIA travam depois de usar o HUB, mesmo com ele fechado. Não
se repetiu aqui, rodando uma macro por `ExecuteScript` antes e depois das mesmas chamadas. Clique em
botão de macro não foi testado aqui. `python verificar.py --catia` mostra o estado na hora do problema.

## Splits: diferenças conhecidas em relação ao VBA

- **Documento incompleto.** Depois de um erro, a cópia ou a peça incompleta não fica aberta, e os
  alertas e a tela do CATIA voltam ao normal. No Split 3D, a macro deixava os dois desligados.
- **Parar.** Dá para parar entre uma folha ou parte e a seguinte.
- **Vistas travadas no arquivo exportado (09/11/2026).** O Split 2D copia o arquivo do disco, então as
  travas aplicadas no desenho aberto não iam para os arquivos exportados. Agora cada arquivo é travado
  antes de salvar, no Python e em `vba/split2d.txt`. Alterações não salvas continuam fora, como na macro.
