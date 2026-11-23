"""Gera o executavel do HUB: dist\\E1 Tools\\E1 Tools.exe (pasta inteira, sem precisar de Python no PC).

Uso, na pasta do programa:
    pip install pyinstaller
    python compilar.py

Para usar em outro PC, copie a pasta dist\\E1 Tools inteira. O .exe sozinho nao funciona.
"""
import io
import os
import shutil
import struct
import subprocess
import sys

RAIZ = os.path.dirname(os.path.abspath(__file__))
NOME = "E1 Tools"
BUILD = os.path.join(RAIZ, "build")
ICO = os.path.join(BUILD, "e1tools.ico")


def gerar_icone():
    """O mesmo icone da janela (src/ui_qt/icones.py), gravado em .ico para o Windows."""
    sys.path.insert(0, os.path.join(RAIZ, "src"))
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice
    from PySide6.QtGui import QGuiApplication

    app = QGuiApplication.instance() or QGuiApplication([])  # noqa: F841 (o Qt pede para desenhar)
    from ui_qt.icones import icone_app

    tamanhos = (16, 24, 32, 48, 64, 128, 256)
    pngs = []
    for tamanho in tamanhos:
        dados = QByteArray()
        buf = QBuffer(dados)
        buf.open(QIODevice.WriteOnly)
        icone_app().pixmap(tamanho, tamanho).save(buf, "PNG")
        pngs.append(bytes(dados))
    # Formato .ico: cabecalho, uma entrada por tamanho e as imagens PNG em seguida.
    saida = io.BytesIO()
    saida.write(struct.pack("<HHH", 0, 1, len(pngs)))
    deslocamento = 6 + 16 * len(pngs)
    for tamanho, png in zip(tamanhos, pngs):
        lado = 0 if tamanho >= 256 else tamanho
        saida.write(struct.pack("<BBBBHHII", lado, lado, 0, 0, 1, 32, len(png), deslocamento))
        deslocamento += len(png)
    for png in pngs:
        saida.write(png)
    os.makedirs(BUILD, exist_ok=True)
    with open(ICO, "wb") as f:
        f.write(saida.getvalue())


def compilar():
    sep = os.pathsep
    dados = [
        (os.path.join("src", "engine", "catia_scripts"), os.path.join("engine", "catia_scripts")),
    ]
    modelo = os.path.join("src", "engine", "vpm_modelo.xlsx")
    if os.path.exists(os.path.join(RAIZ, modelo)):
        dados.append((modelo, "engine"))
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed",
           "--name", NOME, "--icon", ICO, "--paths", "src",
           "--collect-submodules", "engine", "--collect-submodules", "ui_qt",
           # O HUB novo nao usa a interface antiga nem o pycatia: ficam fora para o pacote nao inchar.
           "--exclude-module", "customtkinter", "--exclude-module", "pycatia", "--exclude-module", "tkinter",
           "--exclude-module", "ui", "--exclude-module", "tools"]
    for origem, destino in dados:
        cmd += ["--add-data", f"{origem}{sep}{destino}"]
    cmd.append("main_qt.py")
    subprocess.run(cmd, cwd=RAIZ, check=True)
    shutil.rmtree(BUILD, ignore_errors=True)
    exe = os.path.join(RAIZ, "dist", NOME, NOME + ".exe")
    print(f"\nPronto: {exe}\nPara outro PC, copie a pasta dist\\{NOME} inteira.")


if __name__ == "__main__":
    gerar_icone()
    compilar()
