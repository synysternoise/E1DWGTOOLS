"""Compara o Font Size Check em Python com o VBA de verdade.

Roda a macro atual (sizedetect.txt) no Excel, nos mesmos desenhos, e grava tudo o
que ela mostra: mensagens, lista de itens e o estado da tela a cada item do
navegador. Depois faz o mesmo em Python e compara linha por linha.

Uso (com o CATIA aberto e sem desenhos importantes abertos, porque fecha todos):
    python tests/parity/rodar_paridade_font.py <pasta do E1DWGVBA> [desenho extra ...]
"""
from __future__ import annotations

import os
import sys
import tempfile
import time

import win32com.client as com

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "..", "src"))

from engine import font_check as fc  # noqa: E402
from engine.catia_bridge import CAMPO, CatiaBridge, CatiaError  # noqa: E402

TLBS = r"C:\Program Files (x86)\Dassault Systemes\B20\intel_a\code\bin"
TOL_TELA = 1e-6
# O zoom vem do Reframe, que muda conforme o estado da janela do CATIA, mesmo com o
# mesmo codigo. A origem e a selecao sao exatas; no zoom so se confere a ordem de grandeza.
TOL_ZOOM = 0.25

MODULO_TESTE = r'''
Option Explicit
Public CATIA As Object
Private mSaida As String
Private mResp As Variant
Private mPos As Long

Private Function Plano(ByVal s As String) As String
    Plano = Replace(Replace(Replace(s, vbCrLf, "<CRLF>"), vbCr, "<CR>"), vbLf, "<LF>")
End Function

Public Sub Grava(ByVal s As String)
    Dim f As Integer: f = FreeFile
    Open mSaida For Append As #f: Print #f, s: Close #f
End Sub

Public Sub MsgTeste(ByVal p As String, Optional ByVal b As Long, Optional ByVal t As String)
    Grava "MSG" & Chr(31) & t & Chr(31) & Plano(p)
End Sub

Public Function InputTeste(ByVal p As String, Optional ByVal t As String, Optional ByVal d As String) As String
    Grava "INPUT" & Chr(31) & t & Chr(31) & Plano(p) & Chr(31) & d
    InputTeste = mResp(mPos)
    mPos = mPos + 1
End Function

Private Function Estado(ByVal doc As Object) As String
    Dim vp As Object, o(1) As Variant, sel As Object, nome As String
    Set sel = doc.Selection
    Set vp = CATIA.ActiveWindow.ActiveViewer.Viewpoint2D
    vp.GetOrigin o
    If sel.Count > 0 Then nome = sel.Item(1).Value.Name
    Estado = doc.Sheets.ActiveSheet.Name & Chr(31) & Trim(Str(o(0))) & Chr(31) & Trim(Str(o(1))) & Chr(31) & _
        Trim(Str(vp.Zoom)) & Chr(31) & sel.Count & Chr(31) & nome
End Function

Public Sub RodarCaso(ByVal caminho As String, ByVal respostas As String, ByVal apagar As Long, ByVal limite As Long, ByVal saida As String)
    Dim doc As Object, i As Long, c As Long, s As String, nNav As Long
    mSaida = saida
    mResp = Split(respostas, ";")
    mPos = 0
    Set CATIA = GetObject(, "CATIA.Application")
    CATIA.DisplayFileAlerts = False
    Do While CATIA.Documents.Count > 0: CATIA.Documents.Item(1).Close: Loop
    Set doc = CATIA.Documents.Open(caminho)
    RunFontInspection
    Grava "RESUMO" & Chr(31) & Plano(FontNavResumo())
    Grava "TOTAL" & Chr(31) & FontNavCount()
    nNav = FontNavCount(): If nNav > limite Then nNav = limite
    For i = 1 To FontNavCount()
        s = "ITEM"
        For c = 0 To 4: s = s & Chr(31) & FontNavInfo(i, c): Next c
        Grava s
    Next i
    For i = 1 To nNav
        If FontNavIr(i) Then Grava "NAV" & Chr(31) & i & Chr(31) & Estado(doc) Else Grava "NAV" & Chr(31) & i & Chr(31) & "FALHOU"
    Next i
    If apagar > 0 Then
        FontNavIr apagar
        doc.Selection.Delete
        Grava "APAGOU" & Chr(31) & apagar
        For i = 1 To FontNavCount()
            If FontNavIr(i) Then Grava "NAV" & Chr(31) & i & Chr(31) & Estado(doc) Else Grava "NAV" & Chr(31) & i & Chr(31) & "FALHOU"
        Next i
    End If
    doc.Close
End Sub

Public Sub CasoReset(ByVal caminho As String, ByVal saida As String)
    Dim doc As Object, sel As Object, t As Object, r As Long, g As Long, b As Long
    mSaida = saida
    Set CATIA = GetObject(, "CATIA.Application")
    CATIA.DisplayFileAlerts = False
    Do While CATIA.Documents.Count > 0: CATIA.Documents.Item(1).Close: Loop
    Set doc = CATIA.Documents.Open(caminho)
    Set sel = doc.Selection
    Set t = doc.Sheets.Item(1).Views.Item(3).Texts.Item(1)
    sel.Clear: sel.Add t: sel.VisProperties.SetRealColor 255, 255, 255, 0: sel.Clear
    ' Sem isto, um erro aqui abriria uma janela no Excel escondido e travaria o teste.
    On Error Resume Next
    ResetColors
    If Err.Number <> 0 Then Grava "ERRO" & Chr(31) & Err.Description
    Err.Clear
    On Error GoTo 0
    sel.Clear: sel.Add t: sel.VisProperties.GetRealColor r, g, b: sel.Clear
    Grava "COR" & Chr(31) & r & "," & g & "," & b
    doc.Close
End Sub

Public Sub Grade(ByVal saida As String)
    Dim k As Long, v As Double, mm As Double, f As Integer
    f = FreeFile
    Open saida For Output As #f
    For k = 1 To 300000
        mm = k / 10000#
        v = Round(mm / 25.4, 4)
        Print #f, Trim(Str(v)) & " " & Format$(v, "0.000")
        mm = 25.4 * (k + 0.5) / 10000#
        v = Round(mm / 25.4, 4)
        Print #f, Trim(Str(v)) & " " & Format$(v, "0.000")
    Next k
    Close #f
End Sub
'''


