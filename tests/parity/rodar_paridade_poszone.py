"""Compara o Position and Zone em Python com a macro em vba_referencia/poszone.

Compara a planilha gerada, celula por celula e com a formatacao, as mensagens, e prova que o
desenho nao mudou. Tambem compara as expressoes regulares com o VBScript.RegExp de verdade,
porque a macro usa esse motor e o Python usa outro.

Uso (com o CATIA aberto e sem desenhos importantes abertos, porque fecha todos):
    python tests/parity/rodar_paridade_poszone.py
"""
from __future__ import annotations

import os
import random
import re
import sys
import tempfile
import time

import pythoncom
import win32com.client as com

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.join(AQUI, "..", "..")
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.join(RAIZ, "src"))

import apoio  # noqa: E402
from engine import pos_zone as pz  # noqa: E402
from engine.catia_bridge import CAMPO, REGISTRO, CatiaBridge  # noqa: E402

SCRIPT = "montar_fixtures_poszone.catvbs"
EXTRA = r'''

Public Sub Rodar()
    PosZone.MapearCalloutsTodasAsFolhas1214
End Sub
'''


def preparar(destino: str, modelo: str, copia: str) -> None:
    fonte = apoio.trocar_janelas(apoio.ler_fonte(os.path.join(RAIZ, "vba_referencia", "poszone"))).replace("\r\n", "\n")
    de = '"\\\\SJKFS17\\Mezcal\\Projects\\OEM\\EMB170-190\\05. Quality\\09. Macros\\_Callouts.xlsm"'
    assert de in fonte
    fonte = fonte.replace(de, '"' + modelo + '"')
    # So no teste: guarda a planilha e fecha o Excel aberto pela macro. O Excel fica visivel nos dois
    # lados, para o tempo ser justo.
    a = "    RestaurarWorkingViewsPrimeiraFolha oDoc\n"
    assert a in fonte
    fonte = fonte.replace(a, f'    xlWB.SaveCopyAs "{copia}"\n    xlWB.Close False\n    xlApp.Quit\n' + a)
    fonte = fonte.replace("xlApp.DisplayAlerts = True", "xlApp.DisplayAlerts = False")
    fonte = re.sub(r"^.*frmE1Tools\.Show.*$", "", fonte, flags=re.M)
    # A macro foi salva com os acentos trocados por espacos; a comparacao ignora a diferenca.
    apoio.gravar_fonte(fonte, destino)


def criar_planilha(caminho: str) -> None:
    xl = com.DispatchEx("Excel.Application")
    xl.Visible = False
    xl.DisplayAlerts = False
    wb = xl.Workbooks.Add()
    ws = wb.Worksheets(1)
    ws.Name = "Dados_Callouts"
    ws.Range("A3:D3").Value = (("POSICAO", "ZONA", "QTD", "ONDE"),)
    ws.Range("A4:D6").Value = (("LIXO 1", "x", 1, "y"), ("LIXO 2", "x", 2, "y"), ("LIXO 3", "x", 3, "y"))
    ws.Range("A4:D6").Interior.Color = 255
    wb.SaveAs(caminho, FileFormat=52)
    wb.Close(False)
    xl.Quit()


def ler_planilha(xl, caminho: str) -> list:
    wb = xl.Workbooks.Open(caminho, False, True)
    ws = wb.Worksheets("Dados_Callouts")
    linhas = []
    ultima = ws.UsedRange.Rows.Count + ws.UsedRange.Row - 1
    for lin in range(1, ultima + 1):
        for col in range(1, 5):
            c = ws.Cells(lin, col)
            linhas.append((
                lin, col, c.Value, c.Font.Name, c.Font.Size, c.Font.Bold, c.Font.Color, c.HorizontalAlignment,
                c.Interior.Pattern, c.Borders.LineStyle, c.Borders.Color,
            ))
    larguras = [round(ws.Columns(i).ColumnWidth, 1) for i in range(1, 5)]
    wb.Close(False)
    return linhas + [("largura", larguras)]


