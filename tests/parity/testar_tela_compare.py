"""Testa o botao do Compare DWG, abrindo um programa de verdade. Nao precisa do CATIA.

Uso:  python tests/parity/testar_tela_compare.py [pasta para as imagens]
A configuracao real do usuario nao e tocada: o teste usa uma pasta temporaria.
"""
import os
import sys
import tempfile
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "..", "src"))

trabalho = tempfile.mkdtemp(prefix="compare dwg com espaco ")
os.environ["E1DWGTOOLS_CONFIG"] = os.path.join(trabalho, "cfg", "config.json")
os.environ["E1DWGTOOLS_COMPARE_PADRAO"] = ""  # sem o caminho da rede, como antes

from PySide6.QtCore import QCoreApplication, QEventLoop, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QFileDialog  # noqa: E402

from engine import compare_dwg as cd  # noqa: E402
from ui_qt.hub_window import PAGINA_COMPARE, HubWindow  # noqa: E402

IMAGENS = sys.argv[1] if len(sys.argv) > 1 else None
falhas = []


def confere(nome, ok, extra=""):
    print(f"[{'OK' if ok else 'FALHOU'}] {nome}{' ' + str(extra) if extra != '' else ''}", flush=True)
    if not ok:
        falhas.append(nome)


def espera(condicao, limite=8.0):
    fim = time.perf_counter() + limite
    while time.perf_counter() < fim:
        QCoreApplication.processEvents(QEventLoop.AllEvents, 50)
        if condicao():
            return True
        time.sleep(0.02)
    return False


def foto(j, nome):
    if IMAGENS:
        os.makedirs(IMAGENS, exist_ok=True)
        j.grab().save(os.path.join(IMAGENS, nome + ".png"))


def clica(b):
    QTest.mouseClick(b, Qt.LeftButton)


# Um "programa" de verdade: um .cmd que grava em que pasta rodou. Em pasta com espaco de proposito.
marca = os.path.join(trabalho, "abriu.txt")
programa = os.path.join(trabalho, "Compare DWG.cmd")
with open(programa, "w", encoding="ascii") as f:
    f.write(f'@cd > "{marca}"\r\n')

escolhas = []
QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: (escolhas.pop(0), ""))

app = QApplication(sys.argv)
j = HubWindow()
j.show()
p = j.compare_page
clica(j.pills["Check"])
clica(j.rail_buttons["Compare DWG"])
confere("o trilho leva ao Compare DWG", j._pages.currentIndex() == PAGINA_COMPARE)
confere("sem caminho, pede para adicionar", p.btn_abrir.text() == "ADICIONAR O CAMINHO DO COMPARE DWG", p.btn_abrir.text())
foto(j, "compare_1_sem_caminho")

escolhas.append(("",))
escolhas[0] = ""
clica(p.btn_abrir)
confere("cancelar não guarda nada", cd.get_path() == "" and not os.path.exists(marca))

escolhas.append(programa.replace("\\", "/"))
clica(p.btn_abrir)
confere("guarda o caminho do jeito do Windows", cd.get_path() == programa, cd.get_path())
confere("adicionar o caminho já abre o programa", espera(lambda: os.path.exists(marca)))
confere("o programa roda na própria pasta", espera(lambda: open(marca, encoding="ascii", errors="replace").read().strip().lower() == trabalho.lower()))
confere("o botão passa a abrir", p.btn_abrir.text() == "ABRIR O COMPARE DWG")
foto(j, "compare_2_com_caminho")

os.remove(marca)
clica(p.btn_abrir)
confere("clicar de novo abre de novo", espera(lambda: os.path.exists(marca)))

j.close()
j2 = HubWindow()
j2.show()
confere("o caminho continua guardado depois de fechar", j2.compare_page.btn_abrir.text() == "ABRIR O COMPARE DWG" and cd.get_path() == programa)
clica(j2.pills["Check"])
clica(j2.rail_buttons["Visão geral"])
os.remove(marca)
clica(j2.geral_page.linha_compare.btn_revisar)
confere("a Visão geral também abre", espera(lambda: os.path.exists(marca)))
foto(j2, "compare_3_visao_geral")

# O programa mudou de lugar.
os.remove(programa)
j2.compare_page._atualizar()
confere("programa sumido avisa", j2.compare_page.btn_abrir.text() == "ESCOLHER O CAMINHO DE NOVO", j2.compare_page.linha_caminho._texto.text())
escolhas.append("")
clica(j2.rail_buttons["Compare DWG"])
clica(j2.compare_page.btn_abrir)
confere("cancelar mantém o aviso, sem erro", j2.compare_page.btn_abrir.text() == "ESCOLHER O CAMINHO DE NOVO")
j2.close()

print("RESULTADO:", "TUDO CERTO" if not falhas else f"{len(falhas)} FALHAS: {falhas}", flush=True)
sys.stdout.flush()
os._exit(1 if falhas else 0)