def plano(s: str) -> str:
    return s.replace("\r\n", "<CRLF>").replace("\r", "<CR>").replace("\n", "<LF>")


def preparar_fonte(pasta_vba: str, destino: str) -> None:
    """Copia a macro atual trocando so as janelas, que nao podem parar o teste."""
    with open(os.path.join(pasta_vba, "sizedetect.txt"), encoding="utf-8") as f:
        fonte = f.read()
    fonte = fonte.replace("MsgBox", "MsgTeste").replace("InputBox(", "InputTeste(")
    with open(destino, "w", encoding="cp1252", newline="\r\n") as f:
        f.write(fonte)


def abrir_excel(arquivo_fonte: str):
    xl = com.Dispatch("Excel.Application")
    xl.Visible = False
    xl.DisplayAlerts = False
    wb = xl.Workbooks.Add()
    wb.VBProject.References.AddFromFile(os.path.join(TLBS, "InfTypeLib.tlb"))
    wb.VBProject.References.AddFromFile(os.path.join(TLBS, "DraftingTypeLib.tlb"))
    m = wb.VBProject.VBComponents.Add(1)
    m.Name = "CHECKSIZE"
    m.CodeModule.DeleteLines(1, m.CodeModule.CountOfLines)
    m.CodeModule.AddFromFile(arquivo_fonte)
    m = wb.VBProject.VBComponents.Add(1)
    m.Name = "Teste"
    m.CodeModule.DeleteLines(1, m.CodeModule.CountOfLines)
    m.CodeModule.AddFromString(MODULO_TESTE)
    return xl, wb


def caso_vba(xl, trabalho: str, caminho: str, respostas: str, apagar: int, limite: int) -> list:
    saida = os.path.join(trabalho, "saida.txt")
    if os.path.exists(saida):
        os.remove(saida)
    xl.Run("RodarCaso", caminho, respostas, apagar, limite, saida)
    with open(saida, encoding="cp1252") as f:
        return f.read().splitlines()


