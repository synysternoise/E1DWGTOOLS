"""Leitura somente-leitura do CATDrawing aberto, para espelhar na UI.

Deteccao real: conecta a uma instancia de CATIA JA em execucao (sem
inicia-la). Nunca usa dados ficticios se passando por CATIA; quando nao ha
CATIA ou desenho, retorna um snapshot com connected/has_drawing = False e
uma mensagem explicando o estado.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

from engine.documento import eh_desenho

# Dimensoes nominais (mm) por formato, para desenhar a folha no preview.
FORMAT_MM = {
    "3A0": (1682.0, 1189.0),
    "A0": (1189.0, 841.0),
    "A1": (841.0, 594.0),
    "A2": (594.0, 420.0),
    "A3": (420.0, 297.0),
    "E3": (1118.0, 864.0),
}
DEFAULT_MM = (841.0, 594.0)


@dataclass
class ViewInfo:
    name: str
    x: float
    y: float


@dataclass
class SheetInfo:
    name: str
    width: float
    height: float
    views: List[ViewInfo] = field(default_factory=list)


@dataclass
class DrawingSnapshot:
    connected: bool = False      # CATIA em execucao?
    has_drawing: bool = False    # ha um CATDrawing ativo?
    name: str = ""
    message: str = ""
    sheets: List[SheetInfo] = field(default_factory=list)
    parameters: List[Tuple[str, str]] = field(default_factory=list)
    detected_format: str = ""


def get_catia_state() -> DrawingSnapshot:
    """Sonda leve (sem ler folhas/views) para o polling de status da UI.

    Distingue 'CATIA fechado' de 'CATIA ocupado': GetActiveObject so falha
    quando o CATIA nao esta registrado (fechado). Se obtivemos o app mas uma
    propriedade falha (CATIA ocupado), reportamos connected=True.
    """
    try:
        from engine.update_template import get_running_catia
        app = get_running_catia()
        count = app.Documents.Count  # força comunicação real com o servidor
    except Exception:
        # GetActiveObject falha (ou o proxy está morto) => CATIA fechado.
        return DrawingSnapshot(message="CATIA não está em execução.")
    if count == 0:
        return DrawingSnapshot(connected=True, message="CATIA aberto, nenhum documento.")
    try:
        name = str(app.ActiveDocument.Name)
    except Exception:
        return DrawingSnapshot(connected=True, message="CATIA aberto.")
    if not eh_desenho(name):
        return DrawingSnapshot(connected=True, name=name,
                               message="O documento ativo não é um CATDrawing.")
    return DrawingSnapshot(connected=True, has_drawing=True, name=name)


def get_snapshot() -> DrawingSnapshot:
    """Le o desenho ativo no CATIA em execucao. Nunca levanta."""
    try:
        from engine.update_template import get_running_catia
        app = get_running_catia()
    except Exception:
        return DrawingSnapshot(message="CATIA não está em execução.")

    try:
        if app.Documents.Count == 0:
            return DrawingSnapshot(
                connected=True, message="CATIA aberto, nenhum documento.")
        doc = app.ActiveDocument
        name = str(doc.Name)
        if not eh_desenho(name):
            return DrawingSnapshot(
                connected=True, name=name,
                message="O documento ativo não é um CATDrawing.")
    except Exception as exc:
        return DrawingSnapshot(connected=True, message=f"Erro ao acessar o CATIA: {exc}")

    # --- formato (do Background da 1a folha) --------------------------
    fmt = ""
    try:
        from engine.update_template import get_format_from_background
        fmt = get_format_from_background(doc.Sheets.Item(1))
    except Exception:
        fmt = ""
    width, height = FORMAT_MM.get(fmt, DEFAULT_MM)

    # --- folhas e views -----------------------------------------------
    sheets: List[SheetInfo] = []
    try:
        for i in range(1, doc.Sheets.Count + 1):
            sh = doc.Sheets.Item(i)
            info = SheetInfo(str(sh.Name), width, height)
            try:
                for j in range(1, sh.Views.Count + 1):
                    v = sh.Views.Item(j)
                    vname = str(v.Name)
                    if "BACKGROUND" in vname.upper():
                        continue  # o fundo seria uma moldura gigante no preview
                    info.views.append(ViewInfo(vname, float(v.x), float(v.y)))
            except Exception:
                pass
            sheets.append(info)
    except Exception as exc:
        return DrawingSnapshot(
            connected=True, name=name, message=f"Erro ao ler folhas: {exc}")

    # --- parametros ---------------------------------------------------
    params: List[Tuple[str, str]] = []
    try:
        for i in range(1, doc.Parameters.Count + 1):
            p = doc.Parameters.Item(i)
            pn = str(p.Name).rsplit("\\", 1)[-1]
            params.append((pn, str(p.ValueAsString())))
    except Exception:
        pass

    return DrawingSnapshot(
        connected=True, has_drawing=True, name=name, sheets=sheets,
        parameters=params, detected_format=fmt)


if __name__ == "__main__":
    snap = get_snapshot()
    print(f"connected={snap.connected} has_drawing={snap.has_drawing} "
          f"name={snap.name!r} msg={snap.message!r} fmt={snap.detected_format!r} "
          f"sheets={len(snap.sheets)} params={len(snap.parameters)}")
