"""Ponto de entrada do novo HUB em PySide6.

Uso:  python main_qt.py   (com o CATIA V5 aberto)
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from PySide6.QtWidgets import QApplication  # noqa: E402

from ui_qt.hub_window import HubWindow  # noqa: E402
from ui_qt.icones import icone_app  # noqa: E402

if __name__ == "__main__":
    if sys.platform == "win32":
        # Sem isto o Windows agrupa a janela como "Python" e mostra o icone do Python na barra de tarefas.
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Embraer.E1Tools.HUB")
    app = QApplication(sys.argv)
    app.setWindowIcon(icone_app())
    janela = HubWindow()
    janela.show()
    sys.exit(app.exec())
