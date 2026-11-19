"""Pecas do layout novo: o voo de progresso, a barra de icones e o cartao de resumo.

Nada aqui fala com o CATIA. O voo so se redesenha quando chega um aviso de progresso que a
ferramenta ja mandava: nao tem relogio nem estimativa de tempo.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QBoxLayout, QButtonGroup, QFrame, QHBoxLayout, QLabel, QPushButton, QStackedWidget, QVBoxLayout, QWidget,
)

from ui_qt import theme as T
from ui_qt.font_size_page import button, label
from ui_qt.icones import icone, pixmap

ALTURA_VOO = 52
ALTURA_VOO_COMPACTO = 46
LARGURA_MINI = 60
LARGURA_CARTAO = 250
INCLINACAO = 20.0  # graus do nariz na decolagem e na descida
NARIZ_NO_POUSO = 5.0  # graus para cima logo antes de tocar a pista


def altura_no_arco(p: float, altura: float) -> float:
    """Quanto o aviao esta acima da pista: 0 nas pontas, altura no meio."""
    p = min(1.0, max(0.0, p))
    return 4.0 * altura * p * (1.0 - p)


def inclinacao(p: float) -> float:
    """Graus do nariz. Sobe na decolagem e desce na aproximacao; no fim arredonda o pouso:
    levanta um pouco o nariz antes de tocar a pista e fica reto no chao."""
    p = min(1.0, max(0.0, p))
    if p <= 0.8:
        return INCLINACAO * (1.0 - 2.0 * p) * min(1.0, p / 0.04)
    descida = INCLINACAO * (1.0 - 2.0 * 0.8)
    if p <= 0.95:
        return descida + (p - 0.8) / 0.15 * (NARIZ_NO_POUSO - descida)
    return NARIZ_NO_POUSO * (1.0 - p) / 0.05


def fracao(atual: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return min(1.0, max(0.0, atual / total))


class Voo(QFrame):
    """Barra de progresso: um aviao decola na esquerda, faz o arco e pousa na direita."""

    def __init__(self, compacto: bool = False):
        super().__init__()
        self.setObjectName("voo")
        self.setFixedHeight(ALTURA_VOO_COMPACTO if compacto else ALTURA_VOO)
        self._compacto = compacto
        self._p = 0.0
        self._titulo = ""
        self._estado = "Pronto para decolar"

    # ---- o que a janela informa ----
    def titulo(self, texto: str) -> None:
        self._titulo = texto
        self.update()

    def ocupado(self, ocupado: bool) -> None:
        if ocupado:
            self._p = 0.0
            self._estado = "CATIA trabalhando"
        else:
            self._p = 1.0
            self._estado = "Pousou: CATIA livre"
        self.update()

    def progresso(self, atual: int, total: int) -> None:
        if total <= 0:
            return
        self._p = fracao(atual, total)
        self._estado = f"{atual} de {total}"
        self.update()

    def definir(self, p: float, estado: str) -> None:
        self._p = min(1.0, max(0.0, p))
        self._estado = estado
        self.update()

    def posicao(self) -> float:
        return self._p

    def estado(self) -> str:
        return self._estado

    # ---- desenho ----
    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        g = QPainter(self)
        g.setRenderHint(QPainter.Antialiasing)
        g.setRenderHint(QPainter.SmoothPixmapTransform)
        largura, altura = self.width(), self.height()
        margem = 10 if self._compacto else 16
        esquerda = margem if self._compacto else min(210, largura // 3)
        direita = largura - margem - (40 if self._compacto else 54)

        fonte = QFont("Segoe UI")
        if not self._compacto:
            fonte.setPixelSize(12)
            fonte.setBold(True)
            g.setFont(fonte)
            g.setPen(QColor(T.TEXT))
            texto = g.fontMetrics().elidedText(self._titulo or "Progresso", Qt.ElideRight, esquerda - margem - 8)
            g.drawText(QRect(margem, 7, esquerda - margem - 8, 16), Qt.AlignLeft | Qt.AlignVCenter, texto)
            fonte.setBold(False)
            fonte.setPixelSize(11)
            g.setFont(fonte)
            g.setPen(QColor(T.MUTED))
            g.drawText(QRect(margem, 24, esquerda - margem - 8, 15), Qt.AlignLeft | Qt.AlignVCenter, self._estado)

        fonte.setBold(True)
        fonte.setPixelSize(13 if self._compacto else 16)
        g.setFont(fonte)
        g.setPen(QColor(T.TEXT))
        g.drawText(QRect(direita, 0, largura - margem - direita, altura), Qt.AlignRight | Qt.AlignVCenter, f"{round(self._p * 100)}%")

        x0, x1 = esquerda + 18, direita - 24
        if x1 - x0 < 40:
            g.end()
            return
        base, pico = altura - 9.0, altura - 20.0
        arco = QPainterPath(QPointF(x0, base))
        arco.quadTo(QPointF((x0 + x1) / 2.0, base - 2.0 * pico), QPointF(x1, base))
        g.setPen(QPen(QColor(T.LINE), 1))
        g.drawLine(QPointF(x0 - 12, base + 1), QPointF(x1 + 12, base + 1))  # a pista
        tracejado = QPen(QColor(T.LINE), 1.4, Qt.DashLine)
        g.setPen(tracejado)
        g.drawPath(arco)
        x = x0 + self._p * (x1 - x0)
        if self._p > 0:
            g.save()
            g.setClipRect(QRectF(x0 - 2, 0, x - x0 + 2, altura))
            g.setPen(QPen(QColor(T.CYAN), 2.6, Qt.SolidLine, Qt.RoundCap))
            g.drawPath(arco)
            g.restore()
        y = base - altura_no_arco(self._p, pico)
        g.translate(x, y - 5)
        g.rotate(-inclinacao(self._p))
        aviao = pixmap("jet", T.SKY, 30)
        g.drawPixmap(QRectF(-15, -15, 30, 30), aviao, QRectF(aviao.rect()))
        g.end()


class Barra(QFrame):
    """Abas e ferramentas so com icones. Em pe e a barra do canto; deitada e a faixa do modo canto."""

    ferramenta = Signal(int, str, int)  # aba, nome, pagina
    aba = Signal(int)
    modo = Signal(int)

    def __init__(self, abas, em_pe: bool, modo_canto: int = 1, modo_cheio: int = 0):
        """abas: lista de (nome da aba, [(nome, icone, pagina), ...])."""
        super().__init__()
        self.setObjectName("mini" if em_pe else "faixa")
        self._em_pe = em_pe
        direcao = QBoxLayout.TopToBottom if em_pe else QBoxLayout.LeftToRight
        col = QBoxLayout(direcao, self)
        col.setSpacing(4)
        if em_pe:
            self.setFixedWidth(LARGURA_MINI)
            col.setContentsMargins(0, 9, 0, 9)
            logo = label("", "selo")
            logo.setFixedSize(38, 38)
            logo.setAlignment(Qt.AlignCenter)
            logo.setPixmap(pixmap("plane", "#FFFFFF", 24))
            col.addWidget(logo, 0, Qt.AlignHCenter)
            self.ponto = label("●", "pontoCatia")
            self.ponto.setAlignment(Qt.AlignCenter)
            col.addWidget(self.ponto, 0, Qt.AlignHCenter)
        else:
            col.setContentsMargins(12, 6, 12, 0)

        self._grupo_abas = QButtonGroup(self)
        self.botoes_aba = []
        for i, (nome, _itens) in enumerate(abas):
            b = button(nome[0], "miniAba")
            b.setCheckable(True)
            b.setChecked(i == 0)
            b.setToolTip(nome)
            b.setFixedSize(42 if em_pe else 30, 28)
            self._grupo_abas.addButton(b, i)
            col.addWidget(b, 0, Qt.AlignCenter)
            self.botoes_aba.append(b)
        self._grupo_abas.idClicked.connect(self.aba)
        col.addWidget(self._risco(), 0, Qt.AlignCenter)

        self._pilha = QStackedWidget()
        self.botoes = {}
        self.selos = {}
        self._grupos = []
        self._por_pagina = {}
        for i, (_nome, itens) in enumerate(abas):
            pagina = QWidget()
            lin = QBoxLayout(direcao, pagina)
            lin.setContentsMargins(0, 0, 0, 0)
            lin.setSpacing(4)
            grupo = QButtonGroup(pagina)
            for nome, ic, indice in itens:
                b = QPushButton()
                b.setObjectName("miniBtn")
                b.setCursor(Qt.PointingHandCursor)
                b.setCheckable(True)
                b.setFixedSize(42, 42)
                b.setIcon(icone(ic, T.TEXT, 19))
                b.setToolTip(nome)
                b.clicked.connect(lambda _=False, a=i, n=nome, p=indice: self.ferramenta.emit(a, n, p))
                selo = QLabel("", b)
                selo.setObjectName("selo2")
                selo.setFixedHeight(15)
                selo.hide()
                grupo.addButton(b)
                lin.addWidget(b, 0, Qt.AlignCenter)
                self.botoes[nome] = b
                self.selos[nome] = selo
                self._por_pagina[indice] = b
            lin.addStretch(1)
            self._grupos.append(grupo)
            self._pilha.addWidget(pagina)
        col.addWidget(self._pilha, 0 if em_pe else 1, Qt.AlignHCenter if em_pe else Qt.Alignment())
        if em_pe:
            col.addStretch(1)
            col.addWidget(self._risco(), 0, Qt.AlignCenter)
            self.btn_canto = self._botao_modo("dock", "Abrir no canto da tela", modo_canto)
            self.btn_cheio = self._botao_modo("expand", "Abrir ampliado", modo_cheio)
            col.addWidget(self.btn_canto, 0, Qt.AlignCenter)
            col.addWidget(self.btn_cheio, 0, Qt.AlignCenter)

    def _risco(self) -> QFrame:
        r = QFrame()
        r.setObjectName("risco")
        r.setFixedSize(*((32, 1) if self._em_pe else (1, 26)))
        return r

    def _botao_modo(self, ic: str, dica: str, modo: int) -> QPushButton:
        b = QPushButton()
        b.setObjectName("miniBtn")
        b.setCursor(Qt.PointingHandCursor)
        b.setFixedSize(42, 36)
        b.setIcon(icone(ic, T.MUTED, 17))
        b.setToolTip(dica)
        b.clicked.connect(lambda: self.modo.emit(modo))
        return b

    def selecionar(self, aba: int, pagina: int) -> None:
        self.botoes_aba[aba].setChecked(True)
        self._pilha.setCurrentIndex(aba)
        b = self._por_pagina.get(pagina)
        if b is not None:
            b.setChecked(True)

    def selo(self, nome: str, n: int, cor: str, fundo: str) -> None:
        selo = self.selos.get(nome)
        if selo is None:
            return
        selo.setText(str(n))
        selo.setStyleSheet(f"color: {cor}; background: {fundo}; border-radius: 7px; font-size: 10px; padding: 0 4px;")
        selo.adjustSize()
        selo.move(42 - selo.width() - 1, 1)
        selo.setVisible(n > 0)

    def catia(self, cor: str, dica: str) -> None:
        if self._em_pe:
            self.ponto.setStyleSheet(f"color: {cor};")
            self.ponto.setToolTip(dica)

    def mousePressEvent(self, event) -> None:
        # Sem moldura: arrastar pela barra move a janela.
        if self._em_pe and event.button() == Qt.LeftButton and self.window().windowHandle():
            self.window().windowHandle().startSystemMove()


class CartaoResumo(QFrame):
    """Cartao que abre ao lado da barra de icones: resumo da ferramenta e o botao de executar."""

    executar = Signal()
    abrir = Signal()

    def __init__(self, dono: QWidget):
        super().__init__(dono, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setObjectName("flutuante")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedWidth(LARGURA_CARTAO)
        col = QVBoxLayout(self)
        col.setContentsMargins(14, 12, 14, 14)
        col.setSpacing(8)
        self.lbl_aba = label("", "secao")
        self.lbl_nome = label("", "titulo")
        self.lbl_nome.setWordWrap(True)
        col.addWidget(self.lbl_aba)
        col.addWidget(self.lbl_nome)
        self._linhas = QVBoxLayout()
        self._linhas.setSpacing(2)
        col.addLayout(self._linhas)
        self.voo = Voo(compacto=True)
        col.addWidget(self.voo)
        self.lbl_estado = label("", "notaTexto")
        col.addWidget(self.lbl_estado)
        self.btn_executar = button("EXECUTAR", "grande")
        self.btn_executar.setIcon(icone("play", T.CYAN_INK, 16, T.DIM, 4))
        self.btn_executar.setFixedHeight(42)
        self.btn_executar.clicked.connect(self.executar)
        col.addWidget(self.btn_executar)
        self.btn_abrir = button("ABRIR NO CANTO", "secundario")
        self.btn_abrir.clicked.connect(self.abrir)
        col.addWidget(self.btn_abrir)

    def preencher(self, aba: str, nome: str, linhas) -> None:
        """linhas: lista de (nome, valor)."""
        self.lbl_aba.setText(aba.upper())
        self.lbl_nome.setText(nome)
        while self._linhas.count():
            item = self._linhas.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for nome_linha, valor in linhas:
            linha = QFrame()
            linha.setObjectName("linhaCartao")
            h = QHBoxLayout(linha)
            h.setContentsMargins(0, 4, 0, 4)
            h.addWidget(label(nome_linha, "kvNome"), 1)
            h.addWidget(label(str(valor), "kvValor"))
            self._linhas.addWidget(linha)
        self.lbl_estado.setText(self.voo.estado())
        self.adjustSize()

    def encostar(self, ancora: QRect) -> None:
        """Fica a esquerda da barra; se nao couber, a direita."""
        x = ancora.left() - self.width() - 8
        if x < 0:
            x = ancora.right() + 8
        self.move(x, ancora.top())
