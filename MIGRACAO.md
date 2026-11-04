# Migração do VBA para Python

Regra: cada ferramenta precisa funcionar igual ou melhor que o VBA, sem perder nada.
O VBA continua em uso até a versão Python passar pela comparação.

## De onde vem o código

A versão de referência de cada macro é a do repositório **CONSERTO-E1DWGVBA**.
A pasta `legacy_vba/` deste repositório está **desatualizada** e não serve de base.
O Update Template atual em `src/engine/update_template.py` também é antigo: foi portado
da versão de 14/10 e precisa ser refeito a partir de `update.txt`.

`tests/versoes_base.json` guarda a impressão digital de cada macro usada como base.
`tests/test_versoes_base.py` falha se uma macro já convertida mudar depois da conversão.

| Ferramenta | Arquivos de base | Situação |
|---|---|---|
| Font Size Check | `sizedetect.txt`, `frmFontNav.txt` | Convertido, em `main_qt.py` |
| Update Template | `update.txt` | Pendente |
| Position and Zone | `poszone.txt` | Pendente |
| Painel | `fixflags.txt` | Será substituído pelo HUB |
| Comparação no Excel | `legacy_vba/excel.txt` | Continua no Excel |
| Fix Flags, Symbol Shape, Split | Código não disponível | Bloqueado |

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
