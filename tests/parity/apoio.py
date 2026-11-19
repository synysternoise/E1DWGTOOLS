"""Apoio dos testes de paridade: roda a macro VBA de verdade num Excel escondido."""
from __future__ import annotations

import os
import re
import subprocess
import threading
import unicodedata

import win32com.client as com
import win32process

TLBS = r"C:\Program Files (x86)\Dassault Systemes\B20\intel_a\code\bin"

# Modulo comum a todos os testes: grava as janelas num arquivo em vez de abri-las.
MODULO_JANELAS = r'''
Option Explicit
Public CATIA As Object
Public mSaida As String
Private mRespostas As Variant
Private mPos As Long

Public Function Plano(ByVal s As String) As String
    Plano = Replace(Replace(Replace(s, vbCrLf, "<CRLF>"), vbCr, "<CR>"), vbLf, "<LF>")
End Function

Public Sub Grava(ByVal s As String)
    Dim f As Integer: f = FreeFile
    Open mSaida For Append As #f: Print #f, s: Close #f
End Sub

Public Sub Preparar(ByVal respostas As String, ByVal saida As String)
    mSaida = saida
    mRespostas = Split(respostas, ";")
    mPos = 0
    Set CATIA = GetObject(, "CATIA.Application")
End Sub

Public Function MsgTeste(ByVal p As String, Optional ByVal b As Long, Optional ByVal t As String) As Long
    Grava "MSG" & Chr(31) & t & Chr(31) & Plano(p)
    MsgTeste = 6
End Function

Public Function InputTeste(ByVal p As String, Optional ByVal t As String, Optional ByVal d As String) As String
    Grava "INPUT" & Chr(31) & t & Chr(31) & Plano(p) & Chr(31) & d
    InputTeste = mRespostas(mPos)
    mPos = mPos + 1
End Function
'''


def sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def plano(s: str) -> str:
    return s.replace("\r\n", "<CRLF>").replace("\r", "<CR>").replace("\n", "<LF>")


def trocar_janelas(fonte: str) -> str:
    fonte = re.sub(r"\bMsgBox\b", "MsgTeste", fonte)
    return re.sub(r"\bInputBox\b", "InputTeste", fonte)


def ler_fonte(caminho: str) -> str:
    with open(caminho, "rb") as f:
        dados = f.read()
    try:
        return dados.decode("utf-8")
    except UnicodeDecodeError:
        return dados.decode("cp1252")


def abrir_excel(arquivos: dict, referencias=("InfTypeLib.tlb", "DraftingTypeLib.tlb", "KweTypeLib.tlb"), extra: str = ""):
    """Abre um Excel so para o teste. arquivos: nome do modulo -> caminho do fonte."""
    xl = com.DispatchEx("Excel.Application")
    xl.Visible = False
    xl.DisplayAlerts = False
    wb = xl.Workbooks.Add()
    for ref in referencias:
        caminho = os.path.join(TLBS, ref)
        if os.path.exists(caminho):
            wb.VBProject.References.AddFromFile(caminho)
    for nome, caminho in arquivos.items():
        m = wb.VBProject.VBComponents.Add(1)
        m.Name = nome
        m.CodeModule.DeleteLines(1, m.CodeModule.CountOfLines)
        m.CodeModule.AddFromFile(caminho)
    m = wb.VBProject.VBComponents.Add(1)
    m.Name = "Janelas"
    m.CodeModule.DeleteLines(1, m.CodeModule.CountOfLines)
    m.CodeModule.AddFromString(MODULO_JANELAS + extra)
    return xl, wb


def gravar_fonte(fonte: str, destino: str) -> None:
    """Grava para o VBA importar. Caractere que o cp1252 nao tem vira ?, como no editor do VBA."""
    with open(destino, "w", encoding="cp1252", errors="replace", newline="\r\n") as f:
        f.write(fonte.replace("\r\n", "\n"))


def vigia(xl, segundos: int) -> threading.Timer:
    """Se o Excel do teste travar numa janela escondida, encerra so ele e mostra o texto dela."""
    _, pid = win32process.GetWindowThreadProcessId(xl.Hwnd)

    def estourou():
        print(f"TEMPO ESGOTADO: encerrando o Excel do teste (PID {pid})", flush=True)
        try:
            import win32gui

            def filho(c, _):
                t = win32gui.GetWindowText(c)
                if t and win32gui.GetClassName(c) == "Static":
                    print("   janela:", t, flush=True)
                return True

            def topo(h, _):
                if win32process.GetWindowThreadProcessId(h)[1] == pid and win32gui.GetClassName(h) == "#32770":
                    win32gui.EnumChildWindows(h, filho, None)
                return True

            win32gui.EnumWindows(topo, None)
        except Exception as exc:  # o diagnostico nao pode impedir o encerramento
            print("   sem diagnostico:", exc, flush=True)
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
        os._exit(3)

    t = threading.Timer(segundos, estourou)
    t.daemon = True
    t.start()
    return t
