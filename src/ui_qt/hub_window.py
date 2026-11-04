"""Janela do HUB em PySide6, seguindo o prototipo em design/hub_prototipo.html.

Cada ferramenta so entra aqui depois de passar pela comparacao com a macro (ver MIGRACAO.md).
O Symbol Shape continua no painel VBA, porque o codigo dele (CATMain11) nao esta disponivel.
"""
from __future__ import annotations

import os

from PySide6.QtCore import QCoreApplication, QEvent, QSize, Qt, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QLabel, QProgressBar, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget,
)

from ui_qt import theme as T
from ui_qt.catia_worker import CatiaWorker
from ui_qt.check_fix_pages import FlagCheckPage, FontSizeFixPage
from ui_qt.fix_flags_page import FixFlagsPage
from ui_qt.font_size_page import FontSizePage, button, label
from ui_qt.icones import icone
from ui_qt.pecas import largura_livre
from ui_qt.sequencia_page import CheckGeralPage, SequenciaPage
from ui_qt.tool_pages import PosZonePage, Split2DPage, Split3DPage, UpdateTemplatePage

LARGURA, ALTURA = 1180, 720
LARGURA_COMPACTA = 460
INTERVALO_STATUS_MS = 2000
AINDA_NO_VBA = "Esta ferramenta ainda roda no painel VBA."
AINDA_NAO_EXISTE = "Esta ferramenta ainda não existe."
ABA_DESIGN, ABA_CHECK, ABA_ENVIO = range(3)
(
    PAGINA_SEQUENCIA, PAGINA_UPDATE, PAGINA_FLAGS, PAGINA_GERAL, PAGINA_FONT, PAGINA_POSZONE, PAGINA_SPLIT3D, PAGINA_SPLIT2D,
    PAGINA_FONTFIX, PAGINA_CHECKFLAGS,
) = range(10)


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
    request_tool = Signal(str)
    request_go = Signal(str, object, object, int)

    def __init__(self):
        super().__init__()
        self.setObjectName("janela")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setWindowTitle("DWG Tools")
        self.setStyleSheet(T.QSS)
        self._compact = False
        self._normal_geometry = None
        self._busy = False
        self._conectado = False
        self._documento = ""

        self.seq_page = SequenciaPage()
        self.update_page = UpdateTemplatePage()
        self.flags_page = FixFlagsPage()
        self.geral_page = CheckGeralPage()
        self.font_page = FontSizePage()
        self.poszone_page = PosZonePage()
        self.split3d_page = Split3DPage()
        self.split2d_page = Split2DPage()
        self.fontfix_page = FontSizeFixPage()
        self.flagcheck_page = FlagCheckPage()
        self.tool_pages = {
            p.TOOL: p for p in (
                self.update_page, self.poszone_page, self.split3d_page, self.split2d_page, self.fontfix_page, self.flagcheck_page,
            )
        }

        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        col.addWidget(self._build_header())
        self.barra_acento = QProgressBar()
        self.barra_acento.setObjectName("acento")
        self.barra_acento.setTextVisible(False)
        self.barra_acento.setFixedHeight(2)
        self.barra_acento.setRange(0, 100)
        self.barra_acento.setValue(100)
        col.addWidget(self.barra_acento)

        corpo = QHBoxLayout()
        corpo.setContentsMargins(12, 12, 12, 12)
        corpo.setSpacing(12)
        self.rail_buttons = {}
        self.rail_badges = {}
        self._aba_pagina = {ABA_DESIGN: PAGINA_SEQUENCIA, ABA_CHECK: PAGINA_GERAL, ABA_ENVIO: PAGINA_SPLIT3D}
        self._rail = QStackedWidget()
        self._rail.setFixedWidth(240)
        self._rail.addWidget(self._build_rail(
            ABA_DESIGN,
            (("APLICAR EM SEQUÊNCIA", (("Sequência de aplicação", "flow", PAGINA_SEQUENCIA, ""),)),
             ("FERRAMENTAS", (("Update Template", "refresh", PAGINA_UPDATE, ""),
                              ("Symbol Shape Converter", "arrow", None, AINDA_NO_VBA),
                              ("Fix Flags", "flag", PAGINA_FLAGS, ""),
                              ("Font Size Fix", "sheet", PAGINA_FONTFIX, "")))),
            "Cada ferramenta também roda sozinha, fora da sequência.",
        ))
        self._rail.addWidget(self._build_rail(
            ABA_CHECK,
            (("CHECK", (("Visão geral", "shield", PAGINA_GERAL, ""),
                        ("Font Size Check", "sheet", PAGINA_FONT, ""),
                        ("Position and Zone", "box", PAGINA_POSZONE, ""),
                        ("Check de Flags", "flag", PAGINA_CHECKFLAGS, ""),
                        ("Compare DWG", "monitor", None, AINDA_NAO_EXISTE))),),
            "O Check não altera o desenho.",
        ))
        self._rail.addWidget(self._build_rail(
            ABA_ENVIO,
            (("PREPARAR PARA ENVIO", (("Split 3D", "saw", PAGINA_SPLIT3D, ""), ("Split 2D", "scissors", PAGINA_SPLIT2D, ""))),),
            "Os Splits criam arquivos novos. O documento aberto não é dividido.",
        ))
        corpo.addWidget(self._rail)

        self._pages = QStackedWidget()
        for pagina in (
            self.seq_page, self.update_page, self.flags_page, self.geral_page, self.font_page,
            self.poszone_page, self.split3d_page, self.split2d_page, self.fontfix_page, self.flagcheck_page,
        ):
            self._pages.addWidget(pagina)
            _so_a_atual_conta(pagina._stack) if hasattr(pagina, "_stack") else None
        _so_a_atual_conta(self._pages)
        corpo.addWidget(self._pages, 1)
        col.addLayout(corpo, 1)
        self.resize(LARGURA, ALTURA)

        self._on_tab(ABA_DESIGN)
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
        self.contagem_check = label("", "contagem")
        self.contagem_check.setFixedHeight(18)
        self.contagem_check.hide()
        for i, (nome, ic) in enumerate((("Design", "pencil"), ("Check", "shield"), ("Envio", "send"))):
            b = button(nome, "pilula")
            b.setIcon(icone(ic, T.TEXT, 15, "", 3))
            b.setIconSize(QSize(21, 15))
            b.setCheckable(True)
            b.setChecked(nome == "Design")
            grupo.addButton(b, i)
            p.addWidget(b)
            self.pills[nome] = b
            if nome == "Check":
                p.addWidget(self.contagem_check)
        grupo.idClicked.connect(self._on_tab)
        h.addWidget(self._pills)
        h.addStretch(1)

        self.chip_catia = label("●  CATIA fechado", "chip")
        self.chip_catia.setFixedHeight(28)
        self.chip_doc = label("Nenhum desenho", "chip")
        self.chip_doc.setFixedHeight(28)
        h.addWidget(self.chip_catia)
        h.addWidget(self.chip_doc)

        self.btn_compact = button("", "janelaBtn")
        self.btn_compact.setIcon(icone("dock", T.MUTED, 16))
        self.btn_compact.setFixedSize(40, 66)
        self.btn_compact.setToolTip("Modo compacto: fica ao lado do CATIA, sempre visível")
        self.btn_compact.clicked.connect(self.toggle_compact)
        h.addWidget(self.btn_compact)
        fechar = button("", "fecharBtn")
        fechar.setIcon(icone("x", T.MUTED, 16))
        fechar.setFixedSize(44, 66)
        fechar.clicked.connect(self.close)
        h.addWidget(fechar)
        return bar

    def _build_rail(self, aba: int, secoes: tuple, texto_nota: str) -> QFrame:
        rail = QFrame()
        rail.setObjectName("painel")
        col = QVBoxLayout(rail)
        col.setContentsMargins(12, 14, 12, 12)
        col.setSpacing(4)
        grupo = QButtonGroup(rail)
        primeiro = True
        for s, (secao, itens) in enumerate(secoes):
            if s:
                col.addSpacing(12)
            col.addWidget(label(secao, "secao"))
            col.addSpacing(6)
            for nome, ic, pagina, dica in itens:
                b = button(nome, "trilho")
                b.setIcon(icone(ic, T.TEXT, 17, T.DIM, 4))
                b.setIconSize(QSize(25, 17))
                if pagina is None:
                    b.setEnabled(False)
                    b.setToolTip(dica)
                else:
                    b.setCheckable(True)
                    b.setChecked(primeiro)
                    primeiro = False
                    grupo.addButton(b)
                    b.clicked.connect(lambda _=False, a=aba, p=pagina: self._on_tool(a, p))
                # Contador dentro do botao, encostado na direita.
                dentro = QHBoxLayout(b)
                dentro.setContentsMargins(0, 0, 10, 0)
                dentro.addStretch(1)
                selo = QLabel("")
                selo.setObjectName("selo2")
                selo.setFixedHeight(18)
                selo.hide()
                dentro.addWidget(selo)
                self.rail_buttons[nome] = b
                self.rail_badges[nome] = selo
                col.addWidget(b)
        col.addStretch(1)
        nota = QFrame()
        nota.setObjectName("nota")
        n = QVBoxLayout(nota)
        n.setContentsMargins(10, 8, 10, 8)
        n.addWidget(largura_livre(label(texto_nota, "notaTexto")))
        col.addWidget(nota)
        return rail

    def _on_tab(self, aba: int) -> None:
        self._rail.setCurrentIndex(aba)
        self._pages.setCurrentIndex(self._aba_pagina[aba])

    def _on_tool(self, aba: int, pagina: int) -> None:
        self._aba_pagina[aba] = pagina
        self._pages.setCurrentIndex(pagina)

    def ir_para(self, aba: int, nome_aba: str, nome_item: str, pagina: int) -> None:
        self.pills[nome_aba].setChecked(True)
        self.rail_buttons[nome_item].setChecked(True)
        self._aba_pagina[aba] = pagina
        self._on_tab(aba)

    # ------------------------------------------------------------------
    # Thread do CATIA
    # ------------------------------------------------------------------
    def _start_worker(self) -> None:
        self._thread = QThread(self)
        self.worker = CatiaWorker()
        self.worker.moveToThread(self._thread)
        pg, wk = self.font_page, self.worker

        self.request_poll.connect(wk.poll)
        self.request_analyze.connect(wk.analyze)
        self.request_tool.connect(wk.run_tool)
        self.request_go.connect(wk.go_to_tool_item)
        pg.analyze_requested.connect(wk.analyze)
        pg.retry_requested.connect(wk.poll)
        pg.go_requested.connect(wk.go_to)
        # Estes so mudam um valor protegido: rodam direto, mesmo com a thread ocupada.
        pg.stop_requested.connect(wk.request_stop, Qt.DirectConnection)
        pg.latest_nav.connect(wk.mark_latest_nav, Qt.DirectConnection)
        pg.format_answered.connect(wk.answer_format, Qt.DirectConnection)

        wk.status.connect(self._on_status)
        wk.busy.connect(self._on_busy)
        wk.started_analysis.connect(pg.on_analysis_started)
        wk.progress.connect(pg.on_progress)
        wk.progress.connect(self._on_any_progress)
        wk.report_ready.connect(pg.on_report)
        wk.report_ready.connect(self._on_font_report)
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
        fl.conferir_requested.connect(self._ir_para_check)
        wk.flags_started.connect(fl.on_started)
        wk.flags_progress.connect(fl.on_progress)
        wk.flags_progress.connect(self._on_any_progress)
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
            pagina.preview_requested.connect(wk.preview)
        self.update_page.formats_changed.connect(wk.set_update_formats, Qt.DirectConnection)
        self.poszone_page.go_requested.connect(self._on_pos_go)
        self.poszone_page.latest_nav.connect(wk.mark_latest_tool_nav, Qt.DirectConnection)
        self.flagcheck_page.go_requested.connect(self._on_flagcheck_go)
        self.flagcheck_page.latest_nav.connect(wk.mark_latest_tool_nav, Qt.DirectConnection)
        self.flagcheck_page.corrigir_requested.connect(self._ir_para_fix_flags)
        self.fontfix_page.go_requested.connect(self._on_fontfix_go)
        self.fontfix_page.latest_nav.connect(wk.mark_latest_tool_nav, Qt.DirectConnection)
        self.fontfix_page.fix_requested.connect(wk.fix_fonts)
        wk.font_fixed.connect(self.fontfix_page.on_fixed)
        # Metodos da janela, nao lambdas: um lambda rodaria na thread do CATIA e mexeria na tela.
        wk.tool_started.connect(self._on_tool_started)
        wk.tool_progress.connect(self._on_tool_progress)
        wk.tool_status.connect(self._on_tool_status)
        wk.tool_ready.connect(self._on_tool_ready)
        wk.tool_failed.connect(self._on_tool_failed)
        wk.tool_ask.connect(self._on_tool_ask)
        wk.tool_warn.connect(self._on_tool_warn)
        wk.tool_info.connect(self._on_tool_info)
        wk.tool_preview.connect(self._on_tool_preview)
        wk.tool_nav_done.connect(self._on_tool_nav)

        sq = self.seq_page
        sq.run_requested.connect(wk.run_sequence)
        sq.stop_requested.connect(wk.request_stop_sequence, Qt.DirectConnection)
        sq.conferir_requested.connect(self._ir_para_check)
        sq.revisar_fontes_requested.connect(self._ir_para_font_fix)
        wk.seq_started.connect(sq.on_started)
        wk.seq_step.connect(sq.on_step)
        wk.seq_progress.connect(sq.on_progress)
        wk.seq_finished.connect(sq.on_finished)

        self.geral_page.run_requested.connect(self._rodar_checks)
        self.geral_page.revisar_requested.connect(self._revisar)

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
        self._on_any_progress(atual, total)

    @Slot(str, str)
    def _on_tool_status(self, tool: str, texto: str) -> None:
        self.tool_pages[tool].on_status(texto)

    @Slot(str, object)
    def _on_tool_ready(self, tool: str, report) -> None:
        self.tool_pages[tool].on_ready(report)
        if tool == "poszone":
            self.geral_page.on_poszone(report)
            self._atualizar_contagens()
        elif tool == "flagcheck":
            self.geral_page.on_flags(report)
            self._atualizar_contagens()
        elif tool == "update" and report is not None:
            self.update_page.pedir_previa()

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

    @Slot(str, object)
    def _on_tool_preview(self, tool: str, previa) -> None:
        self.tool_pages[tool].on_preview(previa)

    @Slot(object, object, int)
    def _on_pos_go(self, report, item, pedido: int) -> None:
        self.request_go.emit("poszone", report, item, pedido)

    @Slot(object, object, int)
    def _on_flagcheck_go(self, report, item, pedido: int) -> None:
        self.request_go.emit("flagcheck", report, item, pedido)

    @Slot(object, object, int)
    def _on_fontfix_go(self, report, item, pedido: int) -> None:
        self.request_go.emit("fontfix", report, item, pedido)

    @Slot(str, int, bool)
    def _on_tool_nav(self, tool: str, pedido: int, ok: bool) -> None:
        self.tool_pages[tool].on_nav_done(pedido, ok)

    @Slot(object)
    def _on_font_report(self, report) -> None:
        self.geral_page.on_font(report)
        self._atualizar_contagens()

    def _atualizar_contagens(self) -> None:
        font, pos = self.geral_page.pendencias_font(), self.geral_page.pendencias_pos()
        flags = self.geral_page.pendencias_flags()
        for nome, n, cor, fundo in (
            ("Font Size Check", font, T.RED, T.RED_BG), ("Position and Zone", pos, T.AMBER, T.AMBER_BG),
            ("Check de Flags", flags, T.RED, T.RED_BG),
        ):
            selo = self.rail_badges[nome]
            selo.setText(str(n))
            selo.setStyleSheet(f"color: {cor}; background: {fundo};")
            selo.setVisible(n > 0)
        self.contagem_check.setText(str(font + pos + flags))
        self.contagem_check.setVisible(font + pos + flags > 0)

    @Slot(list)
    def _rodar_checks(self, checks: list) -> None:
        if "font" in checks:
            self.request_analyze.emit()
        if "poszone" in checks:
            self.request_tool.emit("poszone")
        if "flagcheck" in checks:
            self.request_tool.emit("flagcheck")

    @Slot(str)
    def _revisar(self, qual: str) -> None:
        if qual == "font":
            self.ir_para(ABA_CHECK, "Check", "Font Size Check", PAGINA_FONT)
        elif qual == "flagcheck":
            self.ir_para(ABA_CHECK, "Check", "Check de Flags", PAGINA_CHECKFLAGS)
        else:
            self.ir_para(ABA_CHECK, "Check", "Position and Zone", PAGINA_POSZONE)

    @Slot()
    def _ir_para_fix_flags(self) -> None:
        self.ir_para(ABA_DESIGN, "Design", "Fix Flags", PAGINA_FLAGS)

    @Slot()
    def _ir_para_font_fix(self) -> None:
        self.ir_para(ABA_DESIGN, "Design", "Font Size Fix", PAGINA_FONTFIX)

    @Slot()
    def _ir_para_check(self) -> None:
        self.ir_para(ABA_CHECK, "Check", "Visão geral", PAGINA_GERAL)

    @Slot(bool)
    def _on_busy(self, ocupado: bool) -> None:
        self._busy = ocupado
        self.barra_acento.setRange(0, 0 if ocupado else 100)
        if not ocupado:
            self.barra_acento.setValue(100)
        self._mostrar_catia()

    @Slot(int, int)
    def _on_any_progress(self, atual: int, total: int) -> None:
        if self._busy and total > 0:
            self.barra_acento.setRange(0, total)
            self.barra_acento.setValue(atual)

    def _mostrar_catia(self) -> None:
        if self._busy:
            self.chip_catia.setText("●  CATIA ocupado")
            self.chip_catia.setStyleSheet(f"color: {T.AMBER};")
        else:
            self.chip_catia.setText("●  CATIA ativo" if self._conectado else "●  CATIA fechado")
            self.chip_catia.setStyleSheet(f"color: {T.GREEN if self._conectado else T.RED};")

    def _on_status(self, connected: bool, document: str) -> None:
        self._conectado = connected
        self._documento = document
        self._mostrar_catia()
        self.chip_doc.setText(document or "Nenhum desenho")
        for pagina in (self.font_page, self.flags_page, self.seq_page, self.geral_page, *self.tool_pages.values()):
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
        for pagina in (self.font_page, self.flags_page, self.seq_page, self.geral_page, *self.tool_pages.values()):
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
        self.worker.request_stop_sequence()
        self.worker.answer_format("")
        self.worker.answer_confirm(False)
        self._thread.quit()
        if not self._thread.wait(5000):
            # O CATIA nao respondeu: nao segura o HUB aberto por causa dele.
            os._exit(0)
        super().closeEvent(event)
