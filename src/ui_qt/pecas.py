"""Pecas visuais do prototipo: moldura, etiqueta, cartao de numero, resumo, linha de situacao."""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

from ui_qt import theme as T
from ui_qt.font_size_page import button, label
from ui_qt.icones import icone, pixmap


FOLGA_ICONE = 4


def moldura(nome: str = "painel") -> QFrame:
    f = QFrame()
    f.setObjectName(nome)
    return f


def largura_livre(rotulo: QLabel) -> QLabel:
    """Texto longo nao pode impedir a janela de encolher."""
    rotulo.setWordWrap(True)
    rotulo.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
    return rotulo


def botao(texto: str, nome: str, ic: str = "", cor: str = T.TEXT, tam: int = 16) -> QPushButton:
    b = button(texto, nome)
    if ic:
        b.setIcon(icone(ic, cor, tam, T.DIM, FOLGA_ICONE))
        b.setIconSize(QSize(tam + 2 * FOLGA_ICONE, tam))
    return b


def botao_grande(texto: str, ic: str = "play") -> QPushButton:
    b = botao(texto, "grande", ic, T.CYAN_INK)
    b.setFixedHeight(46)
    return b


def etiqueta(texto: str, tipo: str = "altera") -> QWidget:
    """altera: ambar, com lapis. confere: verde, com escudo. cria: ciano."""
    nome, ic, cor = {
        "altera": ("etiquetaAviso", "pencil", T.AMBER),
        "confere": ("etiqueta", "shield", T.GREEN),
        "cria": ("etiquetaInfo", "file", T.CYAN),
    }[tipo]
    f = moldura(nome)
    f.setFixedHeight(22)
    h = QHBoxLayout(f)
    h.setContentsMargins(8, 0, 9, 0)
    h.setSpacing(5)
    i = QLabel()
    i.setPixmap(pixmap(ic, cor, 12))
    t = label(texto, nome + "Texto")
    h.addWidget(i)
    h.addWidget(t)
    return f


def cabecalho(titulo: str, tag=None, botao_direita=None):
    """Titulo, subtitulo e, a direita, etiqueta e botao. Devolve o layout e o rotulo do subtitulo."""
    topo = QHBoxLayout()
    textos = QVBoxLayout()
    textos.setSpacing(1)
    textos.addWidget(label(titulo, "titulo"))
    sub = largura_livre(label("", "sub"))
    textos.addWidget(sub)
    topo.addLayout(textos, 1)
    if tag is not None:
        topo.addWidget(tag, 0, Qt.AlignTop)
    if botao_direita is not None:
        topo.addWidget(botao_direita, 0, Qt.AlignTop)
    return topo, sub


class Cartao(QFrame):
    """Numero grande com legenda. tom: verde, ambar, vermelho ou neutro."""

    def __init__(self, legenda: str, tom: str = "neutro"):
        super().__init__()
        self.setObjectName({"verde": "statVerde", "ambar": "statAmbar", "vermelho": "statVermelho"}.get(tom, "statNeutro"))
        self.setFixedHeight(50)
        h = QHBoxLayout(self)
        h.setContentsMargins(14, 0, 14, 0)
        h.setSpacing(8)
        cor = {"verde": T.GREEN, "ambar": T.AMBER, "vermelho": T.RED}.get(tom, T.TEXT)
        self.numero = label("0", "statNumero")
        self.numero.setStyleSheet(f"color: {cor};")
        self.legenda = label(legenda, "statLegenda")
        self.legenda.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        h.addWidget(self.numero)
        h.addWidget(self.legenda, 1)

    def valor(self, n) -> None:
        self.numero.setText(str(n))


class Resumo(QFrame):
    """Lista de nome e valor, como o painel Resumo do prototipo."""

    def __init__(self, nomes):
        super().__init__()
        self.setObjectName("kv")
        col = QVBoxLayout(self)
        col.setContentsMargins(12, 6, 12, 6)
        col.setSpacing(0)
        self.valores = {}
        for nome in nomes:
            linha = QHBoxLayout()
            linha.setContentsMargins(0, 5, 0, 5)
            n = label(nome, "kvNome")
            n.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            linha.addWidget(n, 1)
            v = label("-", "kvValor")
            linha.addWidget(v)
            col.addLayout(linha)
            self.valores[nome] = v

    def definir(self, nome: str, valor, cor: str = "") -> None:
        self.valores[nome].setText(str(valor))
        self.valores[nome].setStyleSheet(f"color: {cor};" if cor else "")