def comparar_regex(n: int = 60000) -> int:
    """Os mesmos textos no VBScript.RegExp e no Python."""
    re_ref = com.Dispatch("VBScript.RegExp")
    re_ref.Pattern, re_ref.IgnoreCase, re_ref.Global = "(^|[^A-Z])REF([^A-Z]|$)", True, False
    re_a = com.Dispatch("VBScript.RegExp")
    re_a.Pattern, re_a.IgnoreCase, re_a.Global = r"\(?(\d+)\)?\s*X?\s*(PLCS|PLACES|PLS|PL|REQUIRED|REQ'D|REQD)([^A-Z]|$)", True, False
    re_d = com.Dispatch("VBScript.RegExp")
    re_d.Pattern, re_d.IgnoreCase, re_d.Global = r"(^|[^A-Z])(REQUIRED|REQ'D|REQD)\s*[:=]?\s*(\d+)", True, False

    def vb_qtd(s):
        try:
            if re_a.Test(s):
                v = int(re_a.Execute(s).Item(0).SubMatches.Item(0))
            elif re_d.Test(s):
                v = int(re_d.Execute(s).Item(0).SubMatches.Item(2))
            else:
                return 0
        except Exception:
            return 0
        return 0 if v > pz.MAIOR_LONG else v

    pedacos = ["REF", "ref", "PREF", "REFERENCE", "PL", "pl", "PLCS", "PLS", "PLACES", "PLATE", "APPLY", "REQD", "REQ'D", "REQUIRED",
               "req", "X", "x", " ", "  ", "\n", "\r\n", "\t", "\xa0", "(", ")", ":", "=", ",", ".", "-", "/", "0", "1", "2", "4", "12", "99",
               "007", "2147483648", "ITEM", "É", "ç", "SPLICE", "é"]
    rnd = random.Random(1214)
    difs = 0
    for _ in range(n):
        s = "".join(rnd.choice(pedacos) for _ in range(rnd.randint(0, 7)))
        ref, qtd = bool(re_ref.Test(s)), vb_qtd(s)
        if pz.has_ref(s) != ref or pz.extract_quantity(s) != qtd:
            difs += 1
            if difs <= 8:
                print(f"  regex diferente em {s!r}: VBScript REF={ref} QTD={qtd} | Python REF={pz.has_ref(s)} QTD={pz.extract_quantity(s)}")
    print(f"[{'DIFERENTE' if difs else 'IGUAL'}] expressoes regulares: {n} textos, {difs} diferencas", flush=True)
    return 1 if difs else 0


def foto(bridge) -> str:
    r = bridge.app.SystemService.ExecuteScript(os.path.join(AQUI), 1, "sonda_update.catvbs", "Foto", [])
    return re.sub(r"ccp_dummy\d+", "ccp_dummy", r)


def abrir(bridge, caminho) -> None:
    bridge.app.SystemService.ExecuteScript(AQUI, 1, SCRIPT, "Fechar", [])
    if caminho:
        bridge.app.Documents.Open(caminho)


def vba_uma(xl, trabalho) -> list:
    saida = os.path.join(trabalho, "saida.txt")
    if os.path.exists(saida):
        os.remove(saida)
    xl.Run("Preparar", "", saida)
    xl.Run("Rodar")
    if not os.path.exists(saida):
        return []
    with open(saida, encoding="cp1252") as f:
        return f.read().splitlines()


def normaliza_msg(l: str) -> str:
    # A macro do zip trocou cada letra acentuada por um espaco. Tira as acentuadas de um lado e os
    # espacos dos dois: "concluído" e "conclu do" viram "concludo".
    return re.sub(r"[^A-Za-z0-9<>:/.\-_\\]", "", l.split(CAMPO)[-1])


