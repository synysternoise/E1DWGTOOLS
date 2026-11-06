"""Compara a importacao e a comparacao com o Part List com a macro de verdade (vba_referencia/excel).

Monta um Part List com os casos dificeis, roda ImportarDadosSAP e LimparDadosSAP num Excel escondido e
compara com o Python: a tabela importada, e a cor de cada celula do desenho e do SAP, verde ou vermelha.

Uso: python tests/parity/rodar_paridade_part_list.py (nao precisa do CATIA)
"""
from __future__ import annotations

import os
import re
import sys
import tempfile
from types import SimpleNamespace as NS

import pythoncom
import win32com.client as com

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.join(AQUI, "..", "..")
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.join(RAIZ, "src"))

import apoio  # noqa: E402
from engine import part_list as pl  # noqa: E402

VERDE = 198 + 239 * 256 + 206 * 65536
VERMELHO = 255 + 199 * 256 + 206 * 65536

# Posicao, zona, quantidade no desenho.
DESENHO = [
    (10, "A001", 2),        # tudo certo
    (11, "A002", 2),        # zona errada
    (12, "A003", 5),        # quantidade errada
    (13, "A004", 1),        # nao esta no SAP
    (14, "A005; A006", 2),  # duas zonas no desenho
    (15, "", 1),            # sublinhado, sem zona
    (16, "A007", 5),        # duas linhas no SAP, a soma bate
    (17, "A008", 3),        # duas efetividades: vale a maior
    (18, "A009", 4),        # dois arquivos: soma
    (19, "A-010", 1),       # zona com traco
    (20, "B001", 1),        # posicao com zeros a esquerda no SAP
    (21, "B002", 2),        # quantidade quebrada
]

# Diferenca pedida: com duas zonas, basta uma bater. A macro deixa essa posicao vermelha.
POSICAO_DIFERENTE = "14"

# PN, posicao, zona, programa, SN inicial, SN final, quantidade.
ARQUIVO_1 = [
    ("PN10", "10", "A001", "0170", "1", "9", 2),
    ("PN11", "11", "A099", "0170", "1", "9", 2),
    ("PN12", "12", "A003", "0170", "1", "9", 4),
    ("PN14", "14", "A005", "0170", "1", "9", 1),
    ("PN14", "14", "A006", "0170", "1", "9", 1),
    ("PN16", "16", "A007", "0170", "1", "9", 2),
    ("PN16", "16", "A007", "0170", "1", "9", 3),
    ("PN17", "17", "A008", "0170", "1", "9", 3),
    ("PN17", "17", "A008", "0190", "1", "9", 2),
    ("PN18", "18", "A009", "0170", "1", "9", 1),
    ("PN19", "19", "A010", "0170", "1", "9", 1),
    ("PN20", "0020", "B001", "0170", "1", "9", 1),
    ("PN21", "21", "B002", "0170", "1", "9", 1.5),
    ("PN22", "22", "C001", "0170", "1", "9", 7),   # so no SAP
    ("PN23", "ABC", "C002", "0170", "1", "9", 1),  # posicao de texto, so no SAP
    ("PN24", "", "C003", "0170", "1", "9", 1),     # sem posicao: nao conta
    ("PN25", "25", "C004", "0170", "1", "9", "x"),  # quantidade que nao e numero vira zero
]
ARQUIVO_2 = [
    ("PN18", "18", "A009", "0170", "1", "9", 3),
    ("PN26", "26", "C005", "0170", "1", "9", 1),
]

EXTRA = r'''

Public Function ArquivosTeste(Optional ByVal novo As Variant) As Variant
    Static guardado As Variant
    If Not IsMissing(novo) Then guardado = novo
    ArquivosTeste = guardado
End Function

Public Sub Rodar(ByVal a As String, ByVal b As String)
    If Len(b) > 0 Then ArquivosTeste Array(a, b) Else ArquivosTeste Array(a)
    Macro.ImportarDadosSAP
End Sub

Public Sub Limpar()
    Macro.LimparDadosSAP
End Sub
'''