class LinhaSituacao(QFrame):
    """Faixa com uma pilula: ok (verde), erro (vermelho), neutro ou espera."""

    def __init__(self):
        super().__init__()
        self.setFixedHeight(36)
        h = QHBoxLayout(self)
        h.setContentsMargins(10, 0, 12, 0)
        h.setSpacing(10)
        self._pilula = QLabel()
        self._pilula.setFixedSize(34, 20)
        self._pilula.setAlignment(Qt.AlignCenter)
        self._texto = label("", "linhaTexto")
        self._texto.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        h.addWidget(self._pilula)
        h.addWidget(self._texto, 1)
        self.definir("neutro", "")

    def definir(self, estado: str, texto: str) -> None:
        nome, fundo, tinta, ic = {
            "ok": ("linhaOk", T.GREEN, T.GREEN_INK, "check"),
            "erro": ("linhaErro", T.RED, T.RED_INK, "x"),
            "aviso": ("linhaAviso", T.AMBER, T.RED_INK, "alert"),
            "neutro": ("linhaNeutra", T.CARD_2, T.MUTED, "minus"),
        }[estado]
        self.setObjectName(nome)
        self.setStyleSheet("")  # reaplica o QSS do novo nome
        self._pilula.setStyleSheet(f"background: {fundo}; border-radius: 10px;")
        self._pilula.setPixmap(pixmap(ic, tinta, 13, 2.6))
        self._texto.setText(texto)
        self.style().unpolish(self)
        self.style().polish(self)


class Segmentos(QFrame):
    """Escolha entre opcoes, como o seletor Completa / Sem Update Template / Minha selecao."""

    def __init__(self, opcoes):
        super().__init__()
        self.setObjectName("segFundo")
        h = QHBoxLayout(self)
        h.setContentsMargins(3, 3, 3, 3)
        h.setSpacing(2)
        self.grupo = QButtonGroup(self)
        self.botoes = []
        for i, texto in enumerate(opcoes):
            b = button(texto, "seg")
            b.setCheckable(True)
            b.setChecked(i == 0)
            self.grupo.addButton(b, i)
            h.addWidget(b, 1)
            self.botoes.append(b)


class Caixa(QPushButton):
    """Caixa de marcar do prototipo: quadrado ciano com o visto."""

    def __init__(self, marcada: bool = True):
        super().__init__()
        self.setObjectName("caixa")
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(20, 20)
        self.setIconSize(QSize(14, 14))
        self.setIcon(icone("check", T.CYAN_INK, 14))
        self.toggled.connect(self._desenhar)
        self.setChecked(marcada)
        self._desenhar(marcada)

    def _desenhar(self, marcada: bool) -> None:
        self.setIcon(icone("check", T.CYAN_INK, 14) if marcada else icone("minus", "#00000000", 14))


def aviso_catia_ocupado() -> QFrame:
    """O CATIA nao responde enquanto a ferramenta roda; sem este aviso parece travado."""
    f = moldura("avisoAmbar")
    h = QHBoxLayout(f)
    h.setContentsMargins(12, 9, 12, 9)
    h.setSpacing(10)
    i = QLabel()
    i.setPixmap(pixmap("alert", T.AMBER, 18))
    h.addWidget(i, 0, Qt.AlignTop)
    t = largura_livre(label(
        "O CATIA fica travado enquanto a ferramenta roda. É normal: não clique nele. "
        "O HUB continua respondendo e avisa quando terminar.", "avisoTexto"))
    h.addWidget(t, 1)
    return f


def icone_grande(nome: str) -> QFrame:
    f = moldura("iconeGrande")
    f.setFixedSize(64, 64)
    h = QHBoxLayout(f)
    h.setContentsMargins(0, 0, 0, 0)
    i = QLabel()
    i.setAlignment(Qt.AlignCenter)
    i.setPixmap(pixmap(nome, T.MUTED, 28))
    h.addWidget(i)
    return f
