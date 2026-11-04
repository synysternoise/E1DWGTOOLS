"""Thread que fala com o CATIA, para a janela nunca travar enquanto ele trabalha.

Toda chamada COM acontece aqui. A janela pede por sinais e recebe por sinais.
"""
from __future__ import annotations

import threading
from typing import Optional

import pywintypes
from PySide6.QtCore import QObject, Signal, Slot

from engine import font_check as fc
from engine.catia_bridge import CatiaBridge, CatiaError


class CatiaWorker(QObject):
    status = Signal(bool, str)  # conectado, nome do documento ativo ("" se nenhum)
    started_analysis = Signal()
    progress = Signal(int, int)
    report_ready = Signal(object)  # FontReport, ou None se o pedido de formato foi cancelado
    failed = Signal(str)
    nav_done = Signal(int, bool)  # pedido, resultado
    ask_format = Signal(str, str, str)  # pergunta, titulo, sugestao
    warn = Signal(str, str)  # mensagem, titulo

    def __init__(self):
        super().__init__()
        self._bridge: Optional[CatiaBridge] = None
        self._stop = threading.Event()
        self._answer_ready = threading.Event()
        self._answer = ""
        self._last_nav = 0

    # Chamados da thread da janela.
    def request_stop(self) -> None:
        self._stop.set()

    def answer_format(self, text: str) -> None:
        self._answer = text
        self._answer_ready.set()

    def mark_latest_nav(self, request: int) -> None:
        self._last_nav = request

    def _get_bridge(self) -> CatiaBridge:
        if self._bridge is None:
            self._bridge = CatiaBridge()
        return self._bridge

    @Slot()
    def poll(self) -> None:
        try:
            app = self._get_bridge().app
            name = app.ActiveDocument.Name if app.Documents.Count else ""
        except (CatiaError, pywintypes.com_error):
            self._bridge = None
            self.status.emit(False, "")
            return
        self.status.emit(True, name)

    def _ask(self, question: str, title: str, default: str) -> str:
        self._answer_ready.clear()
        self.ask_format.emit(question, title, default)
        self._answer_ready.wait()
        return self._answer

    @Slot()
    def analyze(self) -> None:
        self._stop.clear()
        self.started_analysis.emit()
        try:
            report = fc.run_font_inspection(
                self._get_bridge(),
                self._ask,
                self.warn.emit,
                progress=self.progress.emit,
                should_stop=self._stop.is_set,
            )
        except CatiaError as exc:
            self._bridge = None
            self.failed.emit(str(exc))
            return
        self.report_ready.emit(report)

    @Slot(object, object, int)
    def go_to(self, report, item, request: int) -> None:
        # Cliques seguidos em PROXIMO: so o ultimo pedido precisa mover a tela.
        if request != self._last_nav:
            return
        try:
            ok = fc.go_to_item(self._get_bridge(), report, item)
        except CatiaError:
            self._bridge = None
            ok = False
        self.nav_done.emit(request, ok)
