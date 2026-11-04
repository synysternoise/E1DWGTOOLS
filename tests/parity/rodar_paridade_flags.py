"""Compara o Fix Flags em Python com o VBA de verdade.

1. Simulacao: o mesmo DrawingText simulado, que falha sob encomenda, roda no VBA (Excel) e
   no script (cscript). Cobre os caminhos que restauram o desenho, que o CATIA nao reproduz.
2. CATIA: a macro atual (vba_referencia/fixflags) e o Python rodam nos mesmos desenhos. Depois
   de cada um, todos os textos sao fotografados: texto, tipo da flag, cor e borda de cada
   letra, tamanho, posicao e leaders. Mensagens e fotografias precisam ser iguais.

Uso (com o CATIA aberto e sem desenhos importantes abertos, porque fecha todos):
    python tests/parity/rodar_paridade_flags.py [--so-vba] [--so-simulacao]
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import unicodedata

import pythoncom
import win32com.client as com
import win32process

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.join(AQUI, "..", "..")
sys.path.insert(0, os.path.join(RAIZ, "src"))

from engine import fix_flags as ff  # noqa: E402
from engine.catia_bridge import CAMPO, REGISTRO, SCRIPTS_DIR, CatiaBridge  # noqa: E402

LIMITE_S = 1500

MODULO_TESTE = r'''
Option Explicit
Public CATIA As Object
Private mSaida As String
Private mResposta As Long

Private Function Plano(ByVal s As String) As String
    Plano = Replace(Replace(Replace(s, vbCrLf, "<CRLF>"), vbCr, "<CR>"), vbLf, "<LF>")
End Function

Public Sub Grava(ByVal s As String)
    Dim f As Integer: f = FreeFile
    Open mSaida For Append As #f: Print #f, s: Close #f
End Sub

Public Function MsgTeste(ByVal p As String, Optional ByVal b As Long, Optional ByVal t As String) As Long
    Grava "MSG" & Chr(31) & t & Chr(31) & b & Chr(31) & Plano(p)
    MsgTeste = mResposta
End Function

Public Sub Rodar(ByVal resposta As Long, ByVal saida As String)
    mSaida = saida
    mResposta = resposta
    Set CATIA = GetObject(, "CATIA.Application")
    CorrigirFlagNotes
End Sub

Public Sub RodarSimulacao(ByVal saida As String)
    Dim f As Integer: f = FreeFile
    Open saida For Output As #f: Print #f, RodarSimulados(): Close #f
End Sub
'''

FIM_FONTE = r'''

Public Function LerContadoresFix() As String
    LerContadoresFix = Join(Array(fixTotalTextos, fixTotalFlags, fixTotalFlagsObjetoInteiro, _
        fixTotalFlagsTextEditor, fixTotalFlagsComCadeado, fixTotalCorrigidas, fixTotalJaCorretas, _
        fixTotalIgnoradas, fixTotalFalhasValidacao, fixTotalRestauradas, fixTotalErros), Chr(31))
End Function
'''

SEM_ACENTO_TIT = {ff.TITULO_AVISO, ff.TITULO_CONFIRMA, ff.TITULO_RESULTADO, ff.TITULO_ERRO}


def sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def plano(s: str) -> str:
    return s.replace("\r\n", "<CRLF>").replace("\r", "<CR>").replace("\n", "<LF>")


def ler_simulado() -> str:
    with open(os.path.join(AQUI, "texto_simulado.vbsinc"), encoding="ascii") as f:
        return f.read()


def classes_para_vba(fonte: str) -> dict:
    """Separa as Class do arquivo comum em modulos de classe do VBA e o resto em modulo comum."""
    classes, resto, atual, nome = {}, [], None, ""
    for linha in fonte.splitlines():
        if linha.startswith("Class "):
            nome, atual = linha.split()[1], []
        elif linha.startswith("End Class"):
            classes[nome] = "\n".join(atual)
            atual = None
        elif atual is not None:
            atual.append(linha)
        else:
            resto.append(linha)
    return {"classes": classes, "resto": "\n".join(resto)}


def preparar_fonte(destino: str) -> None:
    with open(os.path.join(RAIZ, "vba_referencia", "fixflags"), encoding="cp1252") as f:
        fonte = f.read()
    # Janelas nao podem parar o teste; e a simulacao chama direto a rotina de um texto.
    fonte = re.sub(r"\bMsgBox\b", "MsgTeste", fonte)
    fonte = fonte.replace("Private Sub ProcessarFlagSegura", "Public Sub ProcessarFlagSegura")
    fonte = fonte.replace("Private Sub ResetarContadoresFix", "Public Sub ResetarContadoresFix")
    with open(destino, "w", encoding="cp1252", newline="\r\n") as f:
        f.write(fonte + FIM_FONTE)


def abrir_excel(arquivo_fonte: str):
    xl = com.DispatchEx("Excel.Application")
    xl.Visible = False
    xl.DisplayAlerts = False
    wb = xl.Workbooks.Add()
    m = wb.VBProject.VBComponents.Add(1)
    m.Name = "FlagNotesFix"
    m.CodeModule.DeleteLines(1, m.CodeModule.CountOfLines)
    m.CodeModule.AddFromFile(arquivo_fonte)
    m = wb.VBProject.VBComponents.Add(1)
    m.Name = "Teste"
    m.CodeModule.DeleteLines(1, m.CodeModule.CountOfLines)
    m.CodeModule.AddFromString(MODULO_TESTE)
    partes = classes_para_vba(ler_simulado())
    for nome, corpo in partes["classes"].items():
        c = wb.VBProject.VBComponents.Add(2)
        c.Name = nome
        c.CodeModule.DeleteLines(1, c.CodeModule.CountOfLines)
        c.CodeModule.AddFromString(corpo)
    m = wb.VBProject.VBComponents.Add(1)
    m.Name = "Simulados"
    m.CodeModule.DeleteLines(1, m.CodeModule.CountOfLines)
    m.CodeModule.AddFromString(
        partes["resto"] + "\nFunction NovoTextoSimulado()\n    Set NovoTextoSimulado = New TextoSimulado\nEnd Function\n"
    )
    return xl, wb


def vigia(xl) -> threading.Timer:
    """Se o Excel do teste travar numa janela escondida, encerra so ele."""
    _, pid = win32process.GetWindowThreadProcessId(xl.Hwnd)

    def estourou():
        print(f"TEMPO ESGOTADO: encerrando o Excel do teste (PID {pid})", flush=True)
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
        os._exit(3)

    t = threading.Timer(LIMITE_S, estourou)
    t.daemon = True
    t.start()
    return t


def rodar_simulacao_vbs(trabalho: str) -> str:
    with open(os.path.join(SCRIPTS_DIR, ff.SCRIPT), encoding="ascii") as f:
        script = f.read()
    corpo = ler_simulado() + "\nFunction NovoTextoSimulado()\n    Set NovoTextoSimulado = New TextoSimulado\nEnd Function\n"
    caminho = os.path.join(trabalho, "simulacao.vbs")
    with open(caminho, "w", encoding="cp1252", newline="\r\n") as f:
        f.write(script + "\r\n" + corpo + "\r\nWScript.StdOut.Write RodarSimulados()\r\n")
    r = subprocess.run(["cscript", "//nologo", caminho], capture_output=True, timeout=300)
    if r.returncode != 0 or r.stderr:
        raise RuntimeError("cscript falhou: " + r.stderr.decode("cp1252", "replace"))
    return r.stdout.decode("cp1252")


def rodar_simulacao_vba(xl, trabalho: str) -> str:
    saida = os.path.join(trabalho, "simulacao_vba.txt")
    xl.Run("RodarSimulacao", saida)
    with open(saida, encoding="cp1252") as f:
        return f.read()


def comparar_simulacao(xl, trabalho: str) -> int:
    vba = [l for l in rodar_simulacao_vba(xl, trabalho).splitlines() if l.strip()]
    vbs = [l for l in rodar_simulacao_vbs(trabalho).splitlines() if l.strip()]
    difs = [(a, b) for a, b in zip(vba, vbs) if a != b]
    falha = bool(difs) or len(vba) != len(vbs)
    print(f"[{'DIFERENTE' if falha else 'IGUAL'}] simulacao de falhas: {len(vba)} casos VBA x {len(vbs)} script, {len(difs)} diferencas")
    for a, b in difs[:14]:
        print(f"    VBA: {a!r}\n    PY : {b!r}")
    # Mostra quantos casos de fato passaram pelos caminhos de falha.
    falhas = sum(1 for l in vba if int(l.split(" => ")[1].split(chr(31))[8]) > 0)
    restauradas = sum(1 for l in vba if int(l.split(" => ")[1].split(chr(31))[9]) > 0)
    erros = sum(1 for l in vba if int(l.split(" => ")[1].split(" :: ")[0].split(chr(31))[10]) > 0)
    print(f"    casos com falha de validacao: {falhas}, com restauracao: {restauradas}, com erro: {erros}")
    return 1 if falha else 0


def foto(bridge: CatiaBridge) -> list:
    r = bridge.app.SystemService.ExecuteScript(AQUI, 1, "sonda_flags.catvbs", "Foto", [])
    if r.startswith("ERRO FOTO"):
        raise RuntimeError(r)
    return r.split(REGISTRO)


def fechar_tudo(bridge: CatiaBridge) -> None:
    bridge.app.SystemService.ExecuteScript(AQUI, 1, "sonda_flags.catvbs", "Fechar", [])


def abrir(bridge: CatiaBridge, caminho) -> None:
    fechar_tudo(bridge)
    if caminho:
        bridge.app.Documents.Open(caminho)


def vba_uma(xl, trabalho: str, resposta: int) -> list:
    saida = os.path.join(trabalho, "saida.txt")
    if os.path.exists(saida):
        os.remove(saida)
    xl.Run("Rodar", resposta, saida)
    if not os.path.exists(saida):
        return []
    with open(saida, encoding="cp1252") as f:
        return f.read().splitlines()


def python_uma(bridge: CatiaBridge, sim: bool) -> tuple:
    linhas = []

    def confirm(mensagem, titulo):
        linhas.append(CAMPO.join(["MSG", titulo, "292", plano(mensagem)]))
        return sim

    def warn(mensagem, titulo):
        linhas.append(CAMPO.join(["MSG", titulo, "48", plano(mensagem)]))

    t0 = time.perf_counter()
    try:
        rep = ff.run_fix_flags(bridge, confirm, warn)
    except ff.FixInterrompido as exc:
        linhas.append(CAMPO.join(["MSG", ff.TITULO_ERRO, "16", plano(exc.mensagem)]))
        rep = None
    if rep is not None:
        linhas.append(CAMPO.join(["MSG", ff.TITULO_RESULTADO, "64", plano(rep.mensagem)]))
    return linhas, rep, time.perf_counter() - t0


def norm_msgs(linhas: list) -> list:
    return [sem_acento(l) for l in linhas]


def caso(xl, bridge, trabalho, nome, caminho, resposta_vba, vezes=1, so_vba=False, exigir=None) -> int:
    abrir(bridge, caminho)
    antes = foto(bridge) if caminho and caminho.lower().endswith(".catdrawing") else []
    vba_msgs, vba_fotos, t_vba = [], [], 0.0
    for _ in range(vezes):
        t0 = time.perf_counter()
        vba_msgs.append(vba_uma(xl, trabalho, resposta_vba))
        t_vba += time.perf_counter() - t0
        if antes:
            vba_fotos.append(foto(bridge))
    if so_vba:
        print(f"--- {nome} ({t_vba:.1f} s)")
        for m in vba_msgs:
            print("   MSGS:", [l.split(CAMPO)[-1][:300] for l in m if "Confirmar" not in l])
        if antes:
            print(f"   textos: {len(antes)}, mudaram: {sum(a != b for a, b in zip(antes, vba_fotos[0]))}")
        return 0

    abrir(bridge, caminho)
    # A primeira leitura das folhas custa cerca de 1 s no CATIA: a foto paga isso nos dois lados.
    antes_py = foto(bridge) if antes else []
    falha = 0
    if antes_py != antes:
        falha = 1
        print("  o desenho nao partiu do mesmo estado nos dois lados")
    py_msgs, py_fotos, t_py = [], [], 0.0
    rep = primeiro_rep = None
    for _ in range(vezes):
        linhas, rep, tempo = python_uma(bridge, resposta_vba == 6)
        primeiro_rep = primeiro_rep or rep
        t_py += tempo
        py_msgs.append(linhas)
        if antes:
            py_fotos.append(foto(bridge))

    for n, (a, b) in enumerate(zip(vba_msgs, py_msgs), 1):
        if norm_msgs(a) != norm_msgs(b):
            falha = 1
            print(f"  mensagens diferentes na execucao {n}:\n    VBA: {a}\n    PY : {b}")
    for n, (a, b) in enumerate(zip(vba_fotos, py_fotos), 1):
        difs = [(x, y) for x, y in zip(a, b) if x != y]
        if difs or len(a) != len(b):
            falha = 1
            print(f"  fotografia diferente na execucao {n}: {len(difs)} textos, {len(a)} x {len(b)}")
            for x, y in difs[:10]:
                print(f"    VBA: {x!r}\n    PY : {y!r}")
    mudaram = sum(a != b for a, b in zip(antes, vba_fotos[0])) if antes else 0
    if rep is not None and exigir:
        # Sem isto, desenhos de teste mal montados dariam um "igual" que nao prova nada.
        faltou = [n for n, v in exigir.items() if getattr(primeiro_rep, n) < v]
        if faltou:
            falha = 1
            print(f"  o desenho de teste nao cobriu: {faltou}")
    if primeiro_rep is not None:
        print("  " + plano(primeiro_rep.mensagem).replace("<CRLF>", " | "))
    print(f"[{'DIFERENTE' if falha else 'IGUAL'}] {nome}: {len(antes)} textos, {mudaram} mudaram; VBA {t_vba:.1f} s, Python {t_py:.2f} s", flush=True)
    return falha


def main() -> int:
    so_vba = "--so-vba" in sys.argv
    so_sim = "--so-simulacao" in sys.argv
    trabalho = tempfile.mkdtemp(prefix="paridade_flags_")
    fonte = os.path.join(trabalho, "fixflags_teste.txt")
    preparar_fonte(fonte)
    pythoncom.CoInitialize()
    xl, wb = abrir_excel(fonte)
    relogio = vigia(xl)
    falhas = 0
    try:
        if not so_vba:
            falhas += comparar_simulacao(xl, trabalho)
        if so_sim:
            return falhas
        bridge = CatiaBridge()
        r = bridge.app.SystemService.ExecuteScript(AQUI, 1, "montar_fixtures_flags.catvbs", "Montar", [trabalho])
        print("Desenhos de teste:", r, trabalho, flush=True)
        if not r.startswith("OK"):
            return 1
        arq = lambda n: os.path.join(trabalho, n)  # noqa: E731
        cobertura = {"objeto": 50, "text_editor": 20, "cadeado": 20, "corrigidas": 30, "ja_corretas": 10,
                     "ignoradas": 50, "falhas": 1, "restauradas": 1}
        casos = [
            ("sem documento", None, 6, 1, None),
            ("documento nao e desenho", arq("NAO_E_DESENHO.CATPart"), 6, 1, None),
            ("responde Nao na confirmacao", arq("FLAGS_RICO.CATDrawing"), 7, 1, None),
            ("todos os casos, duas vezes seguidas", arq("FLAGS_RICO.CATDrawing"), 6, 2, cobertura),
            ("sem nenhuma flag", arq("FLAGS_SEM.CATDrawing"), 6, 1, None),
            ("tudo ja correto", arq("FLAGS_CERTAS.CATDrawing"), 6, 2, {"objeto": 1, "text_editor": 1, "ja_corretas": 2}),
        ]
        for nome, caminho, resp, vezes, exigir in casos:
            falhas += caso(xl, bridge, trabalho, nome, caminho, resp, vezes, so_vba, exigir)
        fechar_tudo(bridge)
    finally:
        relogio.cancel()
        wb.Close(False)
        xl.Quit()
    print("RESULTADO:", "TUDO IGUAL" if not falhas else f"{falhas} COM DIFERENCA")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
