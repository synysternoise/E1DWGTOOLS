"""Base das telas de ferramenta: inicio, em andamento e resultado.

Cada ferramenta informa os textos, o tipo de documento e monta a parte do resultado.
"""
from __future__ import annotations

import os
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QHeaderView, QMessageBox, QInputDialog, QProgressBar, QSizePolicy,
    QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from ui_qt.font_size_page import button, label

PAGINA_INICIO, PAGINA_ANDAMENTO, PAGINA_RESULTADO = range(3)


def tabela(colunas, larguras: dict, esticar: int) -> QTableWidget:
    t = QTableWidget(0, len(colunas))
    t.setHorizontalHeaderLabels(colunas)
    t.verticalHeader().hide()
    t.setShowGrid(False)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.setSelectionMode(QAbstractItemView.SingleSelection)
    t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    t.verticalHeader().setDefaultSectionSize(34)
    cab = t.horizontalHeader()
    cab.setHighlightSections(False)
    cab.setSectionResizeMode(QHeaderView.Fixed)
    cab.setSectionResizeMode(esticar, QHeaderView.Stretch)
    cab.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    for coluna, largura in larguras.items():
        t.setColumnWidth(coluna, largura)
    return t


def preencher(t: QTableWidget, linhas) -> None:
    t.clearContents()
    t.setRowCount(len(linhas))
    for i, linha in enumerate(linhas):
        for j, texto in enumerate(linha):
            cel = QTableWidgetItem(str(texto))
            cel.setToolTip(str(texto))
            t.setItem(i, j, cel)


