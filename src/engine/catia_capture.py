"""Captura a folha ativa do CATDrawing aberto como imagem, para o preview.

Usa Viewer.CaptureToFile (automacao CATIA V5): reflete fielmente o que o
CATIA mostra. Quando nao ha CATIA/desenho ou a captura falha, retorna None e
a UI cai no preview esquematico.
"""
from __future__ import annotations

import os
import tempfile
from typing import Optional

from engine.documento import eh_desenho

# (valor do enum CatCaptureFormat, extensao). Tenta em ordem ate gerar arquivo.
_CAPTURE_FORMATS = ((4, "png"), (3, "jpg"), (0, "bmp"), (5, "tif"))


def _temp_path(ext: str) -> str:
    return os.path.join(tempfile.gettempdir(), f"dwg_sheet_preview.{ext}")


def get_active_sheet_name() -> Optional[str]:
    """Nome da folha ativa no CATIA (para sincronizar o seletor), ou None."""
    try:
        from engine.update_template import get_running_catia
        app = get_running_catia()
        if app.Documents.Count == 0:
            return None
        doc = app.ActiveDocument
        if not eh_desenho(doc.Name):
            return None
        return str(doc.Sheets.ActiveSheet.Name)
    except Exception:
        return None


def capture_active_sheet(sheet_name: Optional[str] = None) -> Optional[str]:
    """Ativa a folha indicada (se houver), reenquadra e captura a tela.

    Retorna o caminho do arquivo de imagem gerado ou None.
    """
    try:
        from engine.update_template import get_running_catia
        app = get_running_catia()
        if app.Documents.Count == 0:
            return None
        doc = app.ActiveDocument
        if not eh_desenho(doc.Name):
            return None

        # Ativa a folha selecionada no HUB (reflete a folha escolhida).
        if sheet_name:
            try:
                sheets = doc.Sheets
                for i in range(1, sheets.Count + 1):
                    if str(sheets.Item(i).Name) == sheet_name:
                        sheets.Item(i).Activate()
                        break
            except Exception:
                pass

        viewer = app.ActiveWindow.ActiveViewer
        try:
            viewer.Reframe()  # centraliza/enquadra o conteudo
        except Exception:
            pass

        for fmt, ext in _CAPTURE_FORMATS:
            path = _temp_path(ext)
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass
            try:
                viewer.CaptureToFile(fmt, path)
            except Exception:
                continue
            if os.path.exists(path) and os.path.getsize(path) > 0:
                return path
        return None
    except Exception:
        return None
