"""Symbol Shape Converter: troca a ponta dos leaders dos textos pelo simbolo cheio.

Porte de vba/symbolconvert.txt (CATMain11). A regra e a mesma da macro:
circulo transparente, circulo vazado e onda viram circulo cheio; seta vazada vira seta cheia.
So os leaders de textos entram, em todas as vistas de todas as folhas.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Tuple

from engine.catia_bridge import CatiaBridge, CatiaError

SCRIPT = "symbol_shape.catvbs"
TITULO_FEITO = "Update Completed"
TITULO_NADA = "Update"
NAO_E_DESENHO = 1002


@dataclass
class SymbolReport:
    doc_full_name: str
    sheets: List[Tuple[str, int, int, int]] = field(default_factory=list)  # folha, circulos, setas, leaders lidos

    @property
    def doc_name(self) -> str:
        return os.path.basename(self.doc_full_name)

    @property
    def circulos(self) -> int:
        return sum(s[1] for s in self.sheets)

    @property
    def setas(self) -> int:
        return sum(s[2] for s in self.sheets)

    @property
    def leaders(self) -> int:
        return sum(s[3] for s in self.sheets)

    @property
    def convertidos(self) -> int:
        return self.circulos + self.setas

    @property
    def mensagem(self) -> str:
        """O mesmo texto da janela da macro."""
        if self.convertidos > 0:
            return f"{self.convertidos} símbolo(s) convertido(s) com sucesso."
        return "Nenhum símbolo passível de conversão foi encontrado."


def run_symbol_shape(bridge: CatiaBridge) -> SymbolReport:
    """Converte o desenho inteiro numa chamada so: cada ida ao CATIA custa mais que a conversao."""
    try:
        registros = bridge.call(SCRIPT, "Converter")
    except CatiaError as exc:
        if exc.number == NAO_E_DESENHO:  # o texto da macro, com acento
            raise CatiaError("O documento ativo não é um Drawing.", exc.number) from exc
        raise
    report = SymbolReport(registros[0][0])
    for nome, circulos, setas, lidos in registros[1:]:
        report.sheets.append((nome, int(circulos), int(setas), int(lidos)))
    return report
