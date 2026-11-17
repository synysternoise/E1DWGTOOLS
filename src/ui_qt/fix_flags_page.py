"""Tela do Fix Flags: corrige as flag notes e leva ate cada uma delas no CATIA."""
from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QButtonGroup, QFrame, QHBoxLayout, QHeaderView, QMessageBox, QProgressBar,
    QSizePolicy, QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from engine import fix_flags as ff
from engine.documento import eh_desenho
from ui_qt import theme as T
from ui_qt.font_size_page import PAPEL_OK, MarkDelegate, button, label
from ui_qt.pecas import (
    Cartao, LinhaSituacao, Resumo, aviso_catia_ocupado, botao, botao_grande, etiqueta, icone_grande, moldura,
)
from ui_qt.tool_page import LARGURA_LATERAL

NAO_ENCONTRADO = "Flag não encontrada: foi apagada ou o desenho foi fechado."
COLUNAS = ("", "FOLHA", "VISTA", "ANTES", "DEPOIS", "TIPO")
COL_MARCA, COL_FOLHA, COL_VISTA, COL_ANTES, COL_DEPOIS, COL_TIPO = range(6)
FILTRO_CORRIGIDAS, FILTRO_CORRETAS, FILTRO_PROBLEMA, FILTRO_TODAS = range(4)


def mostrar(texto: str) -> str:
    """Texto de uma linha, com aspas quando ha espaco nas pontas, que nao se veria."""
    plano = texto.replace("\r", "").replace("\n", " / ").replace("\t", " ").replace("\xa0", " ")
    return f"“{plano}”" if plano != plano.strip(" ") or plano != texto else plano


