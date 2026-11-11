"""Icones do prototipo (design/hub_prototipo.html), desenhados na cor pedida."""
from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

_FORMAS = {
    "check": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    "pencil": '<path d="M4 20l1-4L16 5l3 3L8 19l-4 1zM14 7l3 3"/>',
    "shield": '<path d="M12 3l7.5 3v5.5c0 4.5-3 8-7.5 9.5-4.5-1.5-7.5-5-7.5-9.5V6z"/><path d="M8.8 12l2.3 2.3 4.2-4.3"/>',
    "flow": '<circle cx="5" cy="6" r="2.5"/><circle cx="19" cy="18" r="2.5"/><path d="M7.5 6H15a3 3 0 010 6H9a3 3 0 000 6h7.5"/>',
    "left": '<path d="M15 5l-7 7 7 7"/>',
    "right": '<path d="M9 5l7 7-7 7"/>',
    "x": '<path d="M6 6l12 12M18 6L6 18"/>',
    "alert": '<path d="M12 4l9.5 16.5h-19zM12 10v4.5M12 17.5h.01"/>',
    "dock": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M15 4v16"/>',
    "refresh": '<path d="M20 12a8 8 0 11-2.4-5.7M20 3.5V8h-4.5"/>',
    "play": '<path d="M7 4.5l12 7.5-12 7.5z" fill="currentColor"/>',
    "stop": '<rect x="6" y="6" width="12" height="12" rx="1.5"/>',
    "sheet": '<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M4 9h16M4 15h16M12 3v18"/>',
    "open": '<path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 01-1 1H5a1 1 0 01-1-1V7a1 1 0 011-1h5"/>',
    "minus": '<path d="M6 12h12"/>',
    "flag": '<path d="M6 21V4h13l-3.5 4 3.5 4H6"/>',
    "arrow": '<path d="M21 3L3 10.5l7.5 3L14 21z"/>',
    "box": '<rect x="3.5" y="3.5" width="17" height="17" rx="2"/><path d="M8 12.5l3 3 5.5-6.5"/>',
    "monitor": '<rect x="3" y="4" width="18" height="13" rx="1.5"/><path d="M8 21h8M12 17v4M8 13l3-5 3 3 2-2"/>',
    "file": '<path d="M7 3h7l5 5v13H7zM14 3v5h5"/>',
    "saw": '<path d="M2 8h13v5l-2 3-1.5-3-2 3L8 13l-2 3-1.5-3-2 3zM15 6h5a2 2 0 012 2v4a2 2 0 01-2 2h-5zM18.5 9v2"/>',
    "scissors": '<circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M20 4L8.2 15.8M14.5 14.5L20 20M8.2 8.2L12 12"/>',
    "send": '<path d="M12 16V4M7 9l5-5 5 5M4 20h16"/>',
    "expand": '<rect x="3" y="4" width="18" height="16" rx="2"/>',
    "rail": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M18 4v16"/>',
    # Aviao visto de cima, apontando para o canto: asa enflechada e dois motores sob as asas.
    "plane": '<g transform="rotate(45 12 12)" stroke="none" fill="currentColor">'
             '<path d="M12 1.5c.9 0 1.3 1.6 1.3 3.2V9l9 5.2v1.6l-9-2.3v5l3 2.2v1.3L12 21l-4.3 1v-1.3l3-2.2v-5l-9 2.3v-1.6l9-5.2V4.7'
             'c0-1.6.4-3.2 1.3-3.2z"/><rect x="6.5" y="9.3" width="1.6" height="2.7" rx=".7"/>'
             '<rect x="15.9" y="9.3" width="1.6" height="2.7" rx=".7"/></g>',
    # Aviao de lado, voando para a direita: e o que percorre a barra de progresso.
    "jet": '<g transform="translate(0 6.7) scale(0.706)" stroke="none" fill="currentColor">'
           '<path d="M3 7L1 1h3.2L9 7z"/><path d="M2 9q0-2.2 3-2.2h19q5.5 0 8 2.7-2.5 1.7-8 1.7H5Q2 11.2 2 9z"/>'
           '<path d="M14 10L9.5 14.5h3.3L20 10z"/><rect x="15" y="11" width="5" height="2.4" rx="1.2"/></g>',
}


@lru_cache(maxsize=256)
def pixmap(nome: str, cor: str, tamanho: int = 18, traco: float = 2.0) -> QPixmap:
    forma = _FORMAS[nome].replace("currentColor", cor)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{cor}" '
        f'stroke-width="{traco}" stroke-linecap="round" stroke-linejoin="round">{forma}</svg>'
    )
    escala = 2  # nitido em telas com zoom
    px = QPixmap(tamanho * escala, tamanho * escala)
    px.fill(Qt.transparent)
    pintor = QPainter(px)
    QSvgRenderer(QByteArray(svg.encode("ascii"))).render(pintor, QRectF(0, 0, tamanho * escala, tamanho * escala))
    pintor.end()
    px.setDevicePixelRatio(escala)
    return px


def _com_folga(px: QPixmap, folga: int) -> QPixmap:
    """Espaco dos dois lados do desenho: o Qt encosta o icone no texto do botao."""
    if not folga:
        return px
    escala = int(px.devicePixelRatio())
    novo = QPixmap(px.width() + 2 * folga * escala, px.height())
    novo.fill(Qt.transparent)
    pintor = QPainter(novo)
    px2 = QPixmap(px)
    px2.setDevicePixelRatio(1)
    pintor.drawPixmap(folga * escala, 0, px2)
    pintor.end()
    novo.setDevicePixelRatio(escala)
    return novo


def icone(nome: str, cor: str, tamanho: int = 18, cor_desligado: str = "", folga: int = 0) -> QIcon:
    ic = QIcon(_com_folga(pixmap(nome, cor, tamanho), folga))
    if cor_desligado:
        ic.addPixmap(_com_folga(pixmap(nome, cor_desligado, tamanho), folga), QIcon.Disabled)
    return ic
