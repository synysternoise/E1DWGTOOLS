"""Que documento e este.

O desenho e reconhecido pelo tipo que o CATIA informa (DrawingDocument), como os scripts que rodam
dentro dele ja fazem. O nome muda conforme a origem: salvo no PC vem 171-60466-803.CATDrawing; pelo
VPM vem "171-60466-803      1       1  --- CATDRAWING     1 ---", e outras origens podem ter outro
formato. O nome so decide quando o tipo nao pode ser lido.
"""
from __future__ import annotations

import re

DESENHO, PECA, PRODUTO = "DrawingDocument", "PartDocument", "ProductDocument"

_RE_VPM_DESENHO = re.compile(r"---\s*CATDRAWING\b", re.I)
_RE_SOMENTE_LEITURA = re.compile(r"\s*\(readonly\)$", re.I)
_RE_EXTENSAO = re.compile(r"\.(catdrawing|catpart|catproduct)$", re.I)


def tipo_documento(doc) -> str:
    """O tipo do documento no CATIA, como o TypeName do VBA. "" se nao der para saber."""
    try:
        tipo = doc._oleobj_.GetTypeInfo().GetDocumentation(-1)[0]
        if isinstance(tipo, str) and tipo.endswith("Document"):
            return tipo
    except Exception:  # noqa: BLE001 - sem a informacao de tipo, tenta pelo que o documento tem
        pass
    for atributo, tipo in (("Sheets", DESENHO), ("Part", PECA), ("Product", PRODUTO)):
        try:
            getattr(doc, atributo)
            return tipo
        except Exception:  # noqa: BLE001 - o documento nao tem esse atributo
            continue
    return ""


def _nome_e_desenho(nome: str) -> bool:
    nome = _RE_SOMENTE_LEITURA.sub("", str(nome).strip())
    return nome.lower().endswith(".catdrawing") or _RE_VPM_DESENHO.search(nome) is not None


def eh_desenho(doc_ou_nome) -> bool:
    """Documento do CATIA ou o nome dele. Com o documento, vale o tipo; o nome e so a reserva."""
    if isinstance(doc_ou_nome, str):
        return _nome_e_desenho(doc_ou_nome)
    tipo = tipo_documento(doc_ou_nome)
    if tipo:
        return tipo == DESENHO
    try:
        return _nome_e_desenho(str(doc_ou_nome.Name))
    except Exception:  # noqa: BLE001
        return False


def pn_do_documento(nome) -> str:
    """O PN: o nome sem a extensao ou, em nome com blocos (VPM e parecidos), o primeiro bloco."""
    nome = _RE_SOMENTE_LEITURA.sub("", str(nome).strip())
    if _RE_EXTENSAO.search(nome):
        return nome[: nome.rfind(".")]
    partes = nome.split()
    return partes[0] if partes else nome