class FixFlagsPage(QWidget):
    run_requested = Signal()
    stop_requested = Signal()
    retry_requested = Signal()
    go_requested = Signal(object, object, int)
    latest_nav = Signal(int)
    confirm_answered = Signal(bool)
    conferir_requested = Signal()

    def __init__(self):
        super().__init__()
        self._report: Optional[ff.FixReport] = None
        self._rows: List[ff.FlagItem] = []
        self._current = -1
        self._nav_request = 0
        self._connected = False
        self._has_drawing = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._stack = QStackedWidget()
        layout.addWidget(self._stack)
        self._stack.addWidget(self._build_intro())
        self._stack.addWidget(self._build_running())
        self._stack.addWidget(self._build_results())
        self._update_intro()

    # ------------------------------------------------------------------
    # Telas
    # ------------------------------------------------------------------
    def _build_intro(self) -> QWidget:
        w = moldura()
        col = QVBoxLayout(w)
        col.setContentsMargins(22, 18, 22, 18)
        col.addStretch(1)
        linha_icone = QHBoxLayout()
        linha_icone.addStretch(1)
        linha_icone.addWidget(icone_grande("flag"))
        linha_icone.addStretch(1)
        col.addLayout(linha_icone)
        self._intro_title = label("Fix Flags", "titulo")
        self._intro_title.setAlignment(Qt.AlignCenter)
        self._intro_title.setWordWrap(True)
        self._intro_sub = label("", "sub")
        self._intro_sub.setAlignment(Qt.AlignCenter)
        self._intro_sub.setWordWrap(True)
        self._intro_error = label("", "erro")
        self._intro_error.setAlignment(Qt.AlignCenter)
        self._intro_error.setWordWrap(True)
        self._intro_error.hide()
        self.btn_run = button("CORRIGIR FLAGS", "primario")
        self.btn_run.clicked.connect(self._on_intro_button)
        col.addWidget(self._intro_title)
        col.addSpacing(6)
        col.addWidget(self._intro_sub)
        col.addSpacing(10)
        col.addWidget(self._intro_error)
        col.addSpacing(10)
        linha = QHBoxLayout()
        linha.addStretch(1)
        linha.addWidget(self.btn_run)
        linha.addStretch(1)
        col.addLayout(linha)
        col.addStretch(2)
        return w

    def _build_running(self) -> QWidget:
        w = moldura()
        col = QVBoxLayout(w)
        col.setContentsMargins(22, 18, 22, 18)
        col.addStretch(1)
        t = label("Corrigindo as flags", "titulo")
        t.setAlignment(Qt.AlignCenter)
        self._run_text = label("", "sub")
        self._run_text.setAlignment(Qt.AlignCenter)
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(10)
        self.btn_stop = button("PARAR", "secundario")
        self.btn_stop.clicked.connect(self._on_stop)
        col.addWidget(t)
        col.addSpacing(6)
        col.addWidget(self._run_text)
        col.addSpacing(14)
        col.addWidget(self.bar)
        col.addSpacing(14)
        col.addWidget(aviso_catia_ocupado())
        col.addSpacing(14)
        linha = QHBoxLayout()
        linha.addStretch(1)
        linha.addWidget(self.btn_stop)
        linha.addStretch(1)
        col.addLayout(linha)
        col.addStretch(2)
        return w

    def _build_results(self) -> QWidget:
        w = QWidget()
        fora = QHBoxLayout(w)
        fora.setContentsMargins(0, 0, 0, 0)
        fora.setSpacing(12)
        centro = moldura()
        col = QVBoxLayout(centro)
        col.setContentsMargins(18, 14, 18, 14)
        col.setSpacing(10)
        fora.addWidget(centro, 1)

        topo = QHBoxLayout()
        textos = QVBoxLayout()
        textos.setSpacing(1)
        textos.addWidget(label("Fix Flags", "titulo"))
        self.lbl_sub = label("", "sub")
        self.lbl_sub.setWordWrap(True)
        self.lbl_sub.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        textos.addWidget(self.lbl_sub)
        self.lbl_counts = label("", "sub")
        self.lbl_counts.setWordWrap(True)
        self.lbl_counts.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.lbl_counts.hide()  # as mesmas contagens ficam no Resumo, ao lado
        textos.addWidget(self.lbl_counts)
        topo.addLayout(textos, 1)
        self._tag = etiqueta("ALTERA O DESENHO")
        topo.addWidget(self._tag, 0, Qt.AlignTop)
        self.btn_again = botao("Corrigir de novo", "secundario", "refresh")
        self.btn_again.clicked.connect(self.run_requested)
        topo.addWidget(self.btn_again, 0, Qt.AlignTop)
        col.addLayout(topo)

        self.lbl_error = label("", "erro")
        self.lbl_error.setWordWrap(True)
        self.lbl_error.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.lbl_error.hide()
        col.addWidget(self.lbl_error)

        cartoes = QHBoxLayout()
        cartoes.setSpacing(8)
        self.card_corrigidas = Cartao("corrigidas", "verde")
        self.card_certas = Cartao("já estavam certas")
        self.card_lidas = Cartao("flags lidas")
        for c in (self.card_corrigidas, self.card_certas, self.card_lidas):
            cartoes.addWidget(c, 1)
        self._cartoes = QFrame()
        self._cartoes.setLayout(cartoes)
        cartoes.setContentsMargins(0, 0, 0, 0)
        col.addWidget(self._cartoes)

        filtros = QHBoxLayout()
        filtros.setSpacing(6)
        self._group = QButtonGroup(self)
        self.btn_fixed = button("", "filtro")
        self.btn_ok = button("", "filtro")
        self.btn_problem = button("", "filtro")
        self.btn_all = button("", "filtro")
        for i, b in enumerate((self.btn_fixed, self.btn_ok, self.btn_problem, self.btn_all)):
            b.setCheckable(True)
            self._group.addButton(b, i)
            filtros.addWidget(b)
        filtros.addStretch(1)
        self.btn_fixed.setChecked(True)
        self._group.idClicked.connect(lambda _: self._fill_table())
        col.addLayout(filtros)

        self.table = QTableWidget(0, len(COLUNAS))
        self.table.setHorizontalHeaderLabels(COLUNAS)
        self.table.verticalHeader().hide()
        self.table.setShowGrid(False)
        self.table.setFocusPolicy(Qt.StrongFocus)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setDefaultSectionSize(38)
        self.table.setItemDelegateForColumn(COL_MARCA, MarkDelegate(self.table))
        cab = self.table.horizontalHeader()
        cab.setHighlightSections(False)
        cab.setSectionResizeMode(QHeaderView.Fixed)
        cab.setSectionResizeMode(COL_VISTA, QHeaderView.Stretch)
        cab.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        for coluna, largura in ((COL_MARCA, 40), (COL_FOLHA, 90), (COL_ANTES, 84), (COL_DEPOIS, 84), (COL_TIPO, 120)):
            self.table.setColumnWidth(coluna, largura)
        self.table.selectionModel().currentRowChanged.connect(self._on_row_changed)
        col.addWidget(self.table, 1)

        detalhe = QFrame()
        detalhe.setObjectName("detalhe")
        d = QHBoxLayout(detalhe)
        d.setContentsMargins(14, 8, 14, 8)
        textos = QVBoxLayout()
        textos.setSpacing(0)
        self.lbl_detail = label("", "detalheForte")
        self.lbl_detail.setWordWrap(True)
        self.lbl_where = label("", "detalheFraco")
        self.lbl_where.setWordWrap(True)
        for rotulo in (self.lbl_detail, self.lbl_where):
            rotulo.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        textos.addWidget(self.lbl_detail)
        textos.addWidget(self.lbl_where)
        d.addLayout(textos, 1)
        self.lbl_nav_state = label("", "chipEstado")
        d.addWidget(self.lbl_nav_state)
        col.addWidget(detalhe)

        nav = QHBoxLayout()
        self.btn_prev = botao("ANTERIOR", "secundario", "left")
        self.btn_next = botao("PRÓXIMO", "primario", "right", T.CYAN_INK)
        self.btn_next.setLayoutDirection(Qt.RightToLeft)
        self.lbl_pos = label("", "posicao")
        self.lbl_pos.setAlignment(Qt.AlignCenter)
        self.btn_prev.clicked.connect(self._on_prev)
        self.btn_next.clicked.connect(self._on_next)
        for b in (self.btn_prev, self.btn_next):
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            b.setFixedHeight(40)
        nav.addWidget(self.btn_prev, 2)
        nav.addWidget(self.lbl_pos, 1)
        nav.addWidget(self.btn_next, 2)
        col.addLayout(nav)

        self._lateral = moldura()
        self._lateral.setFixedWidth(LARGURA_LATERAL)
        lado = QVBoxLayout(self._lateral)
        lado.setContentsMargins(14, 14, 14, 14)
        lado.setSpacing(10)
        lado.addWidget(label("Resumo", "titulo"))
        self.resumo = Resumo((
            "Textos analisados", "Flags lidas", "No objeto inteiro", "Pelo Text Editor", "Fixas com cadeado",
            "Corrigidas", "Já certas", "Ignorados", "Falhas de validação", "Restaurados", "Erros",
        ))
        lado.addWidget(self.resumo)
        lado.addStretch(1)
        self.linha_fim = LinhaSituacao()
        lado.addWidget(self.linha_fim)
        self.btn_conferir = botao_grande("CONFERIR NO CHECK", "shield")
        self.btn_conferir.clicked.connect(self.conferir_requested)
        lado.addWidget(self.btn_conferir)
        fora.addWidget(self._lateral)
        return w

    # ------------------------------------------------------------------
    # Estado do CATIA e tela inicial
    # ------------------------------------------------------------------
    def set_catia_state(self, connected: bool, document: str) -> None:
        self._connected = connected
        self._has_drawing = eh_desenho(document)
        self._update_intro()

    def _update_intro(self) -> None:
        if not self._connected:
            self._intro_title.setText("O CATIA não está aberto")
            self._intro_sub.setText("Abra o CATIA com o desenho. O HUB percebe sozinho e libera a correção.")
            self.btn_run.setText("PROCURAR DE NOVO")
        elif not self._has_drawing:
            self._intro_title.setText("Nenhum desenho aberto")
            self._intro_sub.setText("Abra um CATDrawing no CATIA. O HUB percebe sozinho e libera a correção.")
            self.btn_run.setText("PROCURAR DE NOVO")
        else:
            self._intro_title.setText("Fix Flags")
            self._intro_sub.setText(
                "Corrige as flag notes: NL006 vira NL0006. O resultado aparece aqui, sem pintar o desenho. "
                "Flags já corretas não são tocadas. Altera o desenho: salve uma cópia antes."
            )
            self.btn_run.setText("CORRIGIR FLAGS")
        self.btn_again.setEnabled(self._connected and self._has_drawing)

    def _on_intro_button(self) -> None:
        if self._connected and self._has_drawing:
            self.run_requested.emit()
        else:
            self.retry_requested.emit()

    # ------------------------------------------------------------------
    # Execucao
    # ------------------------------------------------------------------
    def on_started(self) -> None:
        self._intro_error.hide()
        self.bar.setRange(0, 0)
        self._run_text.setText("Conferindo o desenho")
        self.btn_stop.setEnabled(True)
        self._stack.setCurrentIndex(1)

    def on_progress(self, sheet: int, total: int) -> None:
        self.bar.setRange(0, total)
        self.bar.setValue(sheet)
        self._run_text.setText(f"Folha {sheet} de {total}")

    def _on_stop(self) -> None:
        self.btn_stop.setEnabled(False)
        self._run_text.setText("Parando ao fim desta folha")
        self.stop_requested.emit()

    def on_ask_confirm(self, message: str, title: str) -> None:
        # Clicar em Corrigir ja e a confirmacao: a janela de pergunta saiu a pedido.
        self.confirm_answered.emit(True)

    def _perguntar(self, message: str, title: str) -> bool:
        # Como no VBA, o botao padrao e o Nao: o desenho so muda se a pessoa escolher Sim.
        caixa = QMessageBox(self)
        caixa.setIcon(QMessageBox.Question)
        caixa.setWindowTitle(title)
        caixa.setText(message.replace("\r\n", "\n"))
        sim = caixa.addButton("Sim", QMessageBox.YesRole)
        nao = caixa.addButton("Não", QMessageBox.NoRole)
        caixa.setDefaultButton(nao)
        caixa.setEscapeButton(nao)
        caixa.exec()
        return caixa.clickedButton() is sim

    def on_warn(self, message: str, title: str) -> None:
        QMessageBox.warning(self, title, message.replace("\r\n", "\n"))

    def on_failed(self, message: str, report: Optional[ff.FixReport]) -> None:
        texto = message.replace("\r\n", "\n")
        if report is None:
            self._intro_error.setText(texto)
            self._intro_error.show()
            self._stack.setCurrentIndex(0)
            return
        self.on_report(report)
        self.lbl_error.setText(texto + "\nO que aparece abaixo já foi alterado no desenho.")
        self.lbl_error.show()

    def on_report(self, report: Optional[ff.FixReport]) -> None:
        if report is None:  # nao era um desenho, ou respondeu Nao: nada mudou
            self._stack.setCurrentIndex(2 if self._report else 0)
            return
        self._report = report
        self.lbl_error.hide()
        problemas = [i for i in report.items if not i.ok]
        self.card_corrigidas.valor(report.corrigidas)
        self.card_certas.valor(report.ja_corretas)
        self.card_lidas.valor(report.flags)
        for nome, valor, cor in (
            ("Textos analisados", report.textos, ""), ("Flags lidas", report.flags, ""),
            ("No objeto inteiro", report.objeto, ""), ("Pelo Text Editor", report.text_editor, ""), ("Fixas com cadeado", report.cadeado, ""),
            ("Corrigidas", report.corrigidas, T.GREEN if report.corrigidas else ""), ("Já certas", report.ja_corretas, ""),
            ("Ignorados", report.ignoradas, ""), ("Falhas de validação", report.falhas, T.RED if report.falhas else ""),
            ("Restaurados", report.restauradas, T.AMBER if report.restauradas else ""), ("Erros", report.erros, T.RED if report.erros else ""),
        ):
            self.resumo.definir(nome, valor, cor)
        self.linha_fim.definir("aviso" if problemas else "ok", "Confira as flags com problema" if problemas else "Pode voltar a usar o CATIA")
        parou = "  ·  Parado antes do fim" if report.stopped else ""
        self.lbl_sub.setText(
            f"{report.textos} textos analisados  ·  {report.flags} flags{parou}"
        )
        self.lbl_counts.setText(
            f"{report.objeto} no objeto inteiro  ·  {report.text_editor} pelo Text Editor  ·  "
            f"{report.cadeado} fixas com cadeado  ·  {report.falhas} falhas de validação  ·  "
            f"{report.restauradas} restaurados  ·  {report.erros} erros"
        )
        self.btn_fixed.setText(f"Corrigidas ({report.corrigidas})")
        self.btn_ok.setText(f"Já corretas ({report.ja_corretas})")
        self.btn_problem.setText(f"Com problema ({len(problemas)})")
        self.btn_all.setText(f"Todas ({len(report.items)})")
        # O que precisa de atencao aparece primeiro.
        if problemas:
            self.btn_problem.setChecked(True)
        elif report.corrigidas:
            self.btn_fixed.setChecked(True)
        else:
            self.btn_all.setChecked(True)
        self._stack.setCurrentIndex(2)
        self._fill_table()

    # ------------------------------------------------------------------
    # Lista e navegacao
    # ------------------------------------------------------------------
    def _filtered(self) -> List[ff.FlagItem]:
        itens = self._report.items
        filtro = self._group.checkedId()
        if filtro == FILTRO_CORRIGIDAS:
            return [i for i in itens if i.result == ff.CORRIGIDA]
        if filtro == FILTRO_CORRETAS:
            return [i for i in itens if i.result == ff.JA_CORRETA]
        if filtro == FILTRO_PROBLEMA:
            return [i for i in itens if not i.ok]
        return list(itens)

    def _fill_table(self) -> None:
        self._rows = self._filtered()
        self._current = -1
        self.table.blockSignals(True)
        self.table.selectionModel().blockSignals(True)
        self.table.clearContents()
        self.table.setRowCount(len(self._rows))
        for linha, it in enumerate(self._rows):
            marca = QTableWidgetItem()
            marca.setData(PAPEL_OK, it.ok)
            self.table.setItem(linha, COL_MARCA, marca)
            for coluna, texto in (
                (COL_FOLHA, it.sheet_name), (COL_VISTA, it.view_name), (COL_ANTES, mostrar(it.before)),
                (COL_DEPOIS, mostrar(it.after)), (COL_TIPO, it.tipo),
            ):
                cel = QTableWidgetItem(texto)
                cel.setToolTip(texto)
                if coluna == COL_DEPOIS:
                    f = cel.font()
                    f.setBold(True)
                    cel.setFont(f)
                self.table.setItem(linha, coluna, cel)
        self.table.selectionModel().blockSignals(False)
        self.table.blockSignals(False)

        tem = bool(self._rows)
        self.btn_prev.setEnabled(tem)
        self.btn_next.setEnabled(tem)
        if tem:
            self.table.setCurrentCell(0, COL_VISTA)
        else:
            self._show_empty()

    def _show_empty(self) -> None:
        self.lbl_pos.setText("")
        self.lbl_nav_state.setText("")
        if self._report.flags == 0:
            self.lbl_detail.setText("Nenhuma flag reconhecida neste desenho")
        else:
            self.lbl_detail.setText("Nenhuma flag nesta lista")
        self.lbl_where.setText("Execute o Check novamente para confirmar.")

    def _on_row_changed(self, atual, _anterior) -> None:
        if atual.isValid():
            self._go(atual.row())

    def _go(self, linha: int) -> None:
        self._current = linha
        it = self._rows[linha]
        self.lbl_pos.setText(f"{linha + 1} de {len(self._rows)}")
        self.lbl_detail.setText(f"{mostrar(it.before)}  ›  {mostrar(it.after)}   |   {ff.NOME_RESULTADO[it.result]}")
        self.lbl_where.setText(f"{it.sheet_name} › {it.view_name} › {it.tipo}")
        self.lbl_where.setToolTip(self.lbl_where.text())
        self._set_nav_state("Indo até a flag", T.AMBER)
        self._nav_request += 1
        self.latest_nav.emit(self._nav_request)
        self.go_requested.emit(self._report, it, self._nav_request)

    def on_nav_done(self, request: int, ok: bool) -> None:
        if request != self._nav_request:
            return
        if ok:
            self._set_nav_state("Selecionada no CATIA", T.GREEN)
        else:
            self._set_nav_state("", T.RED)
            self.lbl_detail.setText(NAO_ENCONTRADO)

    def _set_nav_state(self, texto: str, cor: str) -> None:
        self.lbl_nav_state.setText(f"●  {texto}" if texto else "")
        self.lbl_nav_state.setStyleSheet(f"color: {cor};")

    def _select(self, linha: int) -> None:
        if linha == self._current:
            self._go(linha)
        else:
            self.table.setCurrentCell(linha, COL_VISTA)

    def _on_next(self) -> None:
        if self._rows:
            self._select((self._current + 1) % len(self._rows))

    def _on_prev(self) -> None:
        if self._rows:
            self._select((self._current - 1) % len(self._rows))

    def set_compact(self, compact: bool) -> None:
        self._lateral.setVisible(not compact)
        self._cartoes.setVisible(not compact)
        for coluna in (COL_FOLHA, COL_VISTA, COL_TIPO):
            self.table.setColumnHidden(coluna, compact)
        self.table.horizontalHeader().setSectionResizeMode(COL_DEPOIS, QHeaderView.Stretch if compact else QHeaderView.Fixed)
        self._tag.setVisible(not compact)
        self.btn_ok.setVisible(not compact)
        self.btn_again.setText("Corrigir" if compact else "Corrigir de novo")
