"""Ponto de entrada do E1DWGTOOLS: inicia o HUB de ferramentas.

Uso:  python main.py   (com o CATIA V5 aberto, idealmente com um CATDrawing)
"""
import os
import sys

# Garante que 'src' esteja no path, rode de onde rodar.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from ui.main_window import MainWindow  # noqa: E402

if __name__ == "__main__":
    MainWindow().mainloop()
