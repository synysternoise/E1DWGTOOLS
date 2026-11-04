"""Cores e estilos do HUB, iguais aos do prototipo em design/hub_prototipo.html."""

APP = "#081321"
HEADER = "#0A1828"
PANEL = "#0E1E32"
CARD = "#12263D"
CARD_2 = "#172E49"
LINE = "#24405C"
LINE_SOFT = "#1A3049"
TEXT = "#E8EEF5"
MUTED = "#93A7BE"
DIM = "#6A809A"
CYAN = "#19C6E6"
CYAN_HI = "#3AD4F0"
CYAN_INK = "#04222C"
BRAND = "#005BAF"
BRAND_HI = "#0A6FCC"
GREEN = "#2ECC71"
GREEN_BG = "#0F3B2A"
GREEN_LINE = "#1E6B45"
AMBER = "#E6A23C"
RED = "#F0695C"
RED_BG = "#3A1A1C"
RED_INK = "#2A0B08"
GREEN_INK = "#06281A"

QSS = f"""
* {{ font-family: "Segoe UI"; font-size: 13px; color: {TEXT}; }}
QWidget#janela {{ background: {APP}; }}
QFrame#cabecalho {{ background: {HEADER}; }}
QFrame#acento {{ background: {CYAN}; }}
QFrame#painel {{ background: {PANEL}; border: 1px solid {LINE_SOFT}; border-radius: 10px; }}
QFrame#nota {{ background: {CARD}; border-radius: 8px; }}
QFrame#detalhe {{ background: {CARD}; border: 1px solid {LINE}; border-radius: 8px; }}
QFrame#pilulas {{ background: {PANEL}; border: 1px solid {LINE}; border-radius: 23px; }}
QLabel {{ background: transparent; }}
QLabel#selo {{ background: {CYAN}; color: {CYAN_INK}; border-radius: 12px; font-size: 16px; font-weight: 700; }}
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
QLabel#etiqueta {{ color: {GREEN}; background: {GREEN_BG}; border: 1px solid {GREEN_LINE}; border-radius: 10px;
    padding: 0 9px; font-size: 11px; font-weight: 700; }}
QLabel#chipEstado {{ font-size: 12px; font-weight: 600; }}

QPushButton {{ border: 0; background: transparent; }}
QPushButton#pilula {{ height: 34px; padding: 0 16px; border-radius: 17px; color: {MUTED}; font-weight: 600;
    border: 1px solid transparent; }}
QPushButton#pilula:hover {{ background: {CARD}; color: {TEXT}; }}
QPushButton#pilula:checked {{ background: {BRAND}; color: #FFFFFF; border-color: {CYAN}; }}
QPushButton#janelaBtn {{ color: {MUTED}; font-size: 15px; }}
QPushButton#janelaBtn:hover {{ background: {CARD}; color: {TEXT}; }}
QPushButton#fecharBtn {{ color: {MUTED}; font-size: 15px; }}
QPushButton#fecharBtn:hover {{ background: {RED}; color: {RED_INK}; }}
QPushButton#trilho {{ text-align: left; height: 44px; padding: 0 12px; border-radius: 8px; font-weight: 600;
    border: 1px solid transparent; }}
QPushButton#trilho:hover {{ background: {CARD}; }}
QPushButton#trilho:checked {{ background: {CARD_2}; border-color: {CYAN}; }}
QPushButton#trilho:disabled {{ color: {DIM}; }}
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
QProgressBar {{ background: {CARD}; border: 0; border-radius: 5px; height: 10px; }}
QProgressBar::chunk {{ background: {CYAN}; border-radius: 5px; }}
QMessageBox, QInputDialog {{ background: {PANEL}; }}
QDialog QPushButton {{ background: {CARD}; border: 1px solid {LINE}; border-radius: 6px; padding: 6px 18px; font-weight: 600; }}
QLineEdit {{ background: {APP}; border: 1px solid {LINE}; border-radius: 6px; padding: 5px; }}
QToolTip {{ background: {CARD}; color: {TEXT}; border: 1px solid {LINE}; }}
"""
