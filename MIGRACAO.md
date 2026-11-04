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
| Font Size Check | `sizedetect.txt`, `frmFontNav.txt` do CONSERTO-E1DWGVBA | Convertido, em `main_qt.py` |
| Update Template | `update.txt` do CONSERTO-E1DWGVBA | Pendente, ver abaixo |
| Position and Zone | `vba_referencia/poszone` (V3.5.1) | Pendente |
| Fix Flags | `vba_referencia/fixflags` | Pendente |
| Split 2D e 3D | `vba_referencia/SPLIT 2D`, `SPLIT 3D` | Pendente |
| Painel | `vba_referencia/symbol shape` | Será substituído pelo HUB |
| Comparação no Excel | `vba_referencia/excel` | Continua no Excel |
| Symbol Shape | `CATMain11` não está em nenhum arquivo | Bloqueado |

### Versões em aberto

Dois arquivos do zip são mais antigos que os do CONSERTO-E1DWGVBA. Nada foi substituído até o
usuário decidir, para não haver downgrade:

- **`update`**: mesmo texto de `legacy_vba/UPDATETEMPLATE.bas` (14/10). O `update.txt` é de 23/10,
  tem 2513 linhas e troca o template no próprio desenho. `src/engine/update_template.py` também
  veio da versão de 14/10.
- **`sizedetect`**: ainda pinta o desenho e pede o formato no combobox. O `sizedetect.txt` de
  04/11 não pinta e lê o formato no Background. As regras de tamanho são iguais nos dois.

Os acentos das mensagens de `vba_referencia/poszone` viraram espaços ("n o foi encontrado").
Na conversão, as mensagens devem sair com os acentos certos do `poszone.txt`.

## Como cada ferramenta é convertida

1. O trabalho pesado vai para um script em `src/engine/catia_scripts`, que roda dentro
   do CATIA. A regra e as mensagens ficam em Python (`src/engine`).
2. Cada função de script embrulha a parte real com `On Error Resume Next` e devolve o erro
   como texto, para nunca abrir janela de erro no CATIA. Toda rotina auxiliar com
   `On Error Resume Next` termina com `Err.Clear`.
3. Um teste de paridade roda a macro atual e a versão Python nos mesmos desenhos e compara
   tudo o que o usuário veria.

## Testes

Sem CATIA:

```bat
python -m unittest discover -s tests
```

Com o CATIA aberto e sem desenhos importantes abertos, porque o teste fecha todos:

```bat
python tests\parity\rodar_paridade_font.py C:\Users\renan\Documents\E1DWGVBA
```

## Font Size Check: diferenças conhecidas em relação ao VBA

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
