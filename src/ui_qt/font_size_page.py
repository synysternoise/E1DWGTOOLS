"""Tela do Font Size Check: analisa o desenho e leva ate cada item fora do padrao."""
from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView, QButtonGroup, QFrame, QHBoxLayout, QHeaderView, QInputDialog, QLabel,
    QMessageBox, QProgressBar, QPushButton, QSizePolicy, QStackedWidget, QStyle,
    QStyledItemDelegate, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from engine import font_check as fc
from ui_qt import theme as T

NAO_ENCONTRADO = "Item não encontrado: foi apagado ou o desenho foi fechado."
COLUNAS = ("", "FOLHA", "VISTA", "TEXTO / COTA", "TAMANHO", "PADRÃO DA FOLHA")
COL_MARCA, COL_FOLHA, COL_VISTA, COL_TEXTO, COL_TAMANHO, COL_PADRAO = range(6)
PAPEL_OK = Qt.UserRole + 1


def label(texto: str, nome: str = "") -> QLabel:
    w = QLabel(texto)
    if nome:
        w.setObjectName(nome)
    return w


def button(texto: str, nome: str) -> QPushButton:
    w = QPushButton(texto)
    w.setObjectName(nome)
    w.setCursor(Qt.PointingHandCursor)
    return w


class MarkDelegate(QStyledItemDelegate):
    """Circulo da primeira coluna: verde, vermelho, ciano (OK manual) ou cinza (sem comparacao)."""

    def paint(self, painter: QPainter, option, index) -> None:
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, QColor(T.BRAND))
        ok = index.data(PAPEL_OK)
        d = 18
        r = QRect(option.rect.center().x() - d // 2, option.rect.center().y() - d // 2, d, d)
        painter.setPen(Qt.NoPen)
        manual = ok == "manual"
        neutro = ok is None
        painter.setBrush(QColor(T.CYAN if manual else (T.CARD_2 if neutro else (T.GREEN if ok else T.RED))))
        painter.drawEllipse(r)
        fonte = QFont("Segoe UI", 9)
        fonte.setBold(True)
        painter.setFont(fonte)
        painter.setPen(QColor(T.CYAN_INK if manual else (T.MUTED if neutro else (T.GREEN_INK if ok else T.RED_INK))))
        painter.drawText(r, Qt.AlignCenter, "–" if neutro else ("✓" if ok else "✕"))
        painter.restore()


class FontSizePage(QWidget):
    analyze_requested = Signal()
    stop_requested = Signal()
    retry_requested = Signal()
    go_requested = Signal(object, object, int)
    latest_nav = Signal(int)
    format_answered = Signal(str)

    def __init__(self):
        super().__init__()
        self._report: Optional[fc.FontReport] = None
        self._rows: List[fc.FontItem] = []
        self._removidos = 0
        self._current = -1
        self._nav_request = 0
        self._connected = False
        self._has_drawing = False
        self._compact = False

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
        w = QFrame()
        w.setObjectName("painel")
        col = QVBoxLayout(w)
        col.setContentsMargins(22, 18, 22, 18)
        col.addStretch(1)
        self._intro_title = label("Font Size Check", "titulo")
        self._intro_title.setAlignment(Qt.AlignCenter)
        self._intro_title.setWordWrap(True)
        self._intro_sub = label("", "sub")
        self._intro_sub.setAlignment(Qt.AlignCenter)
        self._intro_sub.setWordWrap(True)
        self._intro_error = label("", "erro")
        self._intro_error.setAlignment(Qt.AlignCenter)
        self._intro_error.setWordWrap(True)
        self._intro_error.hide()
        self.btn_analyze = button("ANALISAR", "primario")
        self.btn_analyze.clicked.connect(self._on_intro_button)
        col.addWidget(self._intro_title)
        col.addSpacing(6)
        col.addWidget(self._intro_sub)
        col.addSpacing(10)
        col.addWidget(self._intro_error)
        col.addSpacing(10)
        linha = QHBoxLayout()
        linha.addStretch(1)
        linha.addWidget(self.btn_analyze)
        linha.addStretch(1)
        col.addLayout(linha)
        col.addStretch(2)
        return w

    def _build_running(self) -> QWidget:
        w = QFrame()
        w.setObjectName("painel")
        col = QVBoxLayout(w)
        col.setContentsMargins(22, 18, 22, 18)
        col.addStretch(1)
        t = label("Analisando o desenho", "titulo")
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
        linha = QHBoxLayout()
        linha.addStretch(1)
        linha.addWidget(self.btn_stop)
        linha.addStretch(1)
        col.addLayout(linha)
        col.addStretch(2)
        return w

    def _build_results(self) -> QWidget:
        w = QFrame()
        w.setObjectName("painel")
        col = QVBoxLayout(w)
        col.setContentsMargins(18, 14, 18, 14)
        col.setSpacing(10)

        topo = QHBoxLayout()
        textos = QVBoxLayout()
        textos.setSpacing(1)
        textos.addWidget(label("Font Size Check", "titulo"))
        self.lbl_sub = label("", "sub")
        self.lbl_sub.setWordWrap(True)
        self.lbl_sub.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        textos.addWidget(self.lbl_sub)
        topo.addLayout(textos, 1)
        from ui_qt.pecas import botao, etiqueta  # aqui porque pecas importa este modulo

        self._tag = etiqueta("SÓ CONFERE", "confere")
        topo.addWidget(self._tag, 0, Qt.AlignTop)
        self.btn_again = botao("Analisar de novo", "secundario", "refresh")
        self.btn_again.clicked.connect(self.analyze_requested)
        topo.addWidget(self.btn_again, 0, Qt.AlignTop)
        col.addLayout(topo)

        filtros = QHBoxLayout()
        filtros.setSpacing(6)
        self._group = QButtonGroup(self)
        self.btn_nok = button("", "filtro")
        self.btn_ok = button("", "filtro")
        self.btn_all = button("", "filtro")
        for i, b in enumerate((self.btn_nok, self.btn_ok, self.btn_all)):
            b.setCheckable(True)
            self._group.addButton(b, i)
            filtros.addWidget(b)
        filtros.addStretch(1)
        self.btn_nok.setChecked(True)
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
        cab.setSectionResizeMode(COL_TEXTO, QHeaderView.Stretch)
        cab.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        for coluna, largura in ((COL_MARCA, 40), (COL_FOLHA, 100), (COL_VISTA, 130), (COL_TAMANHO, 80), (COL_PADRAO, 170)):
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
        # Texto longo sem espacos nao pode alargar a janela.
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
        self.btn_remove = botao("REMOVER ESTE TEXTO DA LISTA", "secundario")
        self.btn_remove.setToolTip("Tira da lista um texto que não precisa ser conferido. Não altera o desenho.")
        self.btn_remove.clicked.connect(self._remover)
        col.addWidget(self.btn_remove)
        return w

    # ------------------------------------------------------------------
    # Estado do CATIA e tela inicial
    # ------------------------------------------------------------------
    def set_catia_state(self, connected: bool, document: str) -> None:
        self._connected = connected
        self._has_drawing = document.lower().endswith(".catdrawing")
        self._update_intro()

    def _update_intro(self) -> None:
        if not self._connected:
            self._intro_title.setText("O CATIA não está aberto")
            self._intro_sub.setText("Abra o CATIA com o desenho. O HUB percebe sozinho e libera a análise.")
            self.btn_analyze.setText("PROCURAR DE NOVO")
        elif not self._has_drawing:
            self._intro_title.setText("Nenhum desenho aberto")
            self._intro_sub.setText("Abra um CATDrawing no CATIA. O HUB percebe sozinho e libera a análise.")
            self.btn_analyze.setText("PROCURAR DE NOVO")
        else:
            self._intro_title.setText("Font Size Check")
            self._intro_sub.setText("Confere o tamanho dos textos pelo formato de cada folha. O desenho não é alterado.")
            self.btn_analyze.setText("ANALISAR")
        self.btn_again.setEnabled(self._connected and self._has_drawing)

    def _on_intro_button(self) -> None:
        if self._connected and self._has_drawing:
            self.analyze_requested.emit()
        else:
            self.retry_requested.emit()

    # ------------------------------------------------------------------
    # Analise
    # ------------------------------------------------------------------
    def on_analysis_started(self) -> None:
        self._intro_error.hide()
        self.bar.setRange(0, 0)
        self._run_text.setText("Lendo o formato de cada folha")
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

    def on_failed(self, message: str) -> None:
        self._intro_error.setText(f"Falha ao executar Font Size Check.\n{message}")
        self._intro_error.show()
        self._stack.setCurrentIndex(0)

    def on_ask_format(self, question: str, title: str, default: str) -> None:
        texto, ok = QInputDialog.getText(self, title, question, text=default)
        self.format_answered.emit(texto if ok else "")

    def on_warn(self, message: str, title: str) -> None:
        QMessageBox.warning(self, title, message)

    def on_report(self, report: Optional[fc.FontReport]) -> None:
        if report is None:  # cancelou o pedido de formato: nada mudou
            self._stack.setCurrentIndex(2 if self._report else 0)
            return
        self._report = report
        self._removidos = 0
        self._contagens()
        self.btn_nok.setChecked(True)
        self._stack.setCurrentIndex(2)
        self._fill_table()

    def _contagens(self) -> None:
        report = self._report
        parou = "  ·  Parado antes do fim" if report.stopped else ""
        removidos = f"  ·  {self._removidos} removidos da lista" if self._removidos else ""
        self.lbl_sub.setText(
            f"PN {report.drawing_no}  ·  Formato {', '.join(report.formats)}  ·  "
            f"{report.total_items} itens analisados{removidos}{parou}"
        )
        self.btn_nok.setText(f"Fora do padrão ({report.total_nok})")
        self.btn_ok.setText(f"Corretos ({report.total_ok})")
        self.btn_all.setText(f"Todos ({report.total_items})")

    def _remover(self) -> None:
        """Tira da lista um texto que nao precisa ser conferido. O desenho nao muda."""
        if not 0 <= self._current < len(self._rows):
            return
        linha, it, r = self._current, self._rows[self._current], self._report
        if it in r.items:
            r.items.remove(it)
            r.total_nok -= 1
        else:
            r.ok_items.remove(it)
            r.total_ok -= 1
        r.total_items -= 1
        self._removidos += 1
        self._contagens()
        self._fill_table()
        if self._rows:
            self._select(min(linha, len(self._rows) - 1))

    # ------------------------------------------------------------------
    # Lista e navegacao
    # ------------------------------------------------------------------
    def _fill_table(self) -> None:
        r = self._report
        filtro = self._group.checkedId()
        if filtro == 0:
            self._rows = list(r.items)
        elif filtro == 1:
            self._rows = list(r.ok_items)
        else:
            self._rows = sorted(r.items + r.ok_items, key=lambda i: i.order)
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
                (COL_FOLHA, it.sheet_name), (COL_VISTA, it.view_name), (COL_TEXTO, it.text),
                (COL_TAMANHO, it.size), (COL_PADRAO, it.standard),
            ):
                cel = QTableWidgetItem(texto)
                cel.setToolTip(texto)
                if coluna in (COL_TAMANHO, COL_PADRAO):
                    cel.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if coluna == COL_TAMANHO:
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
            self.table.setCurrentCell(0, COL_TEXTO)
        else:
            self._show_empty()

    def _show_empty(self) -> None:
        r = self._report
        self.lbl_pos.setText("")
        self.lbl_nav_state.setText("")
        if self._group.checkedId() == 0:
            self.lbl_detail.setText("Nenhum item fora do padrão")
            self.lbl_where.setText("\n".join(r.standards))
        else:
            self.lbl_detail.setText("Nenhum item nesta lista")
            self.lbl_where.setText("")

    def _on_row_changed(self, atual, _anterior) -> None:
        if atual.isValid():
            self._go(atual.row())

    def _go(self, linha: int) -> None:
        self._current = linha
        it = self._rows[linha]
        self.lbl_pos.setText(f"{linha + 1} de {len(self._rows)}")
        self.lbl_detail.setText(f"Tamanho {it.size}   |   Padrão {it.standard}")
        self.lbl_where.setText(f"{it.sheet_name} › {it.view_name} › {it.text}")
        self.lbl_where.setToolTip(self.lbl_where.text())
        self._set_nav_state("Indo até o item", T.AMBER)
        self._nav_request += 1
        self.latest_nav.emit(self._nav_request)
        self.go_requested.emit(self._report, it, self._nav_request)

    def on_nav_done(self, request: int, ok: bool) -> None:
        if request != self._nav_request:
            return
        if ok:
            self._set_nav_state("Selecionado no CATIA", T.GREEN)
        else:
            self._set_nav_state("", T.RED)
            self.lbl_detail.setText(NAO_ENCONTRADO)

    def _set_nav_state(self, texto: str, cor: str) -> None:
        self.lbl_nav_state.setText(f"●  {texto}" if texto else "")
        self.lbl_nav_state.setStyleSheet(f"color: {cor};")

    def _select(self, linha: int) -> None:
        # Mudar a linha dispara a navegacao; com um item so ela nao muda, entao vai direto.
        if linha == self._current:
            self._go(linha)
        else:
            self.table.setCurrentCell(linha, COL_TEXTO)

    # Do ultimo volta para o primeiro e vice-versa, como no navegador do VBA.
    def _on_next(self) -> None:
        if self._rows:
            self._select((self._current + 1) % len(self._rows))

    def _on_prev(self) -> None:
        if self._rows:
            self._select((self._current - 1) % len(self._rows))

    def set_compact(self, compact: bool) -> None:
        self._compact = compact
        for coluna in (COL_FOLHA, COL_VISTA, COL_PADRAO):
            self.table.setColumnHidden(coluna, compact)
        self._tag.setVisible(not compact)
        self.btn_all.setVisible(not compact)
        self.btn_ok.setVisible(not compact)
        self.btn_again.setText("Analisar" if compact else "Analisar de novo")