def caso(xl, bridge, trabalho, xl_leitor, nome, caminho, modelo, copia_vba, exigir=None, listar=True) -> int:
    abrir(bridge, caminho)
    documento = caminho and caminho.lower().endswith(".catdrawing")
    antes = foto(bridge) if documento else ""
    t0 = time.perf_counter()
    m_vba = vba_uma(xl, trabalho)
    t_vba = time.perf_counter() - t0
    f_vba = foto(bridge) if documento else ""

    abrir(bridge, caminho)
    if documento:
        foto(bridge)
    linhas = []
    t0 = time.perf_counter()
    rep = pz.run_pos_zone(bridge, lambda m, t: linhas.append(CAMPO.join(["MSG", t, apoio.plano(m)])), template=modelo, pasta_saida=trabalho + "\\")
    t_py = time.perf_counter() - t0
    copia_py = ""
    if rep is not None:
        linhas.append(CAMPO.join(["MSG", "Sucesso", apoio.plano(rep.mensagem)]))
        copia_py = os.path.join(trabalho, "copia_py.xlsm")
        if os.path.exists(copia_py):
            os.remove(copia_py)
        rep.xl_book.SaveCopyAs(copia_py)
        rep.xl_book.Close(False)
        rep.xl_app.Quit()
        rep.xl_book = rep.xl_app = None
    f_py = foto(bridge) if documento else ""

    falha = 0
    a, b = [normaliza_msg(l) for l in m_vba], [normaliza_msg(l) for l in linhas]
    if a != b:
        falha = 1
        print(f"  mensagens:\n    VBA: {m_vba}\n    PY : {linhas}")
    if documento:
        if f_vba != f_py:
            falha = 1
            print("  o desenho ficou diferente entre os dois lados")
        # A vista e a folha ativas mudam de proposito: a macro volta para a primeira folha.
        conteudo = lambda f: [x for x in f.split(REGISTRO) if x.split(CAMPO)[0] not in ("DOC", "ABERTOS", "FOLHA")]  # noqa: E731
        if conteudo(f_py) != conteudo(antes):
            falha = 1
            print("  o desenho mudou, e esta ferramenta so le")
    if rep is not None:
        p_vba = ler_planilha(xl_leitor, copia_vba)
        p_py = ler_planilha(xl_leitor, copia_py)
        difs = [(x, y) for x, y in zip(p_vba, p_py) if x != y]
        if difs or len(p_vba) != len(p_py):
            falha = 1
            print(f"  planilha diferente: {len(difs)} celulas, {len(p_vba)} x {len(p_py)}")
            for x, y in difs[:25]:
                print(f"    VBA: {x}\n    PY : {y}")
        for campo, minimo in (exigir or {}).items():
            if getattr(rep.counters, campo) < minimo:
                falha = 1
                print(f"  o desenho de teste nao cobriu {campo}: {getattr(rep.counters, campo)} < {minimo}")
        print("   ", apoio.plano(rep.mensagem).replace("<CRLF>", " | "))
        for c in rep.callouts if listar else []:
            print(f"      {c.number:>6} | {c.zone:24} | {c.qty:>3} | {c.sheet} - {c.view}")
    print(f"[{'DIFERENTE' if falha else 'IGUAL'}] {nome}: VBA {t_vba:.1f} s, Python {t_py:.2f} s", flush=True)
    return falha


def main() -> int:
    trabalho = tempfile.mkdtemp(prefix="paridade_poszone_")
    pythoncom.CoInitialize()
    falhas = comparar_regex()
    bridge = CatiaBridge()
    r = bridge.app.SystemService.ExecuteScript(AQUI, 1, SCRIPT, "Montar", [trabalho])
    print("Desenhos de teste:", r, trabalho, flush=True)
    if not r.startswith("OK"):
        return 1
    modelo = os.path.join(trabalho, "_Callouts.xlsm")
    criar_planilha(modelo)
    copia_vba = os.path.join(trabalho, "copia_vba.xlsm")
    fonte = os.path.join(trabalho, "poszone_teste.txt")
    preparar(fonte, modelo, copia_vba)
    xl, wb = apoio.abrir_excel({"PosZone": fonte}, extra=EXTRA)
    relogio = apoio.vigia(xl, 1500)
    leitor = com.DispatchEx("Excel.Application")
    leitor.Visible = False
    leitor.DisplayAlerts = False
    arq = lambda n: os.path.join(trabalho, n)  # noqa: E731
    try:
        falhas += caso(xl, bridge, trabalho, leitor, "sem documento", None, modelo, copia_vba)
        falhas += caso(xl, bridge, trabalho, leitor, "peca aberta", arq("NAO_E_DESENHO.CATPart"), modelo, copia_vba)
        falhas += caso(xl, bridge, trabalho, leitor, "todos os casos", arq("POS_RICO.CATDrawing"), modelo, copia_vba,
                       {"validos": 40, "grupo": 1, "conflito": 1, "referencias": 2, "multilinha": 3, "chaves": 2})
        falhas += caso(xl, bridge, trabalho, leitor, "sem nenhum callout", arq("POS_VAZIO.CATDrawing"), modelo, copia_vba)
        falhas += caso(xl, bridge, trabalho, leitor, "desenho grande, 3000 baloes", arq("POS_GRANDE.CATDrawing"), modelo, copia_vba, listar=False)
        bridge.app.SystemService.ExecuteScript(AQUI, 1, SCRIPT, "Fechar", [])
    finally:
        relogio.cancel()
        wb.Close(False)
        xl.Quit()
        leitor.Quit()
    print("RESULTADO:", "TUDO IGUAL" if not falhas else f"{falhas} COM DIFERENCA")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
