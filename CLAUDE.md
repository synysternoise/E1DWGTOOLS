# E1DWGTOOLS: contexto para quem continuar o projeto

Você está assumindo um projeto em andamento. Leia este arquivo inteiro antes de mexer em qualquer coisa.
Ele descreve o que o programa é, como o código está organizado, as regras da casa e o estado em
17/11/2026, incluindo o que foi alterado e ainda não foi testado no CATIA.

## O que é

HUB em Python (PySide6) que automatiza desenhos 2D (CATDrawing) no CATIA V5, na Embraer, programa
E1 (EMB170-190). É o porte de macros VBA para Python, ferramenta por ferramenta. O dono do projeto é
projetista, não programador: usa o programa no PC da empresa, onde o CATIA abre desenhos do disco e
do ENOVIA VPM, e tem em casa um PC com um CATIA de teste.

O programa abre por `python main_qt.py`, com o CATIA aberto. `main.py`, `src/ui/`, `src/tools/` e
`src/engine/update_template.py` são da interface antiga e não fazem parte da migração. O `README.md`
ainda descreve a interface antiga. A referência atual é o `MIGRACAO.md`.

## Como o código está organizado

| Lugar | Papel |
|---|---|
| `src/engine/catia_bridge.py` | Ponte com o CATIA. Roda uma função de um script dentro do CATIA e recebe uma string só. |
| `src/engine/catia_scripts/*.catvbs` | O que roda dentro do CATIA (VBScript). Só lê, salvo onde o nome diz o contrário. |
| `src/engine/*.py` | As regras de cada ferramenta, testáveis sem o CATIA. |
| `src/ui_qt/` | As telas. `hub_window.py` é a janela, `catia_worker.py` é a thread que fala com o CATIA. |
| `src/engine/documento.py` | Diz se o documento ativo é um desenho e qual é o PN, pelo nome. |
| `vba/` | O VBA mais novo de cada ferramenta. `vba_referencia/` é a base original, sem alteração. `legacy_vba/` está desatualizada. |
| `tests/` | Testes de lógica, sem CATIA. `tests/parity/` precisa do CATIA aberto. |
| `verificar.py` | Confere a instalação no PC do usuário, arquivo por arquivo. |

Protocolo dos scripts: a resposta é uma lista de registros separados por `Chr(30)`, com campos
separados por `Chr(31)`. O primeiro registro é `OK` ou `ERR`, número e descrição. Um erro dentro do
script vira `CatiaError` no Python, com a descrição do CATIA como mensagem.

Ferramentas: Update Template, Fix Flags, Check de Flags, Font Size Check e Fix, Position and Zone
(Check) e Pos and Zone Fix (Design), Check de Template, Symbol Shape, Split 2D e 3D, Compare DWG.

## Regras da casa

- **Idioma.** Tudo em português: código, comentários, mensagens de tela, commits. Comentários e nomes
  no código sem acento; mensagens que o usuário lê, com acento.
- **Paridade com o VBA.** Cada ferramenta precisa funcionar igual ou melhor que a macro. Toda diferença
  proposital entra no `MIGRACAO.md`, na seção da ferramenta.
- **Manifesto.** `verificar.py` guarda linhas e assinatura de cada arquivo. Depois de alterar qualquer
  arquivo listado, rode `python verificar.py --manifesto` e cole a saída no bloco `MANIFESTO`. Arquivo
  novo em `src/` entra na lista, e o total em `tests/test_verificar.py` sobe junto.
- **Macros base.** `tests/versoes_base.json` trava a impressão digital das macros convertidas. Se uma
  macro mudar, o teste falha até a mudança ir para o Python.
- **Nada de suposição sobre o CATIA.** O que não dá para confirmar lendo o código ou rodando no CATIA
  é hipótese, e deve ser dito como hipótese. O usuário pede diagnóstico com arquivo, função e linha
  antes de qualquer edição.
- **Desenho do usuário.** Leitura não altera o desenho. O que altera avisa na tela e tem desfazer ou
  restauração.
- **Commits.** Uma linha de título dizendo o que mudou para quem usa, e o porquê no corpo.

## Como testar

Sem CATIA, no Windows:

```bat
python -m unittest discover -s tests
```