class ToolPage(QWidget):
    run_requested = Signal(str)
    stop_requested = Signal()
    retry_requested = Signal()
    answered = Signal(str)

    TOOL = ""
    TITULO = ""
    DESCRICAO = ""
    BOTAO = "EXECUTAR"
    BOTAO_DE_NOVO = "Executar de novo"
    ANDAMENTO = ""
    EXTENSAO = ".catdrawing"
    NOME_DOCUMENTO = "CATDrawing"
    ETIQUETA = "ALTERA O DESENHO"
    PODE_PARAR = True

    def __init__(self):
        super().__init__()
        self._report = None
        self._connected = False
        self._has_document = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._stack = QStackedWidget()
        layout.addWidget(self._stack)
        self._stack.addWidget(self._build_intro())
        self._stack.addWidget(self._build_running())
        self._stack.addWidget(self._build_results_page())
        self._update_intro()

    # ------------------------------------------------------------------
    # Telas
    # ------------------------------------------------------------------
    def _build_intro(self) -> QWidget:
        w = QWidget()
        col = QVBoxLayout(w)
        col.setContentsMargins(22, 18, 22, 18)
        col.addStretch(1)
        self._intro_title = label(self.TITULO, "titulo")
        self._intro_title.setAlignment(Qt.AlignCenter)
        self._intro_title.setWordWrap(True)
        self._intro_sub = label("", "sub")
        self._intro_sub.setAlignment(Qt.AlignCenter)
        self._intro_sub.setWordWrap(True)
        self._intro_error = label("", "erro")
        self._intro_error.setAlignment(Qt.AlignCenter)
        self._intro_error.setWordWrap(True)
        self._intro_error.hide()
        # Texto longo nao pode impedir a janela de encolher no modo compacto.
        for rotulo in (self._intro_title, self._intro_sub, self._intro_error):
            rotulo.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.btn_run = button(self.BOTAO, "primario")
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
        w = QWidget()
        col = QVBoxLayout(w)
        col.setContentsMargins(22, 18, 22, 18)
        col.addStretch(1)
        t = label(self.ANDAMENTO, "titulo")
        t.setAlignment(Qt.AlignCenter)
        self._run_text = label("", "sub")
        self._run_text.setAlignment(Qt.AlignCenter)
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(10)
        self.btn_stop = button("PARAR", "secundario")
        self.btn_stop.clicked.connect(self._on_stop)
        self.btn_stop.setVisible(self.PODE_PARAR)
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

    def _build_results_page(self) -> QWidget:
        w = QWidget()
        col = QVBoxLayout(w)
        col.setContentsMargins(18, 14, 18, 14)
        col.setSpacing(10)
        topo = QHBoxLayout()
        textos = QVBoxLayout()
        textos.setSpacing(1)
        textos.addWidget(label(self.TITULO, "titulo"))
        self.lbl_sub = label("", "sub")
        self.lbl_sub.setWordWrap(True)
        self.lbl_sub.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        textos.addWidget(self.lbl_sub)
        topo.addLayout(textos, 1)
        self._tag = label(self.ETIQUETA, "etiquetaAviso")
        self._tag.setFixedHeight(20)
        topo.addWidget(self._tag, 0, Qt.AlignTop)
        self.btn_again = button(self.BOTAO_DE_NOVO, "secundario")
        self.btn_again.clicked.connect(self._pedir)
        topo.addWidget(self.btn_again, 0, Qt.AlignTop)
        col.addLayout(topo)
        self.lbl_error = label("", "erro")
        self.lbl_error.setWordWrap(True)
        self.lbl_error.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.lbl_error.hide()
        col.addWidget(self.lbl_error)
        self._build_results(col)
        return w

    def _build_results(self, col: QVBoxLayout) -> None:
        raise NotImplementedError

    def _show_report(self, report) -> None:
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Estado do CATIA e tela inicial
    # ------------------------------------------------------------------
    def set_catia_state(self, connected: bool, document: str) -> None:
        self._connected = connected
        self._has_document = document.lower().endswith(self.EXTENSAO)
        self._update_intro()

    def _update_intro(self) -> None:
        if not self._connected:
            self._intro_title.setText("O CATIA não está aberto")
            self._intro_sub.setText("Abra o CATIA com o documento. O HUB percebe sozinho e libera a ferramenta.")
            self.btn_run.setText("PROCURAR DE NOVO")
        elif not self._has_document:
            self._intro_title.setText(f"Nenhum {self.NOME_DOCUMENTO} aberto")
            self._intro_sub.setText(f"Abra um {self.NOME_DOCUMENTO} no CATIA. O HUB percebe sozinho e libera a ferramenta.")
            self.btn_run.setText("PROCURAR DE NOVO")
        else:
            self._intro_title.setText(self.TITULO)
            self._intro_sub.setText(self.DESCRICAO)
            self.btn_run.setText(self.BOTAO)
        self.btn_again.setEnabled(self._connected and self._has_document)

    def _on_intro_button(self) -> None:
        if self._connected and self._has_document:
            self._pedir()
        else:
            self.retry_requested.emit()

    def _pedir(self) -> None:
        self.run_requested.emit(self.TOOL)

    # ------------------------------------------------------------------
    # Execucao
    # ------------------------------------------------------------------
    def on_started(self) -> None:
        self._intro_error.hide()
        self.bar.setRange(0, 0)
        self._run_text.setText("Conferindo o documento")
        self.btn_stop.setEnabled(True)
        self._stack.setCurrentIndex(PAGINA_ANDAMENTO)

    def on_progress(self, atual: int, total: int) -> None:
        self.bar.setRange(0, total)
        self.bar.setValue(atual)
        self._run_text.setText(f"{atual} de {total}")

    def on_status(self, texto: str) -> None:
        self._run_text.setText(texto)

    def _on_stop(self) -> None:
        self.btn_stop.setEnabled(False)
        self._run_text.setText("Parando ao fim do item atual")
        self.stop_requested.emit()

    def on_ask(self, pergunta: str, titulo: str, sugestao: str) -> None:
        self.answered.emit(self._perguntar(pergunta, titulo, sugestao))

    def _perguntar(self, pergunta: str, titulo: str, sugestao: str) -> str:
        texto, ok = QInputDialog.getText(self, titulo, pergunta.replace("\r\n", "\n"), text=sugestao)
        return texto if ok else ""

    def on_warn(self, mensagem: str, titulo: str) -> None:
        QMessageBox.warning(self, titulo, mensagem.replace("\r\n", "\n"))

    def on_info(self, mensagem: str, titulo: str) -> None:
        QMessageBox.information(self, titulo, mensagem.replace("\r\n", "\n"))

    def on_failed(self, mensagem: str, report) -> None:
        texto = mensagem.replace("\r\n", "\n")
        if report is None:
            self._intro_error.setText(texto)
            self._intro_error.show()
            self._stack.setCurrentIndex(PAGINA_INICIO)
            return
        self.on_ready(report)
        self.lbl_error.setText(texto)
        self.lbl_error.show()

    def on_ready(self, report) -> None:
        if report is None:  # cancelou ou nao havia o que fazer: nada mudou
            self._stack.setCurrentIndex(PAGINA_RESULTADO if self._report else PAGINA_INICIO)
            return
        self._report = report
        self.lbl_error.hide()
        self._show_report(report)
        self._stack.setCurrentIndex(PAGINA_RESULTADO)

    def set_compact(self, compact: bool) -> None:
        self._tag.setVisible(not compact)


def abrir_pasta(pasta: str) -> None:
    if pasta and os.path.isdir(pasta):
        os.startfile(pasta)  # noqa: S606
