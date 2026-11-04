"""Font Size Check: confere o tamanho dos textos pelo formato de cada folha.

Porte de sizedetect.txt. A leitura do desenho roda dentro do CATIA
(catia_scripts/font_check.catvbs); a regra e as mensagens ficam aqui.
"""
from __future__ import annotations

import ctypes
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Callable, List, Optional, Tuple

from engine.catia_bridge import CatiaBridge, CatiaError, parse_number

SCRIPT = "font_check.catvbs"
ZOOM_NAVEGADOR = 8  # vezes o zoom da folha inteira
TOLERANCIA = 0.001
MM_POR_POLEGADA = 25.4
TITULO_ANALISE = "E1 - Font Size Analysis"
TITULO_PEDIDO = "E1 - Font Check"
TITULO_RESET = "E1 - Reset"
MENSAGEM_RESET = "Cores restauradas ao padrão do layer."
PERGUNTA_FORMATO = (
    "Não foi possível identificar o formato da folha no Background.\r\n\r\n"
    "Digite um dos formatos: A0, A1, A2, A3, A4, E0, E3 ou 3A0"
)
FORMATO_SUGERIDO = "A0"

_PADROES = {
    "A4": (0.07, 0.125),
    "A3": (0.17, 0.25),
    "A1": (0.17, 0.25),
    "A2": (0.108, 0.193),
    "A0": (0.197, 0.277),
    "E3": (0.197, 0.277),
    "E0": (0.197, 0.277),
    "3A0": (0.197, 0.277),
}


def get_standard_sizes(formato: str) -> Optional[Tuple[float, float]]:
    """Tamanhos padrao (polegadas) do formato, ou None se nao for conhecido."""
    return _PADROES.get(formato.strip(" ").upper())


def normalize_sheet_format(texto: str) -> str:
    for ch in ("\r", "\n", "\t", "\xa0"):
        texto = texto.replace(ch, "")
    return texto.strip(" ").upper()


def format_from_background(textos: List[List[str]]) -> str:
    """Formato da folha: primeiro o Text.68, depois qualquer texto que seja exatamente um formato."""
    for tipo in ("68", "T"):
        for registro in textos:
            if registro[0] == tipo:
                formato = normalize_sheet_format(registro[1])
                if get_standard_sizes(formato):
                    return formato
    return ""


def round_vba(valor: float, casas: int = 4) -> float:
    """Round do VBA: arredonda o valor escalado para o par mais proximo."""
    escala = 10 ** casas
    return round(valor * escala) / escala


def windows_decimal_separator() -> str:
    """Separador decimal do Windows, o mesmo que o VBA usa ao mostrar numeros."""
    LOCALE_SDECIMAL = 0x0E
    buf = ctypes.create_unicode_buffer(8)
    if ctypes.windll.kernel32.GetLocaleInfoEx(None, LOCALE_SDECIMAL, buf, 8):
        return buf.value
    return "."


def is_standard(valor_polegada: float, padroes: Tuple[float, float]) -> bool:
    return any(abs(valor_polegada - p) <= TOLERANCIA for p in padroes)


def format_inch(valor_polegada: float, sep: str) -> str:
    """Format$(valor, "0.000") do VBA, que arredonda 5 para cima."""
    texto = str(Decimal(repr(valor_polegada)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP))
    return texto.replace(".", sep) + '"'


def format_number(valor: float, sep: str) -> str:
    return repr(valor).replace(".", sep)


def clean_item_text(conteudo: str, eh_cota: bool) -> str:
    texto = conteudo.replace("\r", "").replace("\n", " / ")
    if len(texto) > 60:
        texto = texto[:57] + "..."
    return "Cota " + texto if eh_cota else texto


@dataclass
class FontItem:
    """Texto ou cota conferido."""

    sheet_name: str
    view_index: int
    view_name: str
    item_index: int
    item_name: str
    is_dim: bool
    text: str
    size: str
    standard: str
    ok: bool = False
    order: int = 0  # posicao na ordem de leitura do desenho


