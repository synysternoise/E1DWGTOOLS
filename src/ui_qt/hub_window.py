"""Janela do HUB em PySide6, seguindo o prototipo em design/hub_prototipo.html.

Cada ferramenta so entra aqui depois de passar pela comparacao com a macro (ver MIGRACAO.md).
O Symbol Shape continua no painel VBA, porque o codigo dele (CATMain11) nao esta disponivel.
"""
from __future__ import annotations

import os

from PySide6.QtCore import QCoreApplication, QEvent, QPoint, Qt, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget,
)

from ui_qt import theme as T
from ui_qt.catia_worker import CatiaWorker
from ui_qt.fix_flags_page import FixFlagsPage
from ui_qt.font_size_page import FontSizePage, button, label
from ui_qt.tool_pages import PosZonePage, Split2DPage, Split3DPage, UpdateTemplatePage

LARGURA, ALTURA = 1180, 720
LARGURA_COMPACTA = 460
INTERVALO_STATUS_MS = 2000
AINDA_NO_VBA = "Esta ferramenta ainda roda no painel VBA."
ABA_DESIGN, ABA_CHECK, ABA_ENVIO = range(3)
PAGINA_FONT, PAGINA_VBA, PAGINA_FLAGS, PAGINA_UPDATE, PAGINA_POSZONE, PAGINA_SPLIT3D, PAGINA_SPLIT2D = range(7)


def _so_a_atual_conta(pilha: QStackedWidget) -> None:
    """So a pagina visivel entra na largura minima: as escondidas guardam um minimo antigo."""

    def ajustar(atual: int) -> None:
        for i in range(pilha.count()):
            politica = QSizePolicy.Preferred if i == atual else QSizePolicy.Ignored
            pilha.widget(i).setSizePolicy(politica, politica)

    pilha.currentChanged.connect(ajustar)
    ajustar(pilha.currentIndex())


class Header(QFrame):
    """Cabecalho: arrastar por ele move a janela, que nao tem moldura."""

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.window().windowHandle().startSystemMove()


