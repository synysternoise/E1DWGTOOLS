"""Que documento e este, pelo nome que o CATIA devolve.

Salvo no PC, o nome e o do arquivo: 171-60466-803.CATDrawing. Aberto pelo VPM nao ha arquivo, e o
nome vem como "171-60466-803      1       1  --- CATDRAWING     1 ---".
"""
from __future__ import annotations

import re

_RE_VPM_DESENHO = re.compile(r"---\s*CATDRAWING\b", re.I)
_RE_BLOCOS = re.compile(r"\s{2,}")


def eh_desenho(nome) -> bool:
    nome = str(nome)
    return nome.lower().endswith(".catdrawing") or _RE_VPM_DESENHO.search(nome) is not None


def pn_do_documento(nome) -> str:
    """O PN: o nome do arquivo sem a extensao ou, no VPM, o primeiro bloco do nome."""
    nome = str(nome).strip(" ")
    if _RE_VPM_DESENHO.search(nome):
        return _RE_BLOCOS.split(nome)[0]
    ponto = nome.rfind(".")
    return nome[:ponto] if ponto > 0 else nome