def caso_python(bridge: CatiaBridge, apoio: str, caminho: str, respostas: str, apagar: int, limite: int):
    app = bridge.app
    app.DisplayFileAlerts = False
    while app.Documents.Count:
        app.Documents.Item(1).Close()
    doc = app.Documents.Open(caminho)
    linhas = []
    fila = respostas.split(";")

    def ask(pergunta, titulo, sugestao):
        linhas.append(CAMPO.join(["INPUT", titulo, plano(pergunta), sugestao]))
        return fila.pop(0)

    def warn(mensagem, titulo):
        linhas.append(CAMPO.join(["MSG", titulo, plano(mensagem)]))

    def estado():
        return app.SystemService.ExecuteScript(apoio, 1, "sonda_tela.catvbs", "Estado", [])

    def navegar(rep):
        for i, item in enumerate(rep.items[:limite], 1):
            alvo = estado() if fc.go_to_item(bridge, rep, item) else "FALHOU"
            linhas.append(CAMPO.join(["NAV", str(i), alvo]))

    t0 = time.perf_counter()
    rep = fc.run_font_inspection(bridge, ask, warn)
    tempo = time.perf_counter() - t0

    if rep is None:
        # O VBA sai sem mexer na lista nem no resumo, que ficam vazios.
        linhas += [CAMPO.join(["RESUMO", ""]), CAMPO.join(["TOTAL", "0"])]
    else:
        linhas.append(CAMPO.join(["MSG", fc.TITULO_ANALISE, plano(rep.mensagem)]))
        linhas.append(CAMPO.join(["RESUMO", plano(rep.resumo)]))
        linhas.append(CAMPO.join(["TOTAL", str(len(rep.items))]))
        for it in rep.items:
            linhas.append(CAMPO.join(["ITEM", it.sheet_name, it.view_name, it.text, it.size, it.standard]))
        navegar(rep)
        if apagar > 0:
            fc.go_to_item(bridge, rep, rep.items[apagar - 1])
            app.SystemService.ExecuteScript(apoio, 1, "sonda_tela.catvbs", "ApagarSelecao", [])
            linhas.append(CAMPO.join(["APAGOU", str(apagar)]))
            navegar(rep)
    doc.Close()
    return linhas, tempo


def reset_vba(xl, trabalho: str, caminho: str) -> list:
    saida = os.path.join(trabalho, "saida.txt")
    if os.path.exists(saida):
        os.remove(saida)
    xl.Run("CasoReset", caminho, saida)
    with open(saida, encoding="cp1252") as f:
        return f.read().splitlines()


def reset_python(bridge: CatiaBridge, apoio: str, caminho: str) -> list:
    app = bridge.app
    while app.Documents.Count:
        app.Documents.Item(1).Close()
    doc = app.Documents.Open(caminho)
    app.SystemService.ExecuteScript(apoio, 1, "sonda_tela.catvbs", "PintarBranco", [])
    linhas = []
    try:
        if fc.reset_colors(bridge):
            linhas.append(CAMPO.join(["MSG", fc.TITULO_RESET, plano(fc.MENSAGEM_RESET)]))
    except CatiaError as exc:
        linhas.append(CAMPO.join(["ERRO", str(exc)]))
    linhas.append("COR" + CAMPO + app.SystemService.ExecuteScript(apoio, 1, "sonda_tela.catvbs", "LerCor", []))
    doc.Close()
    return linhas


def iguais(a: str, b: str) -> bool:
    """Linhas iguais; na tela, os numeros podem variar na ultima casa do texto."""
    if a == b:
        return True
    ca, cb = a.split(CAMPO), b.split(CAMPO)
    if ca[0] != "NAV" or cb[0] != "NAV" or len(ca) != 8 or len(cb) != 8:
        return False
    if ca[:3] != cb[:3] or ca[6:] != cb[6:]:
        return False
    if any(abs(float(ca[i]) - float(cb[i])) > TOL_TELA * max(1.0, abs(float(ca[i]))) for i in (3, 4)):
        return False
    return abs(float(ca[5]) - float(cb[5])) <= TOL_ZOOM * float(ca[5])


def comparar_grade(trabalho: str, xl, bridge: CatiaBridge, apoio: str) -> int:
    """Confere a conta de polegadas em 600 mil tamanhos.

    Metade sao tamanhos comuns, que precisam dar exatamente igual. A outra metade sao
    empates exatos (0,17055"), onde o Round do VBA e o do CATIA ja discordam entre si.
    Ali se mede quantos mudariam o resultado da conferencia.
    """
    saida = os.path.join(trabalho, "grade.txt")
    sep = fc.windows_decimal_separator()
    xl.Run("Grade", saida)
    with open(saida, encoding="cp1252") as f:
        vba = f.read().split(chr(10))
    padroes = sorted(set(fc._PADROES.values()))
    comuns = empates = decisao = 0
    exemplos = []
    for k in range(1, 300001):
        for j, mm in enumerate((k / 10000, 25.4 * (k + 0.5) / 10000)):
            valor = fc.round_vba(mm / 25.4)
            v_vba, txt_vba = vba[2 * (k - 1) + j].split(" ")
            v_vba = float(v_vba)
            if abs(v_vba - valor) <= 1e-12 and fc.format_inch(valor, sep) == txt_vba + '"':
                continue
            if j == 0:
                comuns += 1
                print(f"  COMUM DIFERENTE, mm={mm!r}: VBA {v_vba} {txt_vba} x Python {valor!r}")
            else:
                empates += 1
                if any(fc.is_standard(v_vba, p) != fc.is_standard(valor, p) for p in padroes):
                    decisao += 1
                    if len(exemplos) < 12:
                        exemplos.append(f"{mm:.5f} mm")
    print(f"Grade VBA x Python: 300000 tamanhos comuns, {comuns} diferencas")
    print(f"Grade VBA x Python: 300000 empates exatos, {empates} diferencas, {decisao} mudam a conferencia {exemplos}")
    erros_catia = {False: 0, True: 0}
    for inicio in range(1, 300001, 50000):
        fim = min(inicio + 49999, 300000)
        for empate in (False, True):
            vals = bridge.app.SystemService.ExecuteScript(apoio, 1, "sonda_tela.catvbs", "GradeRound", [inicio, fim, empate]).split(" ")
            for k, v in zip(range(inicio, fim + 1), vals):
                mm = 25.4 * (k + 0.5) / 10000 if empate else k / 10000
                if abs(float(v) - fc.round_vba(mm / 25.4)) > 1e-12:
                    erros_catia[empate] += 1
    print(f"Grade dentro do CATIA x Python: comuns {erros_catia[False]} diferencas, empates {erros_catia[True]} diferencas")
    return comuns + erros_catia[False]


