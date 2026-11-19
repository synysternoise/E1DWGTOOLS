"""Telas da aba VPM: Criar PNs, Update Content e Criar e atualizar (sequencia).

O VPM abre no Edge, com o perfil da macro antiga (o login fica guardado). Um lote por vez: o Edge do lote
fica aberto para revisao ate o usuario clicar em Encerrar sessao.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QFileDialog, QHBoxLayout, QHeaderView, QLineEdit, QMessageBox, QPlainTextEdit,
    QProgressBar, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from engine import vpm_lote as L
from ui_qt import theme as T
from ui_qt.font_size_page import label
from ui_qt.pecas import botao, cabecalho, etiqueta, largura_livre, moldura

COLUNAS = ("PN", "AMBIENTE", "ARQUIVOS", "CRIAÇÃO", "CONTEÚDO", "MENSAGEM")
COL_PN, COL_AMB, COL_ARQ, COL_CRI, COL_CONT, COL_MSG = range(6)
TIPOS_TELA = (("CATDRAWING", "2D · CATDrawing"), ("CATPART", "3D · CATPart (experimental)"),
              ("CATPRODUCT", "3D · CATProduct (experimental)"))
ESTILO = f"""
QPlainTextEdit {{ background: {T.APP}; border: 1px solid {T.LINE_SOFT}; border-radius: 8px; color: {T.MUTED};
    font-size: 12px; padding: 6px; }}