@dataclass
class FontReport:
    doc_full_name: str
    drawing_no: str
    formats: List[str] = field(default_factory=list)
    standards: List[str] = field(default_factory=list)
    total_items: int = 0
    total_ok: int = 0
    total_nok: int = 0
    items: List[FontItem] = field(default_factory=list)  # fora do padrao
    ok_items: List[FontItem] = field(default_factory=list)
    stopped: bool = False

    @property
    def resumo(self) -> str:
        return (
            f"PN {self.drawing_no}   |   Formato {', '.join(self.formats)}\r\n"
            f"{self.total_nok} fora do padrão de {self.total_items} itens analisados"
        )

    @property
    def mensagem(self) -> str:
        padroes = "".join("\r\n" + p for p in self.standards)
        return (
            "Análise concluída!\r\n\r\n"
            f"PN: {self.drawing_no}\r\n"
            f"Formato: {', '.join(self.formats)}{padroes}\r\n\r\n"
            f"Itens analisados: {self.total_items}\r\n"
            f"Corretos: {self.total_ok}\r\n"
            f"Incorretos: {self.total_nok}"
        )


def _ask_sheet_format(ask_format, warn) -> str:
    """So quando nenhuma folha tem o formato no Background. Cancelar retorna ""."""
    while True:
        formato = normalize_sheet_format(ask_format(PERGUNTA_FORMATO, TITULO_PEDIDO, FORMATO_SUGERIDO) or "")
        if not formato:
            return ""
        if get_standard_sizes(formato):
            return formato
        warn(f"Formato '{formato}' não reconhecido.", TITULO_PEDIDO)


def run_font_inspection(
    bridge: CatiaBridge,
    ask_format: Callable[[str, str, str], Optional[str]],
    warn: Callable[[str, str], None],
    progress: Optional[Callable[[int, int], None]] = None,
    should_stop: Optional[Callable[[], bool]] = None,
    decimal_sep: Optional[str] = None,
) -> Optional[FontReport]:
    """Confere o desenho ativo. Retorna None se o usuario cancelar o pedido de formato."""
    sep = decimal_sep or windows_decimal_separator()
    doc_full_name, drawing_no, total_folhas = bridge.call(SCRIPT, "LerDesenho")[0]
    total_folhas = int(total_folhas)

    formatos_folha = [
        format_from_background(bridge.call(SCRIPT, "LerFundo", i))
        for i in range(1, total_folhas + 1)
    ]
    padrao = next((f for f in formatos_folha if f), "") or _ask_sheet_format(ask_format, warn)
    if not padrao:
        return None

    report = FontReport(doc_full_name, drawing_no)
    for i in range(1, total_folhas + 1):
        if should_stop and should_stop():
            report.stopped = True
            break
        formato = formatos_folha[i - 1] or padrao
        padroes = get_standard_sizes(formato)
        padrao_1 = format_number(padroes[0], sep)
        padrao_2 = format_number(padroes[1], sep)
        if formato not in report.formats:
            report.formats.append(formato)
            report.standards.append(f'Padrões {formato}: {padrao_1}" e {padrao_2}"')
        registros = bridge.call(SCRIPT, "LerFolha", i)
        nome_folha = registros[0][0]
        for registro in registros[1:]:
            if len(registro) < 7:  # folha sem itens: o script manda um registro vazio
                continue
            tipo, i_vista, i_item, mm, nome_item, nome_vista, conteudo = registro
            eh_cota = tipo == "C"
            valor = round_vba(parse_number(mm) / MM_POR_POLEGADA)
            report.total_items += 1
            correto = is_standard(valor, padroes)
            item = FontItem(
                sheet_name=nome_folha,
                view_index=int(i_vista),
                view_name=nome_vista,
                item_index=int(i_item),
                item_name=nome_item,
                is_dim=eh_cota,
                text=clean_item_text(conteudo, eh_cota),
                size=format_inch(valor, sep),
                standard=f'{formato}: {padrao_1}" ou {padrao_2}"',
                ok=correto,
                order=report.total_items,
            )
            if correto:
                report.total_ok += 1
                report.ok_items.append(item)
            else:
                report.total_nok += 1
                report.items.append(item)
        if progress:
            progress(i, total_folhas)
    return report


def go_to_item(bridge: CatiaBridge, report: FontReport, item: FontItem) -> bool:
    """Leva a tela ate o item. Retorna False se ele ou o desenho nao existem mais."""
    try:
        bridge.call(
            SCRIPT, "IrPara", report.doc_full_name, item.sheet_name, item.view_index,
            item.view_name, item.is_dim, item.item_index, item.item_name, ZOOM_NAVEGADOR,
        )
    except CatiaError:
        return False
    return True


def reset_colors(bridge: CatiaBridge) -> bool:
    """Restaura as cores brancas para preto. Retorna False se nao ha desenho ativo."""
    return bridge.call(SCRIPT, "RestaurarCores")[0][0] == "1"
