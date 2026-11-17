"""Janela do HUB em PySide6, seguindo o prototipo em design/hub_prototipo.html.

Cada ferramenta so entra aqui depois de passar pela comparacao com a macro (ver MIGRACAO.md).
"""
from __future__ import annotations

import os

from PySide6.QtCore import QCoreApplication, QEvent, QRect, QSize, Qt, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QLabel, QProgressBar, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget,
)

from ui_qt import theme as T
from ui_qt.catia_worker import CatiaWorker
from ui_qt.check_fix_pages import CompareDwgPage, FlagCheckPage, FontSizeFixPage, TemplateCheckPage
from ui_qt.fix_flags_page import FixFlagsPage
from ui_qt.font_size_page import FontSizePage, button, label
from ui_qt.icones import icone, pixmap
from ui_qt.pecas import Cartao, Resumo, largura_livre
from ui_qt.poszone_page import PosZoneFixPage, PosZonePage
from ui_qt.sequencia_page import CheckGeralPage, SequenciaPage
from ui_qt.tool_pages import Split2DPage, Split3DPage, SymbolShapePage, UpdateTemplatePage
from ui_qt.voo import Barra, CartaoResumo, Voo

LARGURA, ALTURA = 1180, 720
LARGURA_COMPACTA = 460
INTERVALO_STATUS_MS = 2000
ABA_DESIGN, ABA_CHECK, ABA_ENVIO = range(3)
NOMES_ABA = ("Design", "Check", "Envio")
# Ampliado, no canto da tela, ou so a barra de icones.
MODO_CHEIO, MODO_CANTO, MODO_MINI = range(3)
(
    PAGINA_SEQUENCIA, PAGINA_UPDATE, PAGINA_FLAGS, PAGINA_GERAL, PAGINA_FONT, PAGINA_POSZONE, PAGINA_SPLIT3D, PAGINA_SPLIT2D,
    PAGINA_FONTFIX, PAGINA_CHECKFLAGS, PAGINA_COMPARE, PAGINA_POSZONEFIX, PAGINA_CHECKTEMPLATE, PAGINA_SYMBOL,
) = range(14)


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
    request_partlist = Signal(list)
    request_excel = Signal(str, object)
    request_mover = Signal(str, object, object, str)
    request_desfazer = Signal(str, object, object)
    request_encerrar = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("janela")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setWindowFlag(Qt.FramelessWindowHint)
        # Sem moldura, o Windows so minimiza pela barra de tarefas se a janela disser que aceita.
        self.setWindowFlag(Qt.WindowMinimizeButtonHint)
        self.setWindowTitle("E1 Tools")
        self.setStyleSheet(T.QSS)
        self._compact = False
        self._modo = MODO_CHEIO
        self._seq_etapas = 1
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
        self.poszonefix_page = PosZoneFixPage()
        self.split3d_page = Split3DPage()
        self.split2d_page = Split2DPage()
        self.fontfix_page = FontSizeFixPage()
        self.flagcheck_page = FlagCheckPage()
        self.templatecheck_page = TemplateCheckPage()
        self.compare_page = CompareDwgPage()
        self.symbol_page = SymbolShapePage()
        self.tool_pages = {
            p.TOOL: p for p in (
                self.update_page, self.poszone_page, self.poszonefix_page, self.split3d_page, self.split2d_page, self.fontfix_page,
                self.flagcheck_page, self.templatecheck_page, self.symbol_page,
            )
        }

        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        self._cabecalho = self._build_header()
        col.addWidget(self._cabecalho)
        self.barra_acento = QProgressBar()
        self.barra_acento.setObjectName("acento")
        self.barra_acento.setTextVisible(False)
        self.barra_acento.setFixedHeight(2)
        self.barra_acento.setRange(0, 100)
        self.barra_acento.setValue(100)
        col.addWidget(self.barra_acento)

        self._corpo = QWidget()
        corpo = QHBoxLayout(self._corpo)
        corpo.setContentsMargins(12, 12, 12, 12)
        self._itens_aba = {ABA_DESIGN: [], ABA_CHECK: [], ABA_ENVIO: []}
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
                              ("Symbol Shape Converter", "arrow", PAGINA_SYMBOL, ""),
                              ("Fix Flags", "flag", PAGINA_FLAGS, ""),
                              ("Font Size Fix", "sheet", PAGINA_FONTFIX, ""),
                              ("Pos and Zone Fix", "box", PAGINA_POSZONEFIX, "")))),
            "Cada ferramenta também roda sozinha, fora da sequência.",
        ))
        self._rail.addWidget(self._build_rail(
            ABA_CHECK,
            (("CHECK", (("Visão geral", "shield", PAGINA_GERAL, ""),
                        ("Font Size Check", "sheet", PAGINA_FONT, ""),
                        ("Position and Zone", "box", PAGINA_POSZONE, ""),
                        ("Check de Flags", "flag", PAGINA_CHECKFLAGS, ""),
                        ("Check de Template", "file", PAGINA_CHECKTEMPLATE, ""),
                        ("Compare DWG", "monitor", PAGINA_COMPARE, ""))),),
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
            self.poszone_page, self.split3d_page, self.split2d_page, self.fontfix_page, self.flagcheck_page, self.compare_page,
            self.poszonefix_page, self.templatecheck_page, self.symbol_page,
        ):
            self._pages.addWidget(pagina)
            _so_a_atual_conta(pagina._stack) if hasattr(pagina, "_stack") else None
        _so_a_atual_conta(self._pages)
        corpo.addWidget(self._pages, 1)
        abas = [(NOMES_ABA[a], self._itens_aba[a]) for a in (ABA_DESIGN, ABA_CHECK, ABA_ENVIO)]
        # No canto, o trilho some: esta faixa de icones troca de aba e de ferramenta.
        self._faixa = Barra(abas, em_pe=False)
        self._faixa.hide()
        col.addWidget(self._faixa)
        col.addWidget(self._corpo, 1)
        self.voo = Voo()
        col.addWidget(self.voo)
        self._mini = Barra(abas, em_pe=True, modo_canto=MODO_CANTO, modo_cheio=MODO_CHEIO)
        self._mini.hide()
        col.addWidget(self._mini, 1)
        self.cartao = CartaoResumo(self)
        self._voos = (self.voo, self.cartao.voo)
        self._faixa.aba.connect(self._barra_aba)
        self._faixa.ferramenta.connect(self._faixa_ferramenta)
        self._mini.aba.connect(self._barra_aba)
        self._mini.ferramenta.connect(self._mini_ferramenta)
        self._mini.modo.connect(self.set_modo)
        self.cartao.executar.connect(self._executar_do_cartao)
        self.cartao.abrir.connect(lambda: self.set_modo(MODO_CANTO))
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

        selo = label("", "selo")
        selo.setFixedSize(42, 42)
        selo.setAlignment(Qt.AlignCenter)
        selo.setPixmap(pixmap("plane", "#FFFFFF", 28))
        h.addWidget(selo)
        nomes = QVBoxLayout()
        nomes.setSpacing(0)
        nomes.addStretch(1)
        nomes.addWidget(label("E1 TOOLS", "marca"))
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

        self.btn_min = button("", "janelaBtn")
        self.btn_min.setIcon(icone("minus", T.MUTED, 16))
        self.btn_min.setFixedSize(36, 66)
        self.btn_min.setToolTip("Minimizar")
        self.btn_min.clicked.connect(self.showMinimized)
        h.addWidget(self.btn_min)
        self.btn_compact = button("", "janelaBtn")
        self.btn_compact.setIcon(icone("dock", T.MUTED, 16))
        self.btn_compact.setFixedSize(36, 66)
        self.btn_compact.setToolTip("Modo compacto: fica ao lado do CATIA, sempre visível")
        self.btn_compact.clicked.connect(self.toggle_compact)
        h.addWidget(self.btn_compact)
        self.btn_mini = button("", "janelaBtn")
        self.btn_mini.setIcon(icone("rail", T.MUTED, 16))
        self.btn_mini.setFixedSize(36, 66)
        self.btn_mini.setToolTip("Só ícones: uma barra fina no canto da tela")
        self.btn_mini.clicked.connect(lambda: self.set_modo(MODO_MINI))
        h.addWidget(self.btn_mini)
        fechar = button("", "fecharBtn")
        fechar.setIcon(icone("x", T.MUTED, 16))
        fechar.setFixedSize(40, 66)
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
                    self._itens_aba[aba].append((nome, ic, pagina))
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
        self._sincronizar()

    def _on_tool(self, aba: int, pagina: int) -> None:
        self._aba_pagina[aba] = pagina
        self._pages.setCurrentIndex(pagina)
        self._sincronizar()

    def _sincronizar(self) -> None:
        """As barras de icones mostram a mesma aba e a mesma ferramenta do trilho."""
        if not hasattr(self, "_mini"):
            return
        for barra in (self._faixa, self._mini):
            barra.selecionar(self._rail.currentIndex(), self._pages.currentIndex())

    def _nome_da_pagina(self) -> str:
        aba, pagina = self._rail.currentIndex(), self._pages.currentIndex()
        return next((nome for nome, _ic, p in self._itens_aba[aba] if p == pagina), "")

    @Slot(int)
    def _barra_aba(self, aba: int) -> None:
        self.pills[NOMES_ABA[aba]].setChecked(True)
        self._on_tab(aba)
        if self.cartao.isVisible():
            self._mostrar_cartao()

    @Slot(int, str, int)
    def _faixa_ferramenta(self, aba: int, nome: str, pagina: int) -> None:
        self.ir_para(aba, NOMES_ABA[aba], nome, pagina)

    @Slot(int, str, int)
    def _mini_ferramenta(self, aba: int, nome: str, pagina: int) -> None:
        """Clicar no icone abre o cartao; clicar de novo no mesmo fecha."""
        mesma = self.cartao.isVisible() and self._pages.currentIndex() == pagina
        self.ir_para(aba, NOMES_ABA[aba], nome, pagina)
        if mesma:
            self.cartao.hide()
        else:
            self._mostrar_cartao()

    def _resumo_da_pagina(self) -> list:
        """Os numeros que a propria tela da ferramenta ja mostra."""
        pagina = self._pages.currentWidget()
        linhas = [(c.legenda.text(), c.numero.text()) for c in pagina.findChildren(Cartao)]
        if not linhas:
            resumos = pagina.findChildren(Resumo)
            if resumos:
                linhas = [(nome, valor.text()) for nome, valor in resumos[0].valores.items()]
        return linhas[:5]

    def _mostrar_cartao(self) -> None:
        if self._modo != MODO_MINI:
            return
        self.cartao.preencher(NOMES_ABA[self._rail.currentIndex()], self._nome_da_pagina(), self._resumo_da_pagina())
        self.cartao.encostar(self.frameGeometry())
        self.cartao.show()

    @Slot()
    def _executar_do_cartao(self) -> None:
        """O mesmo que o botao principal da tela da ferramenta faria."""
        if self._busy:
            return
        pagina = self._pages.currentWidget()
        if pagina is self.seq_page:
            self.seq_page.btn_executar.click()
        elif pagina is self.geral_page:
            self.geral_page._rodar()
        elif pagina is self.compare_page:
            self.compare_page.abrir()
        elif hasattr(pagina, "_on_intro_button"):
            pagina._on_intro_button()

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

        self.request_poll.connect(wk.poll_leve)
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
        wk.started_analysis.connect(self._voo_font)
        wk.flags_started.connect(self._voo_flags)
        wk.seq_started.connect(self._voo_seq)
        wk.seq_progress.connect(self._voo_seq_progresso)
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
        self.request_partlist.connect(wk.ler_part_list)
        self.request_excel.connect(wk.abrir_excel)
        self.request_mover.connect(wk.mover_balao)
        self.request_desfazer.connect(wk.desfazer_movimento)
        self.request_encerrar.connect(wk.encerrar)
        wk.partlist_ready.connect(self._on_part_list)
        wk.partlist_failed.connect(self._on_part_list_falhou)
        wk.pos_movido.connect(self._on_pos_movido)
        wk.pos_desfeito.connect(self._on_pos_desfeito)
        wk.excel_failed.connect(self._on_tool_warn_excel)
        for pos in (self.poszone_page, self.poszonefix_page):
            pos.latest_nav.connect(wk.mark_latest_tool_nav, Qt.DirectConnection)
            pos.partlist_requested.connect(self._pedir_part_list)
            pos.partlist_clear_requested.connect(self._limpar_part_list)
            pos.excel_requested.connect(self.request_excel)
            pos.alterado.connect(self._on_pos_alterado)
        self.poszone_page.go_requested.connect(self._on_pos_go)
        self.poszonefix_page.go_requested.connect(self._on_posfix_go)
        self.poszonefix_page.mover_requested.connect(self._on_pos_mover)
        self.poszonefix_page.desfazer_requested.connect(self._on_pos_desfazer)
        self.poszone_page.trocar_requested.connect(self._ir_para_pos_fix)
        self.poszonefix_page.trocar_requested.connect(self._revisar_pos)
        self.flagcheck_page.go_requested.connect(self._on_flagcheck_go)
        self.flagcheck_page.latest_nav.connect(wk.mark_latest_tool_nav, Qt.DirectConnection)
        self.flagcheck_page.corrigir_requested.connect(self._ir_para_fix_flags)
        self.templatecheck_page.go_requested.connect(self._on_templatecheck_go)
        self.templatecheck_page.latest_nav.connect(wk.mark_latest_tool_nav, Qt.DirectConnection)
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
        self.geral_page.compare_requested.connect(self.compare_page.abrir)

        self._thread.start()
        self._timer = QTimer(self)
        self._timer.setInterval(INTERVALO_STATUS_MS)
        self._timer.timeout.connect(self.request_poll)
        self._timer.start()
        self.request_poll.emit()

    @Slot(str)
    def _on_tool_started(self, tool: str) -> None:
        self.tool_pages[tool].on_started()
        self._titulo_voo(self.tool_pages[tool].TITULO)

    def _titulo_voo(self, texto: str) -> None:
        for v in self._voos:
            v.titulo(texto)

    @Slot()
    def _voo_font(self) -> None:
        self._titulo_voo("Font Size Check")

    @Slot()
    def _voo_flags(self) -> None:
        self._titulo_voo("Fix Flags")

    @Slot(list)
    def _voo_seq(self, etapas: list) -> None:
        self._seq_etapas = max(1, len(etapas))
        self._titulo_voo("Sequência de aplicação")

    @Slot(int, int, int)
    def _voo_seq_progresso(self, etapa: int, atual: int, total: int) -> None:
        """Na sequencia o voo e um so: cada etapa vale uma parte do arco."""
        if not self._busy or total <= 0:
            return
        for v in self._voos:
            v.definir((etapa + atual / total) / self._seq_etapas, f"Etapa {etapa + 1} de {self._seq_etapas}")
        self.cartao.lbl_estado.setText(self.cartao.voo.estado())

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
        if tool in ("poszone", "poszonefix"):
            # As duas telas mostram a mesma leitura: nao precisa mapear de novo ao trocar de aba.
            outra = self.poszonefix_page if tool == "poszone" else self.poszone_page
            if report is not None:
                outra.on_ready(report)
            self.geral_page.on_poszone(report)
            self._atualizar_contagens()
        elif tool == "flagcheck":
            self.geral_page.on_flags(report)
            self._atualizar_contagens()
        elif tool == "templatecheck":
            self.geral_page.on_template(report)
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
    def _on_posfix_go(self, report, item, pedido: int) -> None:
        self.request_go.emit("poszonefix", report, item, pedido)

    @Slot(list)
    def _pedir_part_list(self, caminhos: list) -> None:
        for pos in (self.poszone_page, self.poszonefix_page):
            pos.lendo_part_list(True)
        self.request_partlist.emit(caminhos)

    @Slot()
    def _limpar_part_list(self) -> None:
        self._on_part_list(None)

    @Slot(object)
    def _on_part_list(self, parte) -> None:
        for pos in (self.poszone_page, self.poszonefix_page):
            pos.definir_part_list(parte)
        self.geral_page.definir_part_list(parte is not None)
        self._atualizar_visao_pos()

    @Slot(str)
    def _on_part_list_falhou(self, mensagem: str) -> None:
        for pos in (self.poszone_page, self.poszonefix_page):
            pos.lendo_part_list(False)
        self.poszone_page.on_warn(mensagem, "Erro na importação")

    @Slot()
    def _on_pos_alterado(self) -> None:
        origem = self.sender()
        for pos in (self.poszone_page, self.poszonefix_page):
            if pos is not origem:
                pos.atualizar_tabela()
        self._atualizar_visao_pos()

    def _atualizar_visao_pos(self) -> None:
        self.geral_page.on_poszone(self.poszone_page._report or self.poszonefix_page._report)
        self._atualizar_contagens()

    @Slot(object, object, str)
    def _on_pos_mover(self, report, occ, zona: str) -> None:
        self.request_mover.emit("poszonefix", report, occ, zona)

    @Slot(object, object)
    def _on_pos_desfazer(self, report, mov) -> None:
        self.request_desfazer.emit("poszonefix", report, mov)

    @Slot(str, object, str)
    def _on_pos_movido(self, tool: str, mov, erro: str) -> None:
        self.tool_pages[tool].on_movido(mov, erro)

    @Slot(str, object, str)
    def _on_pos_desfeito(self, tool: str, mov, erro: str) -> None:
        self.tool_pages[tool].on_desfeito(mov, erro)

    @Slot(str, str)
    def _on_tool_warn_excel(self, tool: str, mensagem: str) -> None:
        self.tool_pages[tool].on_warn(mensagem, "Abrir no Excel")

    @Slot()
    def _ir_para_pos_fix(self) -> None:
        self.ir_para(ABA_DESIGN, "Design", "Pos and Zone Fix", PAGINA_POSZONEFIX)

    @Slot()
    def _revisar_pos(self) -> None:
        self._revisar("poszone")

    @Slot(object, object, int)
    def _on_flagcheck_go(self, report, item, pedido: int) -> None:
        self.request_go.emit("flagcheck", report, item, pedido)

    @Slot(object, object, int)
    def _on_templatecheck_go(self, report, item, pedido: int) -> None:
        self.request_go.emit("templatecheck", report, item, pedido)

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
        template = self.geral_page.pendencias_template()
        for nome, n, cor, fundo in (
            ("Font Size Check", font, T.RED, T.RED_BG), ("Position and Zone", pos, T.AMBER, T.AMBER_BG),
            ("Check de Flags", flags, T.RED, T.RED_BG), ("Check de Template", template, T.RED, T.RED_BG),
        ):
            selo = self.rail_badges[nome]
            selo.setText(str(n))
            selo.setStyleSheet(f"color: {cor}; background: {fundo};")
            selo.setVisible(n > 0)
            for barra in (self._faixa, self._mini):
                barra.selo(nome, n, cor, fundo)
        self.contagem_check.setText(str(font + pos + flags + template))
        self.contagem_check.setVisible(font + pos + flags + template > 0)

    @Slot(list)
    def _rodar_checks(self, checks: list) -> None:
        if "font" in checks:
            self.request_analyze.emit()
        if "poszone" in checks:
            self.request_tool.emit("poszone")
        if "flagcheck" in checks:
            self.request_tool.emit("flagcheck")
        if "templatecheck" in checks:
            self.request_tool.emit("templatecheck")

    @Slot(str)
    def _revisar(self, qual: str) -> None:
        if qual == "font":
            self.ir_para(ABA_CHECK, "Check", "Font Size Check", PAGINA_FONT)
        elif qual == "flagcheck":
            self.ir_para(ABA_CHECK, "Check", "Check de Flags", PAGINA_CHECKFLAGS)
        elif qual == "templatecheck":
            self.ir_para(ABA_CHECK, "Check", "Check de Template", PAGINA_CHECKTEMPLATE)
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
        for v in self._voos:
            v.ocupado(ocupado)
        self.cartao.lbl_estado.setText(self.cartao.voo.estado())
        self.cartao.btn_executar.setEnabled(not ocupado)
        if not ocupado and self.cartao.isVisible():
            QTimer.singleShot(0, self._mostrar_cartao)  # a tela da ferramenta atualiza os numeros primeiro
        self._mostrar_catia()

    @Slot(int, int)
    def _on_any_progress(self, atual: int, total: int) -> None:
        if self._busy and total > 0:
            self.barra_acento.setRange(0, total)
            self.barra_acento.setValue(atual)
            for v in self._voos:
                v.progresso(atual, total)
            self.cartao.lbl_estado.setText(self.cartao.voo.estado())

    def _mostrar_catia(self) -> None:
        if self._busy:
            self.chip_catia.setText("●  CATIA ocupado")
            self.chip_catia.setStyleSheet(f"color: {T.AMBER};")
            self._mini.catia(T.AMBER, "CATIA ocupado")
        else:
            self.chip_catia.setText("●  CATIA ativo" if self._conectado else "●  CATIA fechado")
            self.chip_catia.setStyleSheet(f"color: {T.GREEN if self._conectado else T.RED};")
            self._mini.catia(T.GREEN if self._conectado else T.RED, "CATIA ativo" if self._conectado else "CATIA fechado")

    def _on_status(self, connected: bool, document: str, desenho: bool = False) -> None:
        self._conectado = connected
        self._documento = document
        self._mostrar_catia()
        self.chip_doc.setText(document or "Nenhum desenho")
        for pagina in (self.font_page, self.flags_page, self.seq_page, self.geral_page, *self.tool_pages.values()):
            pagina.set_catia_state(connected, document, desenho)

    # ------------------------------------------------------------------
    # Os tres modos: ampliado, canto e so icones
    # ------------------------------------------------------------------
    def toggle_compact(self) -> None:
        self.set_modo(MODO_CHEIO if self._modo == MODO_CANTO else MODO_CANTO)

    @Slot(int)
    def set_modo(self, modo: int) -> None:
        if modo == self._modo:
            return
        if self._modo == MODO_CHEIO:
            self._normal_geometry = self.geometry()
        self._modo = modo
        self._compact = modo == MODO_CANTO
        mini = modo == MODO_MINI
        self.cartao.hide()
        for w in (self._cabecalho, self.barra_acento, self._corpo, self.voo):
            w.setVisible(not mini)
        self._mini.setVisible(mini)
        self._faixa.setVisible(modo == MODO_CANTO)
        for w in (self._rail, self._pills, self._brand_sub, self.chip_doc):
            w.setVisible(modo == MODO_CHEIO)
        for pagina in (self.font_page, self.flags_page, self.seq_page, self.geral_page, *self.tool_pages.values()):
            pagina.set_compact(modo != MODO_CHEIO)
        self._sincronizar()
        self.layout().activate()
        self.setWindowFlag(Qt.WindowStaysOnTopHint, modo != MODO_CHEIO)
        self.btn_compact.setToolTip("Voltar ao tamanho normal" if self._compact else "Modo compacto: fica ao lado do CATIA, sempre visível")
        # Mudar a opcao recria a janela do Windows: o tamanho so vale depois de ela se reorganizar.
        self.show()
        QTimer.singleShot(0, self._apply_mode_geometry)

    def _apply_mode_geometry(self, tentativa: int = 0) -> None:
        if tentativa and self._modo != MODO_CHEIO:
            return
        # Os layouts internos ainda nao recalcularam o minimo depois de esconder os widgets.
        # O pedido sobe um nivel de cada vez, da pagina ate a janela.
        for _ in range(4):
            QCoreApplication.sendPostedEvents(None, QEvent.LayoutRequest)
        self.layout().activate()
        area = (self.screen() or QGuiApplication.primaryScreen()).availableGeometry()
        if self._modo == MODO_CANTO:
            alvo = QRect(area.right() - LARGURA_COMPACTA + 1, area.top(), LARGURA_COMPACTA, area.height())
            self.setGeometry(alvo)
            # Os textos com quebra de linha recalculam a altura depois, e a janela crescia sozinha para
            # baixo da tela, escondendo o botao. Confere de novo e devolve a janela ao tamanho da tela.
            for espera_ms in (120, 400, 900):
                QTimer.singleShot(espera_ms, lambda a=alvo: self._segurar_no_canto(a))
        elif self._modo == MODO_MINI:
            altura = min(area.height(), self._mini.sizeHint().height())
            largura = self._mini.width()
            self.setGeometry(area.right() - largura - 7, area.top() + (area.height() - altura) // 3, largura, altura)
        else:
            self.setGeometry(self._normal_geometry)
            if self.geometry() != self._normal_geometry and tentativa < 5:
                # Vindo da barra de icones, as telas estavam escondidas e ainda guardam o minimo antigo.
                QTimer.singleShot(60, lambda: self._apply_mode_geometry(tentativa + 1))

    def _segurar_no_canto(self, alvo: QRect) -> None:
        if self._modo == MODO_CANTO and self.geometry().height() > alvo.height():
            self.setGeometry(alvo)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        # No canto a janela nunca pode passar da altura da tela: o botao fica embaixo.
        if getattr(self, "_modo", MODO_CHEIO) == MODO_CANTO:
            area = (self.screen() or QGuiApplication.primaryScreen()).availableGeometry()
            if self.height() > area.height():
                QTimer.singleShot(0, lambda: self._segurar_no_canto(
                    QRect(self.x(), area.top(), self.width(), area.height())))

    def moveEvent(self, event) -> None:
        super().moveEvent(event)
        cartao = getattr(self, "cartao", None)
        if cartao is not None and cartao.isVisible():
            cartao.encostar(self.frameGeometry())

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        worker = getattr(self, "worker", None)
        if worker is not None and event.type() == QEvent.ActivationChange:
            worker.janela_ativa = self.isActiveWindow()
            if worker.janela_ativa:
                self.request_poll.emit()

    def closeEvent(self, event) -> None:
        self.cartao.hide()
        self._timer.stop()
        self.worker.request_stop()
        self.worker.request_stop_sequence()
        self.worker.answer_format("")
        self.worker.answer_confirm(False)
        # O worker devolve o CATIA limpo e so entao encerra a propria thread.
        self.request_encerrar.emit()
        if not self._thread.wait(5000):
            # O CATIA nao respondeu: nao segura o HUB aberto por causa dele.
            os._exit(0)
        super().closeEvent(event)
