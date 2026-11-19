"""Ponte entre o Python e o CATIA V5.

Cada chamada COM de fora do CATIA e lenta, entao o trabalho pesado roda dentro
dele: o Python chama uma funcao de um script em src/engine/catia_scripts e
recebe tudo de volta numa string so.

Protocolo das funcoes de script: a resposta e uma lista de registros separados
por Chr(30), com campos separados por Chr(31). O primeiro registro e o status:
"OK" ou "ERR" seguido do numero e da descricao do erro. Assim um erro no script
volta como excecao aqui, sem abrir janela de erro no CATIA.

COM exige inicializacao por thread: crie um CatiaBridge dentro da thread que
vai usa-lo.
"""
from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from typing import List, Optional

import pythoncom
import pywintypes
import win32com.client

SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "catia_scripts")
SCRIPT_LIBRARY_DIRECTORY = 1  # catScriptLibraryTypeDirectory

REGISTRO = chr(30)
CAMPO = chr(31)
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


class CatiaError(Exception):
    """Falha ao falar com o CATIA ou erro dentro de um script."""

    def __init__(self, message: str, number: int = 0):
        super().__init__(message)
        self.number = number


class CatiaNotRunning(CatiaError):
    """O CATIA nao esta aberto."""


def parse_response(raw) -> List[List[str]]:
    """Separa a resposta em registros, sem o de status. Status ERR vira excecao."""
    if not isinstance(raw, str) or not raw:
        raise CatiaError("O script do CATIA não devolveu resposta.")
    registros = [r.split(CAMPO) for r in raw.split(REGISTRO)]
    status = registros[0]
    if status[0] == "ERR":
        numero = int(status[1]) if len(status) > 1 and status[1].lstrip("-").isdigit() else 0
        descricao = status[2] if len(status) > 2 else "erro desconhecido"
        raise CatiaError(descricao, numero)
    if status[0] != "OK":
        raise CatiaError(f"Resposta inválida do script do CATIA: {status[0][:60]!r}")
    return registros[1:]


def parse_number(texto: str) -> float:
    """Le um numero vindo do script (CStr usa a virgula decimal do Windows)."""
    return float(texto.replace(",", "."))


def titulo_janela_catia() -> Optional[str]:
    """Titulo da janela principal do CATIA, ou None se ele estiver fechado.

    Le so do Windows, sem falar com o CATIA: serve para consultas repetidas, que nao podem
    atrapalhar o que estiver rodando nele, como a conexao do SmarTeam.
    """
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.QueryFullProcessImageNameW.argtypes = (wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD))
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    user32.GetWindowTextLengthW.argtypes = (wintypes.HWND,)
    user32.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
    user32.IsWindowVisible.argtypes = (wintypes.HWND,)
    user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
    achado: List[str] = []
    processos = {}

    def eh_do_catia(pid: int) -> bool:
        processo = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not processo:
            return False
        try:
            tamanho = wintypes.DWORD(1024)
            caminho = ctypes.create_unicode_buffer(tamanho.value)
            if not kernel32.QueryFullProcessImageNameW(processo, 0, caminho, ctypes.byref(tamanho)):
                return False
            return os.path.basename(caminho.value).lower() == "cnext.exe"
        finally:
            kernel32.CloseHandle(processo)

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def olhar(hwnd, _dados):
        if not user32.IsWindowVisible(hwnd):
            return True
        # O processo vem antes do titulo: ler o titulo de uma janela do proprio HUB esperaria a
        # thread da tela, e o HUB travaria ao fechar.
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value not in processos:
            processos[pid.value] = eh_do_catia(pid.value)
        if not processos[pid.value]:
            return True
        n = user32.GetWindowTextLengthW(hwnd)
        texto = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, texto, n + 1)
        if texto.value.startswith("CATIA"):
            achado.append(texto.value)
            return False
        return True

    user32.EnumWindows(olhar, 0)
    return achado[0] if achado else None


class CatiaBridge:
    def __init__(self, scripts_dir: str = SCRIPTS_DIR):
        self.scripts_dir = scripts_dir
        pythoncom.CoInitialize()
        try:
            self.app = win32com.client.GetActiveObject("CATIA.Application")
        except pywintypes.com_error as exc:
            raise CatiaNotRunning("O CATIA não está aberto.") from exc

    def call(self, script: str, function: str, *args) -> List[List[str]]:
        """Roda uma funcao de script dentro do CATIA e devolve os registros."""
        try:
            raw = self.app.SystemService.ExecuteScript(
                self.scripts_dir, SCRIPT_LIBRARY_DIRECTORY, script, function, list(args)
            )
        except pywintypes.com_error as exc:
            raise CatiaError(f"Falha ao executar {script} ({function}): {exc}") from exc
        return parse_response(raw)
