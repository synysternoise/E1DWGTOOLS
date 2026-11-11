"""Cores e estilos do HUB, iguais aos do prototipo em design/hub_prototipo.html."""

APP = "#060D1C"
HEADER = "#0A1530"
PANEL = "#0F1E3D"
CARD = "#15284F"
CARD_2 = "#1B3261"
LINE = "#22396B"
LINE_SOFT = "#18294F"
TEXT = "#E9EFFB"
MUTED = "#93A6C9"
DIM = "#5F7299"
# O destaque continua com o nome antigo (CYAN) para nao mexer nas telas: agora e azul.
CYAN = "#3B82FF"
CYAN_HI = "#5A97FF"
CYAN_INK = "#FFFFFF"
SKY = "#6FD0FF"
BRAND = "#005BAF"
BRAND_HI = "#0A6FCC"
GREEN = "#2ECC71"
GREEN_BG = "#0F3B2A"
GREEN_LINE = "#1E6B45"
AMBER = "#E6A23C"
AMBER_BG = "#3A2A12"
AMBER_LINE = "#6B4E1E"
RED = "#F0695C"
RED_BG = "#3A1A1C"
RED_LINE = "#6E2C2A"
RED_INK = "#2A0B08"
GREEN_INK = "#06281A"

QSS = f"""
* {{ font-family: "Segoe UI"; font-size: 13px; color: {TEXT}; }}
QWidget#janela {{ background: {APP}; }}
QFrame#cabecalho {{ background: {HEADER}; }}
QFrame#painel {{ background: {PANEL}; border: 1px solid {LINE_SOFT}; border-radius: 12px; }}
QFrame#voo {{ background: {HEADER}; border-top: 1px solid {LINE_SOFT}; }}
QFrame#mini {{ background: {HEADER}; border: 1px solid {LINE}; }}
QFrame#faixa {{ background: {APP}; }}
QFrame#flutuante {{ background: {PANEL}; border: 1px solid {LINE}; }}
QFrame#flutuante QFrame#voo {{ background: {APP}; border: 1px solid {LINE_SOFT}; border-radius: 8px; }}
QFrame#risco {{ background: {LINE}; }}
QFrame#linhaCartao {{ border-bottom: 1px solid {LINE_SOFT}; }}
QLabel#pontoCatia {{ font-size: 11px; color: {RED}; }}
QFrame#kv {{ background: {CARD}; border: 1px solid {LINE}; border-radius: 8px; }}
QFrame#linhaLista {{ background: {CARD}; border: 1px solid {LINE}; border-radius: 8px; }}
QFrame#linhaListaOff {{ background: {PANEL}; border: 1px solid {LINE_SOFT}; border-radius: 8px; }}
QFrame#statNeutro {{ background: {CARD}; border: 1px solid {LINE}; border-radius: 8px; }}
QFrame#statVerde {{ background: {GREEN_BG}; border: 1px solid {GREEN_LINE}; border-radius: 8px; }}
QFrame#statAmbar {{ background: {AMBER_BG}; border: 1px solid {AMBER_LINE}; border-radius: 8px; }}
QFrame#statVermelho {{ background: {RED_BG}; border: 1px solid {RED_LINE}; border-radius: 8px; }}
QFrame#linhaOk {{ background: {GREEN_BG}; border: 1px solid {GREEN_LINE}; border-radius: 8px; }}
QFrame#linhaErro {{ background: {RED_BG}; border: 1px solid {RED_LINE}; border-radius: 8px; }}
QFrame#linhaAviso {{ background: {AMBER_BG}; border: 1px solid {AMBER_LINE}; border-radius: 8px; }}
QFrame#linhaNeutra {{ background: {CARD}; border: 1px solid {LINE}; border-radius: 8px; }}
QFrame#avisoAmbar {{ background: {AMBER_BG}; border: 1px solid {AMBER_LINE}; border-radius: 8px; }}
QFrame#iconeGrande {{ background: {CARD}; border: 1px solid {LINE}; border-radius: 14px; }}
QFrame#segFundo {{ background: {APP}; border: 1px solid {LINE}; border-radius: 8px; }}
QFrame#etiqueta {{ border: 1px solid {GREEN_LINE}; border-radius: 11px; }}
QFrame#etiquetaAviso {{ border: 1px solid {AMBER_LINE}; border-radius: 11px; }}
QFrame#etiquetaInfo {{ border: 1px dashed {CYAN}; border-radius: 11px; }}
QFrame#passoAtual {{ background: {CARD}; border: 1px solid {CYAN}; border-radius: 8px; }}
QFrame#nota {{ background: {CARD}; border-radius: 8px; }}
QFrame#detalhe {{ background: {CARD}; border: 1px solid {LINE}; border-radius: 8px; }}
QFrame#pilulas {{ background: {PANEL}; border: 1px solid {LINE}; border-radius: 23px; }}
QLabel {{ background: transparent; }}
QLabel#selo {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {CYAN}, stop:1 #1746B8); color: #FFFFFF;
    border-radius: 11px; font-size: 16px; font-weight: 700; }}
QLabel#marca {{ font-size: 18px; font-weight: 700; }}
QLabel#marcaSub {{ font-size: 9px; font-weight: 700; color: {MUTED}; }}
QLabel#titulo {{ font-size: 19px; font-weight: 700; }}
QLabel#sub {{ color: {MUTED}; }}
QLabel#secao {{ font-size: 11px; font-weight: 700; color: {MUTED}; }}
QLabel#notaTexto {{ color: {MUTED}; font-size: 12px; }}
QLabel#detalheForte {{ font-size: 14px; font-weight: 600; }}
QLabel#detalheFraco {{ color: {MUTED}; font-size: 12px; }}
QLabel#posicao {{ font-size: 18px; font-weight: 700; }}
QLabel#erro {{ color: {RED}; }}
QLabel#chip {{ background: {CARD}; border-radius: 14px; padding: 0 12px; font-size: 12px; font-weight: 600; }}
QLabel#etiquetaTexto {{ color: {GREEN}; font-size: 10px; font-weight: 700; }}
QLabel#etiquetaAvisoTexto {{ color: {AMBER}; font-size: 10px; font-weight: 700; }}
QLabel#etiquetaInfoTexto {{ color: {CYAN}; font-size: 10px; font-weight: 700; }}
QLabel#statNumero {{ font-size: 26px; font-weight: 700; }}
QLabel#statLegenda {{ font-size: 12px; font-weight: 600; }}
QLabel#kvNome {{ color: {MUTED}; }}
QLabel#kvValor {{ font-weight: 700; }}
QLabel#linhaTexto {{ font-weight: 600; font-size: 12px; }}
QLabel#avisoTexto {{ font-size: 12px; }}
QLabel#subtitulo2 {{ font-size: 13px; font-weight: 700; }}
QLabel#porcento {{ font-size: 38px; font-weight: 700; }}
QLabel#passoNome {{ font-size: 14px; font-weight: 600; }}
QLabel#passoNomeOff {{ font-size: 14px; font-weight: 600; color: {MUTED}; }}
QLabel#passoSub {{ color: {MUTED}; font-size: 12px; }}
QLabel#numeroOrdem {{ color: {CYAN}; font-weight: 700; font-size: 14px; }}
QLabel#selo2 {{ border-radius: 9px; font-size: 11px; font-weight: 700; padding: 0 6px; }}
QLabel#contagem {{ background: {RED}; color: {RED_INK}; border-radius: 9px; font-size: 11px; font-weight: 700; padding: 0 5px; }}
QLabel#log {{ color: {MUTED}; font-size: 12px; }}
QLabel#etiquetaAviso {{ color: {AMBER}; background: {AMBER_BG}; border: 1px solid {AMBER_LINE}; border-radius: 10px;
    padding: 0 9px; font-size: 11px; font-weight: 700; }}
QLabel#chipEstado {{ font-size: 12px; font-weight: 600; }}

QPushButton {{ border: 0; background: transparent; }}
QPushButton#pilula {{ height: 34px; padding: 0 16px; border-radius: 17px; color: {MUTED}; font-weight: 600;
    border: 1px solid transparent; }}
QPushButton#pilula:hover {{ background: {CARD}; color: {TEXT}; }}
QPushButton#pilula:checked {{ background: {BRAND}; color: #FFFFFF; border-color: {CYAN}; }}
QPushButton#miniBtn {{ border-radius: 10px; border: 1px solid transparent; }}
QPushButton#miniBtn:hover {{ background: {CARD}; }}
QPushButton#miniBtn:checked {{ background: {CARD_2}; border-color: {CYAN}; }}
QPushButton#miniAba {{ border-radius: 8px; color: {MUTED}; font-weight: 700; font-size: 12px; border: 1px solid transparent; }}
QPushButton#miniAba:hover {{ background: {CARD}; color: {TEXT}; }}
QPushButton#miniAba:checked {{ background: {BRAND}; color: #FFFFFF; border-color: {CYAN}; }}
QPushButton#janelaBtn {{ color: {MUTED}; font-size: 15px; }}
QPushButton#janelaBtn:hover {{ background: {CARD}; color: {TEXT}; }}
QPushButton#fecharBtn {{ color: {MUTED}; font-size: 15px; }}
QPushButton#fecharBtn:hover {{ background: {RED}; color: {RED_INK}; }}
QPushButton#trilho {{ text-align: left; height: 40px; padding: 0 10px; border-radius: 8px; font-weight: 600;
    border: 1px solid transparent; }}
QPushButton#trilho:hover {{ background: {CARD}; }}
QPushButton#trilho:checked {{ background: {CARD_2}; border-color: {CYAN}; }}
QPushButton#trilho:disabled {{ color: {DIM}; }}
QPushButton#grande {{ background: {CYAN}; color: {CYAN_INK}; border-radius: 8px; font-weight: 700; font-size: 14px; padding: 0 18px; }}
QPushButton#grande:hover {{ background: {CYAN_HI}; }}
QPushButton#grande:disabled {{ background: {CARD}; color: {DIM}; }}
QPushButton#perigo {{ background: transparent; border: 1px solid {RED}; border-radius: 8px; color: {RED}; font-weight: 700; height: 44px; }}
QPushButton#perigo:hover {{ background: {RED_BG}; }}
QPushButton#perigo:disabled {{ color: {DIM}; border-color: {LINE}; }}
QPushButton#seg {{ height: 30px; border-radius: 5px; color: {MUTED}; font-weight: 600; padding: 0 12px; }}
QPushButton#seg:hover {{ color: {TEXT}; }}
QPushButton#seg:checked {{ background: {BRAND}; color: #FFFFFF; }}
QPushButton#formato {{ background: {CARD}; border: 1px solid {LINE}; border-radius: 6px; font-weight: 700; height: 34px; }}
QPushButton#formato:hover {{ border-color: {DIM}; }}
QPushButton#formato:checked {{ background: {BRAND}; border-color: {CYAN}; color: #FFFFFF; }}
QPushButton#caixa {{ background: {APP}; border: 1px solid {LINE}; border-radius: 4px; }}
QPushButton#caixa:checked {{ background: {CYAN}; border-color: {CYAN}; }}
QPushButton#caixa:disabled {{ background: {PANEL}; border-color: {LINE_SOFT}; }}
QPushButton#ligacao {{ color: {CYAN}; font-weight: 600; }}
QPushButton#ligacao:hover {{ color: {CYAN_HI}; }}
QPushButton#primario {{ background: {CYAN}; color: {CYAN_INK}; border-radius: 8px; font-weight: 700; height: 40px; padding: 0 22px; }}
QPushButton#primario:hover {{ background: {CYAN_HI}; }}
QPushButton#primario:disabled {{ background: {CARD}; color: {DIM}; }}
QPushButton#secundario {{ background: {CARD}; border: 1px solid {LINE}; border-radius: 8px; font-weight: 700; height: 38px; padding: 0 16px; }}
QPushButton#secundario:hover {{ border-color: {DIM}; }}
QPushButton#secundario:disabled {{ color: {DIM}; }}
QPushButton#filtro {{ height: 30px; padding: 0 13px; border-radius: 15px; border: 1px solid {LINE}; color: {MUTED};
    font-weight: 600; font-size: 12px; }}
QPushButton#filtro:hover {{ color: {TEXT}; border-color: {DIM}; }}
QPushButton#filtro:checked {{ background: {CARD_2}; border-color: {CYAN}; color: {TEXT}; }}

QTableWidget {{ background: {APP}; border: 1px solid {LINE_SOFT}; border-radius: 8px; outline: 0; }}
QTableWidget::item {{ border-bottom: 1px solid {LINE_SOFT}; padding: 0 6px; }}
QTableWidget::item:selected {{ background: {BRAND}; color: #FFFFFF; }}
QHeaderView {{ background: {APP}; }}
QHeaderView::section {{ background: {APP}; color: {MUTED}; border: 0; border-bottom: 1px solid {LINE_SOFT};
    font-size: 11px; font-weight: 700; padding: 6px; }}
QScrollBar:vertical {{ background: {APP}; width: 10px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {LINE}; border-radius: 5px; min-height: 24px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QProgressBar#acento {{ background: {LINE}; border: 0; border-radius: 0; height: 2px; }}
QProgressBar#acento::chunk {{ background: {CYAN}; border-radius: 0; }}
QProgressBar {{ background: {CARD}; border: 0; border-radius: 5px; height: 10px; }}
QProgressBar::chunk {{ background: {CYAN}; border-radius: 5px; }}
QMessageBox, QInputDialog {{ background: {PANEL}; }}
QDialog QPushButton {{ background: {CARD}; border: 1px solid {LINE}; border-radius: 6px; padding: 6px 18px; font-weight: 600; }}
QSpinBox {{ background: {APP}; border: 1px solid {LINE}; border-radius: 6px; padding: 4px 6px; font-weight: 700; }}
QSpinBox:disabled {{ color: {DIM}; }}
QLineEdit {{ background: {APP}; border: 1px solid {LINE}; border-radius: 6px; padding: 5px; }}
QComboBox {{ background: {APP}; border: 1px solid {LINE}; border-radius: 6px; padding: 5px 8px; font-weight: 700; }}
QComboBox:disabled {{ color: {DIM}; }}
QComboBox QAbstractItemView {{ background: {PANEL}; border: 1px solid {LINE}; selection-background-color: {BRAND}; outline: 0; }}
QToolTip {{ background: {CARD}; color: {TEXT}; border: 1px solid {LINE}; }}
"""
