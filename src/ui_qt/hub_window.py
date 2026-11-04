"""Janela do HUB em PySide6, seguindo o prototipo em design/hub_prototipo.html.

Por enquanto so o Font Size Check e o Fix Flags estao aqui; as demais ferramentas
continuam no painel VBA ate passarem pela comparacao (ver MIGRACAO.md).
"""
from __future__ import annotations

import os

from PySide6.QtCore import QCoreApplication, QEvent, QPoint, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QLabel, QPushButton, QStackedWidget, QVBoxLayout, QWidget,
)

from ui_qt import theme as T
from ui_qt.catia_worker import CatiaWorker
from ui_qt.fix_flags_page import FixFlagsPage
from ui_qt.font_size_page import FontSizePage, button, label

LARGURA, ALTURA = 1180, 720
LARGURA_COMPACTA = 460
INTERVALO_STATUS_MS = 2000
AINDA_NO_VBA = "Esta ferramenta ainda roda no painel VBA."
ABA_DESIGN, ABA_CHECK, ABA_ENVIO = range(3)
PAGINA_FONT, PAGINA_VBA, PAGINA_FLAGS = range(3)
PAGINA_DA_ABA = {ABA_DESIGN: PAGINA_FLAGS, ABA_CHECK: PAGINA_FONT, ABA_ENVIO: PAGINA_VBA}


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
        self._rail = QStackedWidget()
        self._rail.setFixedWidth(240)
        self._rail.addWidget(self._build_rail(
            "DESIGN", "Fix Flags", ("Update Template", "Symbol Shape"),
            "O Fix Flags altera o desenho. As demais ferramentas seguem no painel VBA por enquanto.",
        ))
        self._rail.addWidget(self._build_rail(
            "CHECK", "Font Size Check", ("Position and Zone", "Check de Flags", "Compare DWG"),
            "O Check não altera o desenho. As demais ferramentas seguem no painel VBA por enquanto.",
        ))
        self._rail.addWidget(self._build_rail(
            "ENVIO", "", ("Split 3D", "Split 2D"),
            "As ferramentas de envio seguem no painel VBA por enquanto.",
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

    def _build_rail(self, secao: str, ativa: str, no_vba: tuple, texto_nota: str) -> QFrame:
        rail = QFrame()
        rail.setObjectName("painel")
        col = QVBoxLayout(rail)
        col.setContentsMargins(12, 14, 12, 12)
        col.setSpacing(4)
        col.addWidget(label(secao, "secao"))
        col.addSpacing(6)
        if ativa:
            atual = button(ativa, "trilho")
            atual.setCheckable(True)
            atual.setChecked(True)
            col.addWidget(atual)
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
        self._pages.setCurrentIndex(PAGINA_DA_ABA[aba])

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

        self._thread.start()
        self._timer = QTimer(self)
        self._timer.setInterval(INTERVALO_STATUS_MS)
        self._timer.timeout.connect(self.request_poll)
        self._timer.start()
        self.request_poll.emit()

    def _on_status(self, connected: bool, document: str) -> None:
        self.chip_catia.setText("●  CATIA ativo" if connected else "●  CATIA fechado")
        self.chip_catia.setStyleSheet(f"color: {T.GREEN if connected else T.RED};")
        self.chip_doc.setText(document or "Nenhum desenho")
        self.font_page.set_catia_state(connected, document)
        self.flags_page.set_catia_state(connected, document)

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