class HubWindow(QWidget):
    request_poll = Signal()
    request_analyze = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("janela")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setWindowTitle("DWG Tools")
        self.setStyleSheet(T.QSS)
        self._compact = False
        self._normal_geometry = None

        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        col.addWidget(self._build_header())
        acento = QFrame()
        acento.setObjectName("acento")
        acento.setFixedHeight(2)
        col.addWidget(acento)

        corpo = QHBoxLayout()
        corpo.setContentsMargins(12, 12, 12, 12)
        corpo.setSpacing(12)
        self.font_page = FontSizePage()
        self.flags_page = FixFlagsPage()
        self.update_page = UpdateTemplatePage()
        self.poszone_page = PosZonePage()
        self.split3d_page = Split3DPage()
        self.split2d_page = Split2DPage()
        self.tool_pages = {
            p.TOOL: p for p in (self.update_page, self.poszone_page, self.split3d_page, self.split2d_page)
        }
        self.rail_buttons = {}
        self._aba_pagina = {ABA_DESIGN: PAGINA_UPDATE, ABA_CHECK: PAGINA_FONT, ABA_ENVIO: PAGINA_SPLIT3D}
        self._rail = QStackedWidget()
        self._rail.setFixedWidth(240)
        self._rail.addWidget(self._build_rail(
            ABA_DESIGN, "DESIGN", (("Update Template", PAGINA_UPDATE), ("Fix Flags", PAGINA_FLAGS)), ("Symbol Shape",),
            "As ferramentas de Design alteram o desenho. O Symbol Shape segue no painel VBA por enquanto.",
        ))
        self._rail.addWidget(self._build_rail(
            ABA_CHECK, "CHECK", (("Font Size Check", PAGINA_FONT), ("Position and Zone", PAGINA_POSZONE)),
            ("Check de Flags", "Compare DWG"),
            "O Check não altera o desenho. As demais ferramentas seguem no painel VBA por enquanto.",
        ))
        self._rail.addWidget(self._build_rail(
            ABA_ENVIO, "ENVIO", (("Split 3D", PAGINA_SPLIT3D), ("Split 2D", PAGINA_SPLIT2D)), (),
            "Os Splits criam arquivos novos. O documento aberto não é dividido.",
        ))
        self._rail.setCurrentIndex(ABA_CHECK)
        corpo.addWidget(self._rail)
        painel = QFrame()
        painel.setObjectName("painel")
        painel_col = QVBoxLayout(painel)
        painel_col.setContentsMargins(0, 0, 0, 0)
        self._pages = QStackedWidget()
        self._pages.addWidget(self.font_page)
        self._pages.addWidget(self._build_placeholder())
        self._pages.addWidget(self.flags_page)
        self._pages.addWidget(self.update_page)
        self._pages.addWidget(self.poszone_page)
        self._pages.addWidget(self.split3d_page)
        self._pages.addWidget(self.split2d_page)
        _so_a_atual_conta(self._pages)
        for pagina in (self.font_page, self.flags_page, *self.tool_pages.values()):
            _so_a_atual_conta(pagina._stack)
        painel_col.addWidget(self._pages)
        corpo.addWidget(painel, 1)
        col.addLayout(corpo, 1)
        self.resize(LARGURA, ALTURA)

        self._start_worker()

    # ------------------------------------------------------------------
    # Montagem
    # ------------------------------------------------------------------
    def _build_header(self) -> QFrame:
        bar = Header()
        bar.setObjectName("cabecalho")
        bar.setFixedHeight(66)
        h = QHBoxLayout(bar)
        h.setContentsMargins(18, 0, 0, 0)
        h.setSpacing(8)

        selo = label("E1", "selo")
        selo.setFixedSize(42, 42)
        selo.setAlignment(Qt.AlignCenter)
        h.addWidget(selo)
        nomes = QVBoxLayout()
        nomes.setSpacing(0)
        nomes.addStretch(1)
        nomes.addWidget(label("DWG TOOLS", "marca"))
        self._brand_sub = label("DESIGN ASSURANCE HUB", "marcaSub")
        nomes.addWidget(self._brand_sub)
        nomes.addStretch(1)
        h.addSpacing(3)
        h.addLayout(nomes)
        h.addStretch(1)

        self._pills = QFrame()
        self._pills.setObjectName("pilulas")
        p = QHBoxLayout(self._pills)
        p.setContentsMargins(5, 5, 5, 5)
        p.setSpacing(4)
        grupo = QButtonGroup(self)
        self.pills = {}
        for i, nome in enumerate(("Design", "Check", "Envio")):
            b = button(nome, "pilula")
            b.setCheckable(True)
            b.setChecked(nome == "Check")
            grupo.addButton(b, i)
            p.addWidget(b)
            self.pills[nome] = b
        grupo.idClicked.connect(self._on_tab)
        h.addWidget(self._pills)
        h.addStretch(1)

        self.chip_catia = label("●  CATIA fechado", "chip")
        self.chip_catia.setFixedHeight(28)
        self.chip_doc = label("Nenhum desenho", "chip")
        self.chip_doc.setFixedHeight(28)
        h.addWidget(self.chip_catia)
        h.addWidget(self.chip_doc)

        self.btn_compact = button("◧", "janelaBtn")
        self.btn_compact.setFixedSize(40, 66)
        self.btn_compact.setToolTip("Modo compacto: fica ao lado do CATIA, sempre visível")
        self.btn_compact.clicked.connect(self.toggle_compact)
        h.addWidget(self.btn_compact)
        fechar = button("✕", "fecharBtn")
        fechar.setFixedSize(44, 66)
        fechar.clicked.connect(self.close)
        h.addWidget(fechar)
        return bar

    def _build_rail(self, aba: int, secao: str, ferramentas: tuple, no_vba: tuple, texto_nota: str) -> QFrame:
        rail = QFrame()
        rail.setObjectName("painel")
        col = QVBoxLayout(rail)
        col.setContentsMargins(12, 14, 12, 12)
        col.setSpacing(4)
        col.addWidget(label(secao, "secao"))
        col.addSpacing(6)
        grupo = QButtonGroup(rail)
        for i, (nome, pagina) in enumerate(ferramentas):
            b = button(nome, "trilho")
            b.setCheckable(True)
            b.setChecked(i == 0)
            grupo.addButton(b)
            b.clicked.connect(lambda _=False, a=aba, p=pagina: self._on_tool(a, p))
            col.addWidget(b)
            self.rail_buttons[nome] = b
        for nome in no_vba:
            b = button(nome, "trilho")
            b.setEnabled(False)
            b.setToolTip(AINDA_NO_VBA)
            col.addWidget(b)
        col.addStretch(1)
        nota = QFrame()
        nota.setObjectName("nota")
        n = QVBoxLayout(nota)
        n.setContentsMargins(10, 8, 10, 8)
        t = label(texto_nota, "notaTexto")
        t.setWordWrap(True)
        n.addWidget(t)
        col.addWidget(nota)
        return rail

    def _on_tab(self, aba: int) -> None:
        self._rail.setCurrentIndex(aba)
        self._pages.setCurrentIndex(self._aba_pagina[aba])

    def _on_tool(self, aba: int, pagina: int) -> None:
        self._aba_pagina[aba] = pagina
        self._pages.setCurrentIndex(pagina)

    def _build_placeholder(self) -> QWidget:
        w = QWidget()
        col = QVBoxLayout(w)
        col.addStretch(1)
        t = label("Ainda no painel VBA", "titulo")
        t.setAlignment(Qt.AlignCenter)
        s = label("Cada ferramenta passa para cá só depois de dar o mesmo resultado que a macro atual.", "sub")
        s.setAlignment(Qt.AlignCenter)
        s.setWordWrap(True)
        col.addWidget(t)
        col.addWidget(s)
        col.addStretch(2)
        return w

    # ------------------------------------------------------------------
    # Thread do CATIA
    # ------------------------------------------------------------------
    def _start_worker(self) -> None:
        self._thread = QThread(self)
        self.worker = CatiaWorker()
        self.worker.moveToThread(self._thread)
        pg, wk = self.font_page, self.worker

        self.request_poll.connect(wk.poll)
        pg.analyze_requested.connect(wk.analyze)
        pg.retry_requested.connect(wk.poll)
        pg.go_requested.connect(wk.go_to)
        # Estes tres so mudam um valor protegido: rodam direto, mesmo com a thread ocupada.
        pg.stop_requested.connect(wk.request_stop, Qt.DirectConnection)
        pg.latest_nav.connect(wk.mark_latest_nav, Qt.DirectConnection)
        pg.format_answered.connect(wk.answer_format, Qt.DirectConnection)

        wk.status.connect(self._on_status)
        wk.started_analysis.connect(pg.on_analysis_started)
        wk.progress.connect(pg.on_progress)
        wk.report_ready.connect(pg.on_report)
        wk.failed.connect(pg.on_failed)
        wk.nav_done.connect(pg.on_nav_done)
        wk.ask_format.connect(pg.on_ask_format)
        wk.warn.connect(pg.on_warn)

        fl = self.flags_page
        fl.run_requested.connect(wk.fix_flags)
        fl.retry_requested.connect(wk.poll)
        fl.go_requested.connect(wk.go_to_flag)
        fl.stop_requested.connect(wk.request_stop, Qt.DirectConnection)
        fl.latest_nav.connect(wk.mark_latest_flag_nav, Qt.DirectConnection)
        fl.confirm_answered.connect(wk.answer_confirm, Qt.DirectConnection)
        wk.flags_started.connect(fl.on_started)
        wk.flags_progress.connect(fl.on_progress)
        wk.flags_ready.connect(fl.on_report)
        wk.flags_failed.connect(fl.on_failed)
        wk.flags_nav_done.connect(fl.on_nav_done)
        wk.flags_confirm.connect(fl.on_ask_confirm)
        wk.flags_warn.connect(fl.on_warn)

        for pagina in self.tool_pages.values():
            pagina.run_requested.connect(wk.run_tool)
            pagina.retry_requested.connect(wk.poll)
            pagina.stop_requested.connect(wk.request_stop, Qt.DirectConnection)
            pagina.answered.connect(wk.answer_format, Qt.DirectConnection)
        # Metodos da janela, nao lambdas: um lambda rodaria na thread do CATIA e mexeria na tela.
        wk.tool_started.connect(self._on_tool_started)
        wk.tool_progress.connect(self._on_tool_progress)
        wk.tool_status.connect(self._on_tool_status)
        wk.tool_ready.connect(self._on_tool_ready)
        wk.tool_failed.connect(self._on_tool_failed)
        wk.tool_ask.connect(self._on_tool_ask)
        wk.tool_warn.connect(self._on_tool_warn)
        wk.tool_info.connect(self._on_tool_info)

        self._thread.start()
        self._timer = QTimer(self)
        self._timer.setInterval(INTERVALO_STATUS_MS)
        self._timer.timeout.connect(self.request_poll)
        self._timer.start()
        self.request_poll.emit()

    @Slot(str)
    def _on_tool_started(self, tool: str) -> None:
        self.tool_pages[tool].on_started()

    @Slot(str, int, int)
    def _on_tool_progress(self, tool: str, atual: int, total: int) -> None:
        self.tool_pages[tool].on_progress(atual, total)

    @Slot(str, str)
    def _on_tool_status(self, tool: str, texto: str) -> None:
        self.tool_pages[tool].on_status(texto)

    @Slot(str, object)
    def _on_tool_ready(self, tool: str, report) -> None:
        self.tool_pages[tool].on_ready(report)

    @Slot(str, str, object)
    def _on_tool_failed(self, tool: str, mensagem: str, report) -> None:
        self.tool_pages[tool].on_failed(mensagem, report)

    @Slot(str, str, str, str)
    def _on_tool_ask(self, tool: str, pergunta: str, titulo: str, sugestao: str) -> None:
        self.tool_pages[tool].on_ask(pergunta, titulo, sugestao)

    @Slot(str, str, str)
    def _on_tool_warn(self, tool: str, mensagem: str, titulo: str) -> None:
        self.tool_pages[tool].on_warn(mensagem, titulo)

    @Slot(str, str, str)
    def _on_tool_info(self, tool: str, mensagem: str, titulo: str) -> None:
        self.tool_pages[tool].on_info(mensagem, titulo)

    def _on_status(self, connected: bool, document: str) -> None:
        self.chip_catia.setText("●  CATIA ativo" if connected else "●  CATIA fechado")
        self.chip_catia.setStyleSheet(f"color: {T.GREEN if connected else T.RED};")
        self.chip_doc.setText(document or "Nenhum desenho")
        self.font_page.set_catia_state(connected, document)
        self.flags_page.set_catia_state(connected, document)
        for pagina in self.tool_pages.values():
            pagina.set_catia_state(connected, document)

    # ------------------------------------------------------------------
    # Modo compacto
    # ------------------------------------------------------------------
    def toggle_compact(self) -> None:
        self._compact = not self._compact
        if self._compact:
            self._normal_geometry = self.geometry()
        for w in (self._rail, self._pills, self._brand_sub, self.chip_doc):
            w.setVisible(not self._compact)
        self.font_page.set_compact(self._compact)
        self.flags_page.set_compact(self._compact)
        for pagina in self.tool_pages.values():
            pagina.set_compact(self._compact)
        self.layout().activate()
        self.setWindowFlag(Qt.WindowStaysOnTopHint, self._compact)
        self.btn_compact.setToolTip("Voltar ao tamanho normal" if self._compact else "Modo compacto: fica ao lado do CATIA, sempre visível")
        # Mudar a opcao recria a janela do Windows: o tamanho so vale depois de ela se reorganizar.
        self.show()
        QTimer.singleShot(0, self._apply_mode_geometry)

    def _apply_mode_geometry(self) -> None:
        # Os layouts internos ainda nao recalcularam o minimo depois de esconder os widgets.
        # O pedido sobe um nivel de cada vez, da pagina ate a janela.
        for _ in range(4):
            QCoreApplication.sendPostedEvents(None, QEvent.LayoutRequest)
        self.layout().activate()
        if self._compact:
            area = (self.screen() or QGuiApplication.primaryScreen()).availableGeometry()
            self.setGeometry(area.right() - LARGURA_COMPACTA + 1, area.top(), LARGURA_COMPACTA, area.height())
        else:
            self.setGeometry(self._normal_geometry)

    def closeEvent(self, event) -> None:
        self._timer.stop()
        self.worker.request_stop()
        self.worker.answer_format("")
        self.worker.answer_confirm(False)
        self._thread.quit()
        if not self._thread.wait(5000):
            # O CATIA nao respondeu: nao segura o HUB aberto por causa dele.
            os._exit(0)
        super().closeEvent(event)