Fora do Windows os módulos `pythoncom`, `pywintypes` e `win32com` não existem. Para rodar a lógica,
registre módulos vazios com esses nomes em `sys.modules` (e `pywintypes.com_error`) antes de carregar
os testes. Nesse caso sobram 2 erros de caminho com `\` em `test_pos_zone_logic.Template`, que são do
ambiente e não do código.

Com o CATIA aberto e sem desenhos importantes, porque os testes fecham tudo: os scripts de
`tests/parity/`, listados no `MIGRACAO.md`.

## Position and Zone: como funciona

1. `pos_zone.catvbs` lê folhas, vistas, textos e linhas 2D.
2. `pos_zone.py` monta a grade de zonas de cada folha (`map_zones_source`):
   - primeiro pela margem (`border_zones`): números e letras da Background View;
   - se a margem não fechar, pela grade desenhada (`zones_from_aux_view`): vistas `ZONE`, `ZONE A0`,
     `ZONES_A0_SHT1`, `ZONE_E3_SHT1` e parecidas.
3. A zona de um balão é a do centro de zona mais próximo (`nearest_zone`). A posição do balão na folha
   é `vista.x + texto.x * escala`, com a rotação da vista (`ViewRead.to_sheet`). É a mesma conta do
   zoom em `font_check.catvbs`, que o usuário confirma que centraliza certo.
4. Classificação, REF, quantidades (aglomerado, chave, mesma linha) e consolidação por posição.
5. A tela compara com o Part List do SAP (`part_list.py`), guarda o OK manual e, no Fix, move o balão.

Formatos de folha e grade, lidos dos templates `E1_DRW_TEMPLATE_<formato>_R00.CATDrawing`:

| Formato | Colunas × linhas | Vista de zonas |
|---|---|---|
| 3A0 | 9 × 6 (A–F) | não confirmada |
| A0 | 9 × 6 | `ZONES_A0_SHT1`… |
| A1 | 6 × 4 (A–D) | `ZONES_A1_SHT1`… |
| A2 | 4 × 3 (A–C) | `ZONES_A2_SHT1`… |
| A3 | 3 × 2 (A–B) | `ZONES_A3_SHT1`… |
| E3 | 9 × 6 | `ZONE_E3_SHT1`, o mesmo nome em todas as folhas |

As colunas são numeradas da direita para a esquerda e as linhas de baixo para cima. Nas folhas 2 em
diante a coluna ganha a dezena da folha (C004 vira C024). Não existe tabela de medidas da moldura no
código: a grade sai dos rótulos de cada folha.

## O que foi feito em 17/11/2026

Três problemas relatados pelo usuário, com fotos da tela. Tudo está no branch `ccr-4531aaf5-wxvlh3`,
em três commits sobre `migracao-dwgtools`.

1. **Desenho aberto pelo VPM não era reconhecido.** O HUB decidia pelo final `.catdrawing` do nome, e
   pelo VPM o nome vem como `171-60466-803      1       1  --- CATDRAWING     1 ---`. Agora todas as
   ferramentas usam `eh_desenho` e `pn_do_documento` de `engine/documento.py`. O Split 2D continua
   pedindo o arquivo salvo, e o Split 3D não mudou.
2. **`The method x failed` num desenho 3A0 (171-60895-401).** A posição de cada vista era lida sem
   proteção em `LerFolha_`, e uma vista recusada pelo CATIA derrubava o mapeamento. Agora `LerPosicao`
   protege a leitura, o registro `V` ganhou o campo "posição lida", os callouts da vista ficam com
   zona `N/A` e a tela avisa folha e vista. Mover balão recusa essa vista.
3. **Zona errada num A1 (171-50964-401).** O balão na C004 saía como C003 e o da B002 como C001.
   Provado: a posição do balão está certa, o erro está na grade. Não provado: qual leitura veio
   errada. O que mudou na margem:
   - vale o número que aparece em cima e embaixo e a letra que aparece nos dois lados, para um número
     da legenda não quebrar as colunas;
   - se a posição ou a escala lidas da Background View tiram a margem do lugar, vale a coordenada do
     texto como está;
   - com rótulo de um lado só, vale a regra da macro, mas a margem de cima ganha quando a de baixo vem
     mais curta;
   - a grade desenhada de todos os formatos é reconhecida, como reserva.
4. **Margem pela geometria e avisos (varredura do Position and Zone).** A grade sai dos pares de
   rótulos da margem, sem depender do tamanho do papel (`_geometry_grid`); a faixa da borda virou
   reserva. Callout sem posição fica N/A e um aviso único lista tudo o que pode ter deixado zona
   errada ou vazia (`aviso_mapeamento`). Mover e navegar não travam a tela com erro inesperado.
5. **Arquivo de conferência.** Cada mapeamento grava `%APPDATA%\E1DWGTools\poszone_grade.txt`: origem
   da grade de cada folha, posição das colunas e linhas, comparação com a grade desenhada e posição e
   zona de cada balão.
6. **Update Template no E3.** `ZONE_E3_SHT1` passou a ser reconhecida como grade antiga, para ser
   apagada e numerada como as outras.

## O que falta, em ordem

1. **Testar no CATIA.** Nada do que está acima rodou num CATIA de verdade. A sessão que fez as
   mudanças rodava na nuvem, sem Windows, e o PC do usuário não aceitou a conexão. Roteiro:
   - 171-60895-401 (3A0): deve mapear até o fim e avisar a vista sem posição;
   - 171-50964-401 (A1): os balões 1 e 2 devem sair em C004 e B002;
   - um desenho aberto pelo VPM: a ferramenta deve liberar e o PN deve ser só o número.
   Os dois PNs e o VPM só existem no PC da empresa. No PC de casa dá para validar com desenhos
   montados pelos scripts de `tests/parity/`.
2. **Fechar a causa da zona do A1.** Se os balões ainda saírem errados, o `poszone_grade.txt` desse
   desenho mostra a origem da grade e os números lidos. A hipótese da escala da Background View
   precisa ser confirmada ou descartada com esse arquivo.
3. **Descobrir por que o CATIA recusa a posição de uma vista** no 171-60895-401. O aviso novo dá o
   nome da vista.
4. **Confirmar o nome do documento no VPM.** Supõe-se que `ActiveDocument.Name` é o texto do título
   da janela. O chip do documento no HUB mostra o valor real.
5. **VBA fora de sincronia.** `vba/poszone.txt` e `vba/update.txt` não receberam as mudanças de
   margem, de vista sem posição nem do nome do E3. O teste de paridade do Position and Zone pode
   acusar diferença nos casos em que a margem antiga errava.
6. **Ideia em aberto, não aprovada.** Calcular a zona pela quina da folha, com uma tabela de medidas
   da moldura por formato, sem depender de rótulo nem de grade. O usuário preferiu manter a leitura
   da margem, desde que ela fique confiável. Volta à mesa se a margem continuar errando.
7. **Levar o branch para `migracao-dwgtools`,** que é de onde o usuário baixa o código e para onde o
   `verificar.py` aponta.

## Como falar com o usuário

Em português, direto, sem jargão de programação. Diga o que foi feito, o que não foi testado e o que
ele precisa fazer. Quando não souber a causa de algo, diga que não sabe e o que falta para saber.