QCheckBox {{ spacing: 8px; font-weight: 600; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border: 1px solid {T.LINE}; border-radius: 4px; background: {T.APP}; }}
QCheckBox::indicator:checked {{ background: {T.CYAN}; border-color: {T.CYAN}; }}
QCheckBox:disabled {{ color: {T.DIM}; }}
"""
TEXTOS = {
    L.MODO_CRIAR: ("Criar PNs por Duplicate",
                   "Lê a aba Entrada_Python do Excel (executar = SIM), duplica o PN de origem, preenche e confere os "
                   "atributos e cria o PN novo."),
    L.MODO_UPLOAD: ("Update Content",
                    "Atualiza o conteúdo de PNs que já existem no VPM com os arquivos da pasta. O PN sai do nome do "
                    "arquivo. 2D assistido; 3D experimental."),
    L.MODO_SEQUENCIA: ("Criar e atualizar",
                       "Para cada PN do Excel: cria e faz o Update Content dos arquivos dele antes de passar ao próximo."),
}
NOTAS = {
    L.MODO_CRIAR: "Para no primeiro erro. PNs confirmados no histórico local não são criados de novo. "
                  "Não há consulta prévia de existência no servidor.",
    L.MODO_UPLOAD: "Cada arquivo precisa ter um PN só no nome. Subpastas não entram. O Upload é confirmado por você "
                   "antes e depois do envio; o Commit não é automático.",
    L.MODO_SEQUENCIA: "Cada PN do Excel precisa de UM arquivo para CADA tipo marcado. Arquivos extras da pasta não são "
                      "enviados. Subpastas não entram.",
}

_lote_ativo = {"pagina": None}  # um lote por vez: o perfil do Edge so abre uma vez


class _Avisos:
    """A execucao roda na thread do lote: tudo vai para a tela por sinal."""

    def __init__(self, thread: "ExecutorVPM"):
        self.t = thread

    def log(self, texto: str) -> None:
        self.t.sinal_log.emit(texto)

    def mudou(self, indice: int, linha: dict) -> None:
        self.t.sinal_mudou.emit(indice, linha)

    def progresso(self, pct: int) -> None:
        self.t.sinal_progresso.emit(pct)

    def perguntar(self, texto: str) -> None:
        self.t.sinal_pergunta.emit(texto)

    def aviso(self, texto: str) -> None:
        self.t.sinal_aviso.emit(texto)

    def terminou(self, ok: bool, mensagem: str) -> None:
        self.t.sinal_terminou.emit(ok, mensagem)


class ExecutorVPM(QThread):
    sinal_log = Signal(str)
    sinal_mudou = Signal(int, object)
    sinal_progresso = Signal(int)
    sinal_pergunta = Signal(str)
    sinal_aviso = Signal(str)
    sinal_terminou = Signal(bool, str)

    def __init__(self, plano: List[dict], modo: str, criar: bool):
        super().__init__()
        from engine.vpm_execucao import ExecucaoVPM

        self.execucao = ExecucaoVPM(plano, modo, _Avisos(self), criar)  # historico ilegivel: ValueError aqui

    def run(self) -> None:
        self.execucao.rodar()


class VpmPage(QWidget):
    def __init__(self, modo: str):
        super().__init__()
        self.modo = modo
        self.plano: List[dict] = []
        self.executor: Optional[ExecutorVPM] = None
        self.rodando = False
        self.setStyleSheet(ESTILO)

        fora = QVBoxLayout(self)
        fora.setContentsMargins(0, 0, 0, 0)
        painel = moldura()
        fora.addWidget(painel)
        col = QVBoxLayout(painel)
        col.setContentsMargins(18, 16, 18, 16)
        col.setSpacing(10)
        titulo, texto = TEXTOS[modo]
        topo, sub = cabecalho(titulo, etiqueta("Altera o VPM", "altera"))
        sub.setText(texto)
        col.addLayout(topo)

        self.excel = self.pasta = self.ambiente = self.so_conferir = None
        self.tipos = {}
        if modo in (L.MODO_CRIAR, L.MODO_SEQUENCIA):
            linha = QHBoxLayout()
            self.excel = QLineEdit()
            self.excel.setReadOnly(True)
            self.excel.setPlaceholderText("Excel com a aba Entrada_Python")
            linha.addWidget(self.excel, 1)
            b = botao("Selecionar Excel", "secundario", "file")
            b.clicked.connect(self._escolher_excel)
            linha.addWidget(b)
            b = botao("Gerar modelo Excel", "secundario", "sheet")
            b.clicked.connect(self._gerar_modelo)
            linha.addWidget(b)
            col.addLayout(linha)
        if modo in (L.MODO_UPLOAD, L.MODO_SEQUENCIA):
            linha = QHBoxLayout()
            self.pasta = QLineEdit()
            self.pasta.setReadOnly(True)
            self.pasta.setPlaceholderText("Pasta com os arquivos CATIA (sem subpastas)")
            linha.addWidget(self.pasta, 1)
            b = botao("Selecionar pasta", "secundario", "open")
            b.clicked.connect(self._escolher_pasta)
            linha.addWidget(b)
            col.addLayout(linha)
            linha = QHBoxLayout()
            for tipo, texto_tipo in TIPOS_TELA:
                cb = QCheckBox(texto_tipo)
                cb.setChecked(tipo == "CATDRAWING")
                cb.toggled.connect(self._invalidar)
                self.tipos[tipo] = cb
                linha.addWidget(cb)
            linha.addStretch(1)
            if modo == L.MODO_UPLOAD:
                linha.addWidget(label("Ambiente", "sub"))
                self.ambiente = QLineEdit("EGN2ENG")
                self.ambiente.setFixedWidth(130)
                self.ambiente.textChanged.connect(self._invalidar)
                linha.addWidget(self.ambiente)
            col.addLayout(linha)
        if modo == L.MODO_CRIAR:
            self.so_conferir = QCheckBox("Só preencher e conferir, sem criar (cancela cada formulário)")
            self.so_conferir.toggled.connect(self._invalidar)
            col.addWidget(self.so_conferir)

        nota = moldura("nota")
        n = QVBoxLayout(nota)
        n.setContentsMargins(10, 8, 10, 8)
        n.addWidget(largura_livre(label(NOTAS[modo], "notaTexto")))
        col.addWidget(nota)

        linha = QHBoxLayout()
        self.btn_previa = botao("VALIDAR E MONTAR PRÉVIA", "secundario", "shield")
        self.btn_previa.clicked.connect(self.validar)
        linha.addWidget(self.btn_previa)
        linha.addStretch(1)
        self.btn_executar = botao("EXECUTAR PLANO", "primario", "play", T.CYAN_INK)
        self.btn_executar.setEnabled(False)
        self.btn_executar.clicked.connect(self.executar)
        linha.addWidget(self.btn_executar)
        col.addLayout(linha)

        self.tabela = QTableWidget(0, len(COLUNAS))
        self.tabela.setHorizontalHeaderLabels(COLUNAS)
        self.tabela.verticalHeader().hide()
        self.tabela.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabela.setSelectionBehavior(QAbstractItemView.SelectRows)
        cab = self.tabela.horizontalHeader()
        cab.setSectionResizeMode(QHeaderView.ResizeToContents)
        cab.setSectionResizeMode(COL_MSG, QHeaderView.Stretch)
        if modo == L.MODO_CRIAR:
            self.tabela.hideColumn(COL_ARQ)
            self.tabela.hideColumn(COL_CONT)
        elif modo == L.MODO_UPLOAD:
            self.tabela.hideColumn(COL_CRI)
        col.addWidget(self.tabela, 3)

        col.addWidget(label("ACOMPANHAMENTO", "secao"))
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(5000)
        col.addWidget(self.log, 2)
        self.barra = QProgressBar()
        self.barra.setTextVisible(False)
        self.barra.setFixedHeight(8)
        self.barra.setRange(0, 100)
        col.addWidget(self.barra)

        linha = QHBoxLayout()
        self.btn_parar = botao("Interromper", "perigo", "stop", T.RED)
        self.btn_parar.setEnabled(False)
        self.btn_parar.setFixedWidth(150)
        self.btn_parar.clicked.connect(self.parar)
        linha.addWidget(self.btn_parar)
        self.btn_encerrar = botao("Encerrar sessão", "secundario", "x")
        self.btn_encerrar.setEnabled(False)
        self.btn_encerrar.clicked.connect(self.encerrar_sessao)
        linha.addWidget(self.btn_encerrar)
        linha.addStretch(1)
        b = botao("Abrir pasta de resultados", "ligacao", "open", T.CYAN)
        b.clicked.connect(self._abrir_pasta)
        linha.addWidget(b)
        col.addLayout(linha)

    # ------------------------------------------------------------------
    # Entradas
    # ------------------------------------------------------------------
    def _escolher_excel(self) -> None:
        caminho, _ = QFileDialog.getOpenFileName(self, "Excel de entrada", "", "Excel (*.xlsx)")
        if caminho:
            self.excel.setText(caminho)
            self._invalidar()

    def _escolher_pasta(self) -> None:
        caminho = QFileDialog.getExistingDirectory(self, "Pasta dos arquivos CATIA")
        if caminho:
            self.pasta.setText(caminho)
            self._invalidar()

    def _abrir_pasta(self) -> None:
        L.PASTA.mkdir(parents=True, exist_ok=True)
        os.startfile(str(L.PASTA))  # noqa: S606 - pasta do proprio programa

    def _gerar_modelo(self) -> None:
        origem = L.caminho_do_modelo()
        if origem is None:
            resposta = QMessageBox.question(
                self, "Modelo do Excel",
                "O modelo com as listas suspensas ainda não está neste PC.\n\n"
                "Selecione o arquivo .py da macro antiga do VPM (o que tem o TEMPLATE_BASE64). "
                "O HUB tira o modelo de lá uma vez e guarda para as próximas.", QMessageBox.Ok | QMessageBox.Cancel)
            if resposta != QMessageBox.Ok:
                return
            macro, _ = QFileDialog.getOpenFileName(self, "Macro antiga do VPM", "", "Python (*.py *.pyw);;Todos (*.*)")
            if not macro:
                return
            try:
                dados = L.extrair_modelo_da_macro(macro)
                L.PASTA.mkdir(parents=True, exist_ok=True)
                origem = L.PASTA / "vpm_modelo.xlsx"
                origem.write_bytes(dados)
            except Exception as exc:  # noqa: BLE001
                QMessageBox.warning(self, "Modelo do Excel", str(exc))
                return
        destino, _ = QFileDialog.getSaveFileName(self, "Salvar modelo", "Modelo_VPM.xlsx", "Excel (*.xlsx)")
        if not destino:
            return
        if not destino.lower().endswith(".xlsx"):
            destino += ".xlsx"
        try:
            L.salvar_modelo_vazio(origem, destino)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Modelo do Excel", str(exc))
            return
        QMessageBox.information(self, "Modelo salvo", "Modelo salvo com as listas suspensas, sem PNs preenchidos. "
                                "Preencha os dados e marque SIM só nas linhas que devem rodar.")

    def _invalidar(self, *args) -> None:
        self.plano = []
        self.btn_executar.setEnabled(False)

    def _tipos_marcados(self) -> List[str]:
        return [t for t, cb in self.tipos.items() if cb.isChecked()]

    # ------------------------------------------------------------------
    # Previa e execucao
    # ------------------------------------------------------------------
    def validar(self) -> None:
        try:
            self.plano = L.montar_plano(
                self.modo, self.excel.text() if self.excel else "", self.pasta.text() if self.pasta else "",
                self._tipos_marcados(), self.ambiente.text().strip().upper() if self.ambiente else "")
        except ModuleNotFoundError as exc:
            self._invalidar()
            QMessageBox.warning(self, "Biblioteca faltando", f"Falta a biblioteca {exc.name}. Rode: python verificar.py")
            return
        except Exception as exc:  # noqa: BLE001 - erro de validacao vai inteiro para a tela
            self._invalidar()
            QMessageBox.warning(self, "Plano inválido", str(exc))
            return
        self.tabela.setRowCount(len(self.plano))
        for i, r in enumerate(self.plano):
            self._preencher_linha(i, r)
        self.btn_executar.setEnabled(not self.rodando)
        self.barra.setValue(0)
        self.log.appendPlainText(f"Prévia validada: {len(self.plano)} PNs. Nada foi enviado ao VPM.")

    def _preencher_linha(self, i: int, r: dict) -> None:
        arquivos = "; ".join(Path(f["arquivo"]).name for f in r["files"])
        for j, texto in ((COL_PN, r["pn"]), (COL_AMB, r["ambiente"]), (COL_ARQ, arquivos), (COL_CRI, r["criacao"]),
                         (COL_CONT, r["conteudo"]), (COL_MSG, r["mensagem"])):
            item = QTableWidgetItem(str(texto))
            item.setToolTip(str(texto))
            cor = self._cor(str(texto)) if j in (COL_CRI, COL_CONT) else ""
            if cor:
                item.setForeground(QColor(cor))
            self.tabela.setItem(i, j, item)

    @staticmethod
    def _cor(status: str) -> str:
        if status.startswith(("CONFIRMADO", "VALIDADO", "IGNORADO")):
            return T.GREEN
        if "INCERT" in status or status.startswith(("ERRO", "REVISAO")):
            return T.RED
        if status.startswith("EM_EXECUCAO") or status == "NAO_EXECUTADO":
            return T.AMBER
        return ""

    def executar(self) -> None:
        if not self.plano or self.rodando:
            return
        outra = _lote_ativo["pagina"]
        if outra is not None and outra is not self:
            QMessageBox.information(self, "VPM", "Já existe um lote do VPM aberto em outra tela. Termine e clique em "
                                    "Encerrar sessão nela antes de começar outro.")
            return
        if self.executor is not None and self.executor.isRunning():
            QMessageBox.information(self, "VPM", "O Edge do lote anterior ainda está aberto. Clique em Encerrar sessão.")
            return
        criar = not (self.so_conferir and self.so_conferir.isChecked())
        if self.modo == L.MODO_CRIAR and not criar:
            texto = f"Preencher e conferir {len(self.plano)} formulários e CANCELAR cada um, sem criar?"
        else:
            texto = (f"Executar {len(self.plano)} PNs?\nCriação e Upload alteram o VPM. O lote para no primeiro erro.\n"
                     "O Upload é assistido e o Commit não é automático.\n"
                     "Não há consulta prévia completa de existência no servidor.")
        if any(f["kind"] != "CATDRAWING" for r in self.plano for f in r["files"]):
            texto += ("\n\n3D EXPERIMENTAL: exige o documento DOCCAD do tipo certo já existente no VPM. Não cria "
                      "documentos ausentes nem importa dependências.")
        if QMessageBox.question(self, "Confirmar plano", texto, QMessageBox.Yes | QMessageBox.No,
                                QMessageBox.No) != QMessageBox.Yes:
            return
        try:
            self.executor = ExecutorVPM(self.plano, self.modo, criar)
        except ModuleNotFoundError as exc:
            QMessageBox.warning(self, "Biblioteca faltando", f"Falta a biblioteca {exc.name}. Rode: python verificar.py")
            return
        except Exception as exc:  # noqa: BLE001 - historico ilegivel
            QMessageBox.warning(self, "Histórico inválido", str(exc))
            return
        ex = self.executor
        ex.sinal_log.connect(self.log.appendPlainText)
        ex.sinal_mudou.connect(self._on_mudou)
        ex.sinal_progresso.connect(self.barra.setValue)
        ex.sinal_pergunta.connect(self._on_pergunta)
        ex.sinal_aviso.connect(self._on_aviso)
        ex.sinal_terminou.connect(self._on_terminou)
        ex.finished.connect(self._on_fim_da_sessao)
        _lote_ativo["pagina"] = self
        self.rodando = True
        self._habilitar(False)
        self.btn_parar.setEnabled(True)
        self.btn_encerrar.setEnabled(False)
        self.barra.setValue(0)
        ex.start()

    def _habilitar(self, sim: bool) -> None:
        for w in (self.excel, self.pasta, self.ambiente, self.so_conferir, *self.tipos.values()):
            if w is not None:
                w.setEnabled(sim)
        for b in self.findChildren(QPushButton):
            if b not in (self.btn_parar, self.btn_encerrar) and b.text() != "Abrir pasta de resultados":
                b.setEnabled(sim)
        self.btn_executar.setEnabled(sim and bool(self.plano))

    def _on_mudou(self, i: int, linha: dict) -> None:
        if 0 <= i < len(self.plano):
            self.plano[i] = linha
            self._preencher_linha(i, linha)
            self.tabela.selectRow(i)

    def _on_pergunta(self, texto: str) -> None:
        resposta = QMessageBox.question(self, "Verificação do VPM", texto, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if self.executor is not None:
            self.executor.execucao.responder(resposta == QMessageBox.Yes)

    def _on_aviso(self, texto: str) -> None:
        QMessageBox.warning(self, "PICS / interoperabilidade", texto)

    def _on_terminou(self, ok: bool, mensagem: str) -> None:
        self.rodando = False
        self.btn_parar.setEnabled(False)
        self.btn_encerrar.setEnabled(True)
        self.log.appendPlainText(mensagem)
        if ok:
            self.barra.setValue(100)

    def _on_fim_da_sessao(self) -> None:
        self.rodando = False
        if _lote_ativo["pagina"] is self:
            _lote_ativo["pagina"] = None
        self._habilitar(True)
        self.btn_parar.setEnabled(False)
        self.btn_encerrar.setEnabled(False)
        # Depois de um lote o plano antigo nao vale: os historicos mudaram.
        self._invalidar()

    def parar(self) -> None:
        if self.executor is not None:
            self.executor.execucao.parar.set()
            self.btn_parar.setEnabled(False)
            self.log.appendPlainText("Interrupção pedida. Aguarde a operação atual; o que já foi enviado não é desfeito.")

    def encerrar_sessao(self) -> None:
        if self.executor is not None:
            self.executor.execucao.encerrar.set()
            self.btn_encerrar.setEnabled(False)

    def pode_fechar(self) -> bool:
        """O HUB pergunta antes de fechar: um lote rodando nao pode ser cortado no meio."""
        if self.executor is None or not self.executor.isRunning():
            return True
        if self.rodando:
            QMessageBox.information(self, "VPM em execução", "Interrompa o lote do VPM e aguarde antes de fechar. "
                                    "Um Create ou Upload enviado não pode ser desfeito.")
            return False
        self.executor.execucao.encerrar.set()
        return self.executor.wait(4000)
