"""Ponto de entrada do novo HUB em PySide6.

Uso:  python main_qt.py   (com o CATIA V5 aberto)
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from PySide6.QtWidgets import QApplication  # noqa: E402

from ui_qt.hub_window import HubWindow  # noqa: E402

if __name__ == "__main__":
    app = QApplication(sys.argv)
    janela = HubWindow()
    janela.show()
    sys.exit(app.exec())
