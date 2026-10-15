"""Ferramenta 2: Trocar Template pelo Background (Método 1).

Reaproveita toda a UI da ferramenta Update Template, trocando apenas o motor:
em vez de mover as views para um template novo, copia o fundo (frame +
etiqueta) do template para o desenho, in-place. Serve para comparar os dois
métodos no serviço.
"""
from __future__ import annotations

from tools.update_template_tool import Tool as _BaseTool

TOOL_NAME = "Trocar Template (BG)"
ORDER = 1


class Tool(_BaseTool):
    HEADER_TITLE = "Trocar Template — Background"
    HEADER_SUBTITLE = "Método 1: copia o fundo (frame + etiqueta) do template"

    def _do_conversion(self, progress_callback, status_callback, format_resolver):
        from engine.swap_background import swap_template_background
        return swap_template_background(
            progress_callback=progress_callback,
            status_callback=status_callback,
            format_resolver=format_resolver)