def criar_sap(xl, caminho: str, linhas: list, aba: str, inteiro=True) -> None:
    wb = xl.Workbooks.Add()
    ws = wb.Worksheets(1)
    ws.Name = aba
    for i, (pn, pos, zona, prog, sn1, sn2, qtd) in enumerate(linhas, pl.PRIMEIRA_LINHA_SAP):
        ws.Cells(i, pl.COL_PN).Value = pn
        # Posicao como texto, para guardar os zeros a esquerda, como vem do SAP.
        c = ws.Cells(i, pl.COL_POSICAO)
        c.NumberFormat = "@"
        c.Value = pos
        ws.Cells(i, pl.COL_ZONA).Value = zona
        ws.Cells(i, pl.COL_PROGRAMA).Value = prog
        ws.Cells(i, pl.COL_SN_INICIAL).Value = sn1
        ws.Cells(i, pl.COL_SN_FINAL).Value = sn2
        ws.Cells(i, pl.COL_QUANTIDADE).Value = qtd
    wb.SaveAs(caminho, FileFormat=51)
    wb.Close(False)


def preparar_macro(destino: str) -> None:
    fonte = apoio.trocar_janelas(apoio.ler_fonte(os.path.join(RAIZ, "vba_referencia", "excel"))).replace("\r\n", "\n")
    # A janela de escolher arquivos vira os arquivos do teste.
    fonte, n = re.subn(r"arquivosSelecionados = Application\.GetOpenFilename\(.*?MultiSelect:=True\)", "arquivosSelecionados = Janelas.ArquivosTeste()", fonte, flags=re.S)
    assert n == 1
    apoio.gravar_fonte(fonte, destino)


def resultado_cor(c) -> bool:
    cor = c.Interior.Color
    assert cor in (VERDE, VERMELHO), (c.Address, cor)
    return cor == VERDE


