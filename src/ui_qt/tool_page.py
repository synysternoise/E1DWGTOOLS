"""Base das telas de ferramenta: inicio, em andamento e resultado, no visual do prototipo.

Cada ferramenta informa os textos e o tipo de documento e monta o que for proprio dela. Se tiver
previa, a tela inicial mostra o que sera feito antes de executar, sem alterar nada no documento.
"""
from __future__ import annotations

import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QHeaderView, QInputDialog, QMessageBox, QProgressBar, QStackedWidget,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from ui_qt import theme as T
from ui_qt.font_size_page import label
from ui_qt.icones import icone
from ui_qt.pecas import (
    FOLGA_ICONE, LinhaSituacao, aviso_catia_ocupado, botao, botao_grande, cabecalho, etiqueta, icone_grande, largura_livre, moldura,
)

PAGINA_INICIO, PAGINA_ANDAMENTO, PAGINA_RESULTADO = range(3)
LARGURA_LATERAL = 300


def tabela(colunas, larguras: dict, esticar: int) -> QTableWidget:
    t = QTableWidget(0, len(colunas))
    t.setHorizontalHeaderLabels(colunas)
    t.verticalHeader().hide()
    t.setShowGrid(False)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.setSelectionMode(QAbstractItemView.SingleSelection)
    t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    t.verticalHeader().setDefaultSectionSize(36)
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


def abrir_pasta(pasta: str) -> None:
    if pasta and os.path.isdir(pasta):
        os.startfile(pasta)  # noqa: S606


def abrir_arquivo(caminho: str) -> None:
    if caminho and os.path.isfile(caminho):
        os.startfile(caminho)  # noqa: S606