def main() -> int:
    pasta_vba = sys.argv[1]
    extras = sys.argv[2:]
    trabalho = tempfile.mkdtemp(prefix="paridade_font_")
    bridge = CatiaBridge()
    apoio = AQUI

    r = bridge.app.SystemService.ExecuteScript(AQUI, 1, "montar_fixtures_font.catvbs", "Montar", [trabalho])
    print("Desenhos de teste:", r, trabalho)

    fonte = os.path.join(trabalho, "sizedetect_teste.txt")
    preparar_fonte(pasta_vba, fonte)
    xl, wb = abrir_excel(fonte)

    rico = os.path.join(trabalho, "FONT_RICO.CATDrawing")
    sem = os.path.join(trabalho, "FONT_SEMFORMATO.CATDrawing")
    ok = os.path.join(trabalho, "FONT_TUDOOK.CATDrawing")
    # O cancelamento vem primeiro: no VBA ele nao limpa o resumo da analise anterior.
    casos = [
        ("sem formato, cancela", sem, ";", 0, 9999),
        ("todos os casos", rico, "A1", 0, 9999),
        ("apagando um item no meio", rico, "A1", 3, 9999),
        ("sem formato, responde a2", sem, "a2", 0, 9999),
        ("sem formato, invalido e depois A2", sem, "Z9;A2", 0, 9999),
        ("tudo dentro do padrao", ok, "A1", 0, 9999),
    ] + [(os.path.basename(p), p, "A1", 0, 10) for p in extras]

    falhas = 0
    try:
        for nome, caminho, respostas, apagar, limite in casos:
            vba = caso_vba(xl, trabalho, caminho, respostas, apagar, limite)
            py, tempo = caso_python(bridge, apoio, caminho, respostas, apagar, limite)
            difs = [
                (i, a, b)
                for i, (a, b) in enumerate(zip(vba, py))
                if not iguais(a, b)
            ]
            tamanho = len(vba) != len(py)
            status = "IGUAL" if not difs and not tamanho else "DIFERENTE"
            print(f"[{status}] {nome}: {len(vba)} linhas VBA x {len(py)} Python, Python em {tempo:.2f} s")
            if difs or tamanho:
                falhas += 1
                for i, a, b in difs[:12]:
                    print(f"  linha {i + 1}\n    VBA: {a!r}\n    PY : {b!r}")
                if tamanho:
                    print("  sobrou VBA:", vba[len(py):][:4])
                    print("  sobrou PY :", py[len(vba):][:4])
        vba = reset_vba(xl, trabalho, rico)
        py = reset_python(bridge, apoio, rico)
        # O texto do erro muda de um lado para o outro; compara se falhou e a cor final.
        vba = [lin.split(CAMPO)[0] if lin.startswith("ERRO") else lin for lin in vba if lin.split(CAMPO)[0] in ("ERRO", "MSG", "COR")]
        py = [lin.split(CAMPO)[0] if lin.startswith("ERRO") else lin for lin in py]
        print(f"[{'IGUAL' if vba == py else 'DIFERENTE'}] restaurar cores: {vba} x {py}")
        if vba != py:
            falhas += 1
            print("  VBA:", vba)
            print("  PY :", py)
        falhas += 1 if comparar_grade(trabalho, xl, bridge, apoio) else 0
    finally:
        wb.Close(False)
        xl.Quit()
    print("RESULTADO:", "TUDO IGUAL" if not falhas else f"{falhas} COM DIFERENCA")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
