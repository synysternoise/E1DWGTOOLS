"""Thread que fala com o CATIA, para a janela nunca travar enquanto ele trabalha.

Toda chamada COM acontece aqui. A janela pede por sinais e recebe por sinais.
"""
from __future__ import annotations

import threading
from typing import Optional

import pywintypes
from PySide6.QtCore import QObject, Signal, Slot

from engine import atualizar_template as at
from engine import fix_flags as ff
from engine import font_check as fc
from engine import pos_zone as pz
from engine import splits as sp
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

    flags_started = Signal()
    flags_progress = Signal(int, int)
    flags_ready = Signal(object)  # FixReport, ou None se nao havia desenho ou respondeu Nao
    flags_failed = Signal(str, object)  # mensagem, FixReport com o que ja foi feito (ou None)
    flags_nav_done = Signal(int, bool)
    flags_confirm = Signal(str, str)  # mensagem, titulo
    flags_warn = Signal(str, str)

    # Update Template, Position and Zone e Splits: o primeiro campo e o nome da ferramenta.
    tool_started = Signal(str)
    tool_progress = Signal(str, int, int)
    tool_status = Signal(str, str)
    tool_ready = Signal(str, object)
    tool_failed = Signal(str, str, object)  # mensagem e o que ja foi feito (ou None)
    tool_ask = Signal(str, str, str, str)  # pergunta, titulo, sugestao
    tool_warn = Signal(str, str, str)
    tool_info = Signal(str, str, str)

    def __init__(self):
        super().__init__()
        self._bridge: Optional[CatiaBridge] = None
        self._stop = threading.Event()
        self._answer_ready = threading.Event()
        self._answer = ""
        self._last_nav = 0
        self._confirm_ready = threading.Event()
        self._confirmed = False
        self._last_flag_nav = 0

    # Chamados da thread da janela.
    def request_stop(self) -> None:
        self._stop.set()

    def answer_format(self, text: str) -> None:
        self._answer = text
        self._answer_ready.set()

    def mark_latest_nav(self, request: int) -> None:
        self._last_nav = request

    def answer_confirm(self, yes: bool) -> None:
        self._confirmed = yes
        self._confirm_ready.set()

    def mark_latest_flag_nav(self, request: int) -> None:
        self._last_flag_nav = request

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

    @Slot(str)
    def run_tool(self, tool: str) -> None:
        self._stop.clear()
        self.tool_started.emit(tool)

        def perguntar(pergunta: str, titulo: str, sugestao: str) -> str:
            self._answer_ready.clear()
            self.tool_ask.emit(tool, pergunta, titulo, sugestao)
            self._answer_ready.wait()
            return self._answer

        def progresso(atual: int, total: int) -> None:
            self.tool_progress.emit(tool, atual, total)

        def situacao(texto: str) -> None:
            self.tool_status.emit(tool, texto)

        try:
            ponte = self._get_bridge()
            if tool == "update":
                report = at.run_update_template(ponte, perguntar, status=situacao, progress=progresso)
            elif tool == "poszone":
                report = pz.run_pos_zone(ponte, lambda m, t: self.tool_warn.emit(tool, m, t), progress=progresso)
                if report is not None:
                    # O Excel fica aberto para o usuario; o objeto COM nao pode sair desta thread.
                    report.xl_app = report.xl_book = None
            elif tool == "split2d":
                report = sp.run_split_2d(
                    ponte,
                    lambda m: self.tool_warn.emit(tool, m, "Split 2D"),
                    lambda m: self.tool_info.emit(tool, m, "Split 2D"),
                    progress=progresso,
                    should_stop=self._stop.is_set,
                )
            elif tool == "split3d":
                report = sp.run_split_3d(
                    ponte,
                    perguntar,
                    lambda m: self.tool_warn.emit(tool, m, "Split 3D"),
                    progress=progresso,
                    should_stop=self._stop.is_set,
                )
            else:
                raise CatiaError(f"Ferramenta desconhecida: {tool}")
        except (at.TemplateError, pz.PosZoneError, sp.SplitError) as exc:
            self._bridge = None
            self.tool_failed.emit(tool, exc.mensagem, exc.report)
            return
        except CatiaError as exc:
            self._bridge = None
            self.tool_failed.emit(tool, str(exc), None)
            return
        self.tool_ready.emit(tool, report)

    def _confirm(self, message: str, title: str) -> bool:
        self._confirm_ready.clear()
        self.flags_confirm.emit(message, title)
        self._confirm_ready.wait()
        return self._confirmed

    @Slot()
    def fix_flags(self) -> None:
        self._stop.clear()
        self.flags_started.emit()
        try:
            report = ff.run_fix_flags(
                self._get_bridge(),
                self._confirm,
                self.flags_warn.emit,
                progress=self.flags_progress.emit,
                should_stop=self._stop.is_set,
            )
        except ff.FixInterrompido as exc:
            self._bridge = None
            self.flags_failed.emit(exc.mensagem, exc.report)
            return
        except CatiaError as exc:
            self._bridge = None
            self.flags_failed.emit(ff.FixInterrompido(str(exc), exc.number).mensagem, None)
            return
        self.flags_ready.emit(report)

    @Slot(object, object, int)
    def go_to_flag(self, report, item, request: int) -> None:
        if request != self._last_flag_nav:
            return
        try:
            ok = ff.go_to_flag(self._get_bridge(), report, item)
        except CatiaError:
            self._bridge = None
            ok = False
        self.flags_nav_done.emit(request, ok)