class ToolPage(QWidget):
    run_requested = Signal(str)
    stop_requested = Signal()
    retry_requested = Signal()
    answered = Signal(str)
    preview_requested = Signal(str)

    TOOL = ""
    TITULO = ""
    DESCRICAO = ""
    BOTAO = "EXECUTAR"
    BOTAO_DE_NOVO = "Executar de novo"
    ANDAMENTO = ""
    EXTENSAO = ".catdrawing"
    NOME_DOCUMENTO = "CATDrawing"
    ETIQUETA = "ALTERA O DESENHO"
    TIPO_ETIQUETA = "altera"
    ICONE = "box"
    ICONE_BOTAO = "play"
    PODE_PARAR = True
    TEM_PREVIA = False

    def __init__(self):
        super().__init__()
        self._report = None
        self._connected = False
        self._has_document = False
        self._documento = ""
        self._previa = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._stack = QStackedWidget()
        layout.addWidget(self._stack)
        self._stack.addWidget(self._build_intro())
        self._stack.addWidget(self._build_running())
        self._stack.addWidget(self._build_results_page())
        self._update_intro()

    # ------------------------------------------------------------------
    # Tela inicial
    # ------------------------------------------------------------------
    def _build_intro(self) -> QWidget:
        w = QWidget()
        fora = QHBoxLayout(w)
        fora.setContentsMargins(0, 0, 0, 0)
        fora.setSpacing(12)
        caixa = moldura()
        col = QVBoxLayout(caixa)
        col.setContentsMargins(18, 14, 18, 14)
        col.setSpacing(10)
        self._intro_error = largura_livre(label("", "erro"))
        self._intro_error.setAlignment(Qt.AlignCenter)
        self._intro_error.hide()
        col.addWidget(self._intro_error)

        self.btn_run = botao_grande(self.BOTAO, self.ICONE_BOTAO)
        self.btn_run.clicked.connect(self._on_intro_button)
        self._pilha_intro = QStackedWidget()
        col.addWidget(self._pilha_intro, 1)

        # Sem o documento certo: icone, explicacao, situacao e botao, no centro.
        centro = QWidget()
        self._col_centro = QVBoxLayout(centro)
        self._col_centro.setSpacing(10)
        self._col_centro.addStretch(1)
        linha = QHBoxLayout()
        linha.addStretch(1)
        linha.addWidget(icone_grande(self.ICONE))
        linha.addStretch(1)
        self._col_centro.addLayout(linha)
        self._intro_title = largura_livre(label(self.TITULO, "titulo"))
        self._intro_title.setAlignment(Qt.AlignCenter)
        self._intro_sub = largura_livre(label("", "sub"))
        self._intro_sub.setAlignment(Qt.AlignCenter)
        self._col_centro.addWidget(self._intro_title)
        self._col_centro.addWidget(self._intro_sub)
        self._linha_catia = LinhaSituacao()
        self._linha_doc = LinhaSituacao()
        self._col_linhas = QVBoxLayout()
        self._col_linhas.setSpacing(6)
        self._col_linhas.addWidget(self._linha_catia)
        self._col_linhas.addWidget(self._linha_doc)
        self._col_centro.addLayout(self._col_linhas)
        self._col_centro.addSpacing(4)
        self._linha_botao = QHBoxLayout()
        self._col_centro.addLayout(self._linha_botao)
        self._col_centro.addStretch(2)
        self._pilha_intro.addWidget(centro)

        # Com o documento certo e previa: o que sera feito, e o botao embaixo.
        pronta = QWidget()
        self._col_pronta = QVBoxLayout(pronta)
        self._col_pronta.setContentsMargins(0, 0, 0, 0)
        self._col_pronta.setSpacing(10)
        if self.TEM_PREVIA:
            self._build_ready(self._col_pronta)
        self._pilha_intro.addWidget(pronta)
        fora.addWidget(caixa, 1)
        return w

    def _build_ready(self, col: QVBoxLayout) -> None:
        raise NotImplementedError

    def _show_preview(self, previa) -> None:
        raise NotImplementedError

    def _build_running(self) -> QWidget:
        w = moldura()
        col = QVBoxLayout(w)
        col.setContentsMargins(22, 18, 22, 18)
        col.setSpacing(12)
        col.addStretch(1)
        t = label(self.ANDAMENTO, "titulo")
        t.setAlignment(Qt.AlignCenter)
        self._run_text = largura_livre(label("", "sub"))
        self._run_text.setAlignment(Qt.AlignCenter)
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(10)
        self.btn_stop = botao("PARAR", "perigo", "stop", T.RED)
        self.btn_stop.clicked.connect(self._on_stop)
        self.btn_stop.setVisible(self.PODE_PARAR)
        col.addWidget(t)
        col.addWidget(self._run_text)
        col.addWidget(self.bar)
        col.addWidget(aviso_catia_ocupado())
        col.addWidget(self.btn_stop)
        col.addStretch(2)
        return w

    def _build_results_page(self) -> QWidget:
        w = QWidget()
        fora = QHBoxLayout(w)
        fora.setContentsMargins(0, 0, 0, 0)
        fora.setSpacing(12)
        self._fora_resultado = fora
        caixa = moldura()
        col = QVBoxLayout(caixa)
        col.setContentsMargins(18, 14, 18, 14)
        col.setSpacing(10)
        self._tag = etiqueta(self.ETIQUETA, self.TIPO_ETIQUETA)
        self.btn_again = botao(self.BOTAO_DE_NOVO, "secundario", "refresh")
        self.btn_again.clicked.connect(self._pedir)
        topo, self.lbl_sub = cabecalho(self.TITULO, self._tag, self.btn_again)
        col.addLayout(topo)
        self.lbl_error = largura_livre(label("", "erro"))
        self.lbl_error.hide()
        col.addWidget(self.lbl_error)
        self._build_results(col)
        fora.addWidget(caixa, 1)
        self._lateral = moldura()
        self._lateral.setFixedWidth(LARGURA_LATERAL)
        lateral = QVBoxLayout(self._lateral)
        lateral.setContentsMargins(14, 14, 14, 14)
        lateral.setSpacing(10)
        if self._build_side(lateral):
            fora.addWidget(self._lateral)
        else:
            self._lateral.hide()
        return w

    def _build_results(self, col: QVBoxLayout) -> None:
        raise NotImplementedError

    def _build_side(self, col: QVBoxLayout) -> bool:
        return False

    def _show_report(self, report) -> None:
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Estado do CATIA
    # ------------------------------------------------------------------
    def set_catia_state(self, connected: bool, document: str) -> None:
        mudou = document != self._documento or connected != self._connected
        self._connected = connected
        self._documento = document
        self._has_document = document.lower().endswith(self.EXTENSAO)
        self._update_intro()
        if mudou and self.TEM_PREVIA and self._connected and self._has_document:
            self.pedir_previa()

    def pedir_previa(self) -> None:
        self.preview_requested.emit(self.TOOL)

    def on_preview(self, previa) -> None:
        self._previa = previa
        if previa is not None:
            self._show_preview(previa)

    def _texto_botao(self) -> str:
        return self.BOTAO

    def _update_intro(self) -> None:
        pronto = self._connected and self._has_document
        if not self._connected:
            self._intro_title.setText("O CATIA não está aberto")
            self._intro_sub.setText("Abra o CATIA com o documento. O HUB percebe sozinho e libera a ferramenta.")
            self._linha_catia.definir("erro", "CATIA fechado")
            self._linha_doc.definir("neutro", f"{self.NOME_DOCUMENTO}: esperando o CATIA")
            self.btn_run.setText("PROCURAR DE NOVO")
        elif not self._has_document:
            self._intro_title.setText(f"Nenhum {self.NOME_DOCUMENTO} aberto")
            self._intro_sub.setText(f"Abra um {self.NOME_DOCUMENTO} no CATIA. O HUB percebe sozinho e libera a ferramenta.")
            self._linha_catia.definir("ok", "CATIA ativo")
            self._linha_doc.definir("erro", f"Nenhum {self.NOME_DOCUMENTO} ativo")
            self.btn_run.setText("PROCURAR DE NOVO")
        else:
            self._intro_title.setText(self.TITULO)
            self._intro_sub.setText(self.DESCRICAO)
            self.btn_run.setText(self._texto_botao())
        self.btn_run.setIcon(icone(self.ICONE_BOTAO if pronto else "refresh", T.CYAN_INK, 16, T.DIM, FOLGA_ICONE))
        self.btn_again.setEnabled(pronto)

        com_previa = pronto and self.TEM_PREVIA
        for rotulo in (self._linha_catia, self._linha_doc):
            rotulo.setVisible(not pronto)
        self._pilha_intro.setCurrentIndex(1 if com_previa else 0)
        # O mesmo botao serve aos dois modos: embaixo e largo, ou no centro.
        if com_previa:
            self.btn_run.setMaximumWidth(16777215)
            self._col_pronta.addWidget(self.btn_run)
        else:
            self.btn_run.setMaximumWidth(380)
            self._linha_botao.addWidget(self.btn_run)

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
        if self._lateral.layout().count():
            self._lateral.setVisible(not compact)