def main() -> int:
    pythoncom.CoInitialize()
    trabalho = tempfile.mkdtemp(prefix="paridade_partlist_")
    falhas = 0
    leitor = com.DispatchEx("Excel.Application")
    leitor.Visible = False
    leitor.DisplayAlerts = False
    a1, a2, a3 = (os.path.join(trabalho, n) for n in ("sap1.xlsx", "sap2.xlsx", "sap_psa.xlsx"))
    criar_sap(leitor, a1, ARQUIVO_1, "COMPONENT")
    criar_sap(leitor, a2, ARQUIVO_2, "COMPONENT")
    criar_sap(leitor, a3, ARQUIVO_2, "PSA")
    leitor.Quit()

    fonte = os.path.join(trabalho, "macro.txt")
    preparar_macro(fonte)
    xl, wb = apoio.abrir_excel({"Macro": fonte}, referencias=(), extra=EXTRA)
    relogio = apoio.vigia(xl, 300)
    try:
        ws = wb.Worksheets(1)
        ws.Name = "Dados_Callouts"
        ws.Cells(3, 18).Value = "PN"
        ws.Cells(3, 19).Value = "POS"
        ws.Cells(3, 20).Value = "ZONA"
        ws.Cells(3, 21).Value = "QTD"
        for i, (p, z, q) in enumerate(DESENHO, 4):
            ws.Cells(i, 1).Value = p
            ws.Cells(i, 2).Value = z
            ws.Cells(i, 3).Value = q
        # ThisWorkbook da macro e este arquivo, porque o modulo esta nele.
        saida = os.path.join(trabalho, "saida.txt")
        for nome, arquivos in (("dois arquivos", (a1, a2)), ("um arquivo", (a1, "")), ("aba PSA", (a3, ""))):
            if os.path.exists(saida):
                os.remove(saida)
            xl.Run("Preparar", "", saida)
            xl.Run("Rodar", *arquivos)
            with open(saida, encoding="cp1252") as f:
                msg = f.read()
            ult = ws.Cells(ws.Rows.Count, 19).End(pl.XL_UP).Row
            macro_tabela = [
                (str(ws.Cells(i, 18).Value), str(ws.Cells(i, 19).Value), str(ws.Cells(i, 20).Value), float(ws.Cells(i, 21).Value))
                for i in range(4, ult + 1)
            ]
            macro_sap = [(resultado_cor(ws.Cells(i, 19)), resultado_cor(ws.Cells(i, 20)), resultado_cor(ws.Cells(i, 21))) for i in range(4, ult + 1)]
            macro_pn = [resultado_cor(ws.Cells(i, 18)) for i in range(4, ult + 1)]
            macro_des = [(resultado_cor(ws.Cells(i, 1)), resultado_cor(ws.Cells(i, 2)), resultado_cor(ws.Cells(i, 3))) for i in range(4, 4 + len(DESENHO))]

            parte = pl.ler_part_list([a for a in arquivos if a])
            py_tabela = [(r.pn, r.posicao, r.zona, r.quantidade) for r in parte.registros]
            callouts = [NS(number=str(p), zone=z, qty=q) for p, z, q in DESENHO]
            comp = pl.comparar(callouts, parte.registros)
            py_des = [(lambda r: (r.posicao, r.zona, r.quantidade))(comp.desenho[pl.normalizar_posicao(p)]) for p, _, _ in DESENHO]
            py_sap = [(r.posicao, r.zona, r.quantidade) for r in comp.sap]

            dif = 0
            if macro_tabela != py_tabela:
                dif += 1
                print(f"  tabela diferente:\n   VBA {macro_tabela}\n   PY  {py_tabela}")
            # O resto tem de continuar igual. A posicao diferente e conferida a parte, nos dois lados.
            des_iguais = [str(d[0]) != POSICAO_DIFERENTE for d in DESENHO]
            sap_iguais = [t[1] != POSICAO_DIFERENTE for t in macro_tabela]
            so_iguais = lambda valores, filtro: [v for v, f in zip(valores, filtro) if f]  # noqa: E731
            if so_iguais(macro_des, des_iguais) != so_iguais(py_des, des_iguais):
                dif += 1
                print(f"  cores do desenho:\n   VBA {macro_des}\n   PY  {py_des}")
            if so_iguais(macro_sap, sap_iguais) != so_iguais(py_sap, sap_iguais):
                dif += 1
                print(f"  cores do SAP:\n   VBA {macro_sap}\n   PY  {py_sap}")
            if so_iguais(macro_pn, sap_iguais) != [x[0] for x in so_iguais(py_sap, sap_iguais)]:
                dif += 1
                print(f"  PN acompanha a posicao:\n   VBA {macro_pn}")
            if nome != "aba PSA":  # esse arquivo nao tem a posicao 14
                i_des = des_iguais.index(False)
                if macro_des[i_des][1] or not py_des[i_des][1]:
                    dif += 1
                    print(f"  posicao {POSICAO_DIFERENTE}: esperava macro vermelha e Python verde. VBA {macro_des[i_des]}, PY {py_des[i_des]}")
            m = re.search(r"Linhas v.lidas lidas: (\d+).*?Registros consolidados: (\d+)", msg.replace("<CRLF>", " "))
            if not m or (int(m.group(1)), int(m.group(2))) != (parte.linhas_lidas, len(parte.registros)):
                dif += 1
                print(f"  contagens: macro {m.groups() if m else msg!r}, Python {parte.linhas_lidas}, {len(parte.registros)}")
            print(f"[{'DIFERENTE' if dif else 'IGUAL'}] {nome}: {len(py_tabela)} registros, {sum(all(x) for x in py_des)} de {len(py_des)} callouts batem", flush=True)
            falhas += dif

        # Clean SAP: o Python so esquece o Part List; aqui confere que a macro mantem o desenho.
        xl.Run("Limpar")
        if ws.Cells(4, 19).Value is not None or ws.Cells(4, 1).Value != DESENHO[0][0]:
            falhas += 1
            print("  Clean SAP da macro nao fez o esperado")
    finally:
        relogio.cancel()
        wb.Close(False)
        xl.Quit()

    # Erros, com a mesma mensagem da macro.
    vazio = os.path.join(trabalho, "sem_aba.xlsx")
    sem_linhas = os.path.join(trabalho, "sem_linhas.xlsx")
    leitor = com.DispatchEx("Excel.Application")
    leitor.Visible = False
    leitor.DisplayAlerts = False
    criar_sap(leitor, vazio, ARQUIVO_2, "OUTRA")
    criar_sap(leitor, sem_linhas, [], "COMPONENT")
    leitor.Quit()
    for caminho, esperado in ((vazio, "não foram encontradas"), (sem_linhas, "Nenhum registro foi encontrado")):
        try:
            pl.ler_part_list([caminho])
            falhas += 1
            print("  devia recusar", caminho)
        except pl.PartListError as exc:
            if esperado not in str(exc):
                falhas += 1
                print("  mensagem errada:", exc)
    try:
        pl.ler_part_list([a1, a2, a3])
        falhas += 1
        print("  devia recusar 3 arquivos")
    except pl.PartListError as exc:
        if "máximo dois" not in str(exc):
            falhas += 1
    print("RESULTADO:", "TUDO IGUAL" if not falhas else f"{falhas} COM DIFERENCA", flush=True)
    return 1 if falhas else 0


if __name__ == "__main__":
    codigo = main()
    sys.stdout.flush()
    os._exit(codigo)
