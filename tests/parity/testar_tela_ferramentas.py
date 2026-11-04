"""Testa as telas do Update Template, do Position and Zone e dos Splits, clicando nelas.

Uso (com o CATIA aberto e sem desenhos importantes abertos, porque fecha todos):
    python tests/parity/testar_tela_ferramentas.py <pasta de testes do update> <do poszone> <dos splits> [imagens]

As pastas sao as que os testes de paridade criam (paridade_update_*, paridade_poszone_*, paridade_splits_*).
"""
import os
import shutil
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "..", "src"))

import win32com.client as com  # noqa: E402
from PySide6.QtCore import QCoreApplication, QEventLoop, Qt, QTimer  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QInputDialog, QMessageBox  # noqa: E402

from engine import atualizar_template as at  # noqa: E402
from engine import pos_zone as pz  # noqa: E402
from ui_qt import tool_page  # noqa: E402
from ui_qt.hub_window import (  # noqa: E402
    PAGINA_POSZONE, PAGINA_SPLIT2D, PAGINA_SPLIT3D, PAGINA_UPDATE, HubWindow,
)

P_UPDATE, P_POS, P_SPLIT = sys.argv[1:4]
IMAGENS = sys.argv[4] if len(sys.argv) > 4 else None
falhas = []


def confere(nome, ok, extra=""):
    print(f"[{'OK' if ok else 'FALHOU'}] {nome}{' ' + str(extra) if extra != '' else ''}", flush=True)
    if not ok:
        falhas.append(nome)


def espera(condicao, limite=120.0):
    fim = time.perf_counter() + limite
    while time.perf_counter() < fim:
        QCoreApplication.processEvents(QEventLoop.AllEvents, 50)
        if condicao():
            return True
        time.sleep(0.01)
    return False


def foto_tela(janela, nome):
    if IMAGENS:
        os.makedirs(IMAGENS, exist_ok=True)
        janela.grab().save(os.path.join(IMAGENS, nome + ".png"))


def clica(botao):
    QTest.mouseClick(botao, Qt.LeftButton)


app = QApplication(sys.argv)
catia = com.GetActiveObject("CATIA.Application")
catia.DisplayFileAlerts = False


def fechar_tudo():
    catia.DisplayFileAlerts = False
    while catia.Documents.Count:
        catia.Documents.Item(1).Close()


def abre(caminho):
    fechar_tudo()
    return catia.Documents.Open(caminho)


# Os testes apontam para as pastas de teste, sem tocar nas pastas de rede.
at.PASTA_TEMPLATES = os.path.join(P_UPDATE, "templates")
at.run_update_template.__defaults__ = (None, None, at.PASTA_TEMPLATES)
pz.run_pos_zone.__defaults__ = (None, os.path.join(P_POS, "_Callouts.xlsm"), P_POS + "\\")

avisos = []
QMessageBox.warning = staticmethod(lambda _p, t, m: avisos.append(("warn", t, m)))
QMessageBox.information = staticmethod(lambda _p, t, m: avisos.append(("info", t, m)))
respostas = []
QInputDialog.getText = staticmethod(lambda *a, **k: respostas.pop(0))

fechar_tudo()
j = HubWindow()
j.show()
confere("reconhece o CATIA aberto", espera(lambda: "ativo" in j.chip_catia.text(), 10))

# ---------------- Update Template ----------------
p = j.update_page
clica(j.pills["Design"])
confere("Design abre no Update Template", j._pages.currentIndex() == PAGINA_UPDATE)
confere("sem desenho pede para abrir", espera(lambda: p.btn_run.text() == "PROCURAR DE NOVO", 6), p._intro_title.text())
abre(os.path.join(P_UPDATE, "UPD_RICO.CATDrawing"))
confere("percebe o desenho", espera(lambda: p.btn_run.text() == "ATUALIZAR TEMPLATE", 6))
foto_tela(j, "update_1_inicio")
batidas = [0]
relogio = QTimer()
relogio.timeout.connect(lambda: batidas.__setitem__(0, batidas[0] + 1))
relogio.start(50)
t0 = time.perf_counter()
clica(p.btn_run)
confere("termina", espera(lambda: p._stack.currentIndex() == tool_page.PAGINA_RESULTADO, 90))
tempo = time.perf_counter() - t0
relogio.stop()
confere("tela continua respondendo", batidas[0] >= tempo * 20 * 0.5, f"{batidas[0]} batidas em {tempo:.1f} s")
confere("lista as quatro folhas", p.table.rowCount() == 4, [p.table.item(i, 1).text() for i in range(p.table.rowCount())])
confere("mostra o aviso da folha sem formato", "formato não identificado" in p.lbl_warnings.text(), p.lbl_warnings.text())
confere("tela do CATIA religada", bool(catia.RefreshDisplay) and bool(catia.Interactive))
foto_tela(j, "update_2_resultado")

# Formato pedido, cancelado e invalido.
abre(os.path.join(P_UPDATE, "UPD_SEM_FORMATO.CATDrawing"))
espera(lambda: "SEM_FORMATO" in j.chip_doc.text(), 6)
antes = p._report
respostas.append(("", False))
clica(p.btn_again)
confere("cancelar o formato mantém o resultado anterior", espera(lambda: p._stack.currentIndex() == 2, 15) and p._report is antes)
respostas.append(("Z9", True))
clica(p.btn_again)
confere("formato inválido mostra o erro", espera(lambda: p._intro_error.isVisible(), 15), p._intro_error.text()[:90])
foto_tela(j, "update_3_erro")

# ---------------- Position and Zone ----------------
p = j.poszone_page
clica(j.pills["Check"])
clica(j.rail_buttons["Position and Zone"])
confere("trilho leva ao Position and Zone", j._pages.currentIndex() == PAGINA_POSZONE)
abre(os.path.join(P_POS, "POS_RICO.CATDrawing"))
espera(lambda: "POS_RICO" in j.chip_doc.text(), 6)
confere("percebe o desenho", espera(lambda: p.btn_run.text() == "MAPEAR CALLOUTS", 6))
clica(p.btn_run)
confere("termina", espera(lambda: p._stack.currentIndex() == tool_page.PAGINA_RESULTADO, 90), p.lbl_sub.text())
confere("lista os callouts em ordem", p.table.rowCount() == 42 and p.table.item(0, 0).text() == "12", p.table.rowCount())
confere("mostra as contagens", "Quantidades por chave: 2" in p.lbl_counts.text(), p.lbl_counts.text()[:90])
foto_tela(j, "poszone_resultado")
caminho = p._report.workbook_path
confere("a planilha foi criada", os.path.isfile(caminho), caminho)
# Fecha o Excel que a ferramenta deixou aberto para o usuario, e so ele.
try:
    x = com.GetObject(caminho)
    excel = x.Application
    x.Close(False)
    excel.Quit()
except Exception as exc:  # o teste segue; o Excel fica aberto
    print("   nao fechou o Excel:", exc)

# ---------------- Split 2D ----------------
p = j.split2d_page
clica(j.pills["Envio"])
clica(j.rail_buttons["Split 2D"])
confere("trilho leva ao Split 2D", j._pages.currentIndex() == PAGINA_SPLIT2D)
baixados = os.path.join(os.environ["USERPROFILE"], "Downloads", "SPL_DESENHO")
ja_existia = os.path.isdir(baixados)
abre(os.path.join(P_SPLIT, "SPL_DESENHO.CATDrawing"))
espera(lambda: "SPL_DESENHO" in j.chip_doc.text(), 6)
confere("percebe o desenho", espera(lambda: p.btn_run.text() == "DIVIDIR POR FOLHA", 6))
avisos.clear()
clica(p.btn_run)
confere("termina", espera(lambda: p._stack.currentIndex() == tool_page.PAGINA_RESULTADO, 90), p.lbl_sub.text())
confere("lista os quatro arquivos", p.table.rowCount() == 4)
confere("avisa as vistas travadas", any("bloqueadas" in a[2] for a in avisos), avisos)
foto_tela(j, "split2d_resultado")
if not ja_existia:
    shutil.rmtree(baixados, ignore_errors=True)  # so apaga o que este teste criou

# ---------------- Split 3D ----------------
p = j.split3d_page
clica(j.rail_buttons["Split 3D"])
confere("trilho leva ao Split 3D", j._pages.currentIndex() == PAGINA_SPLIT3D)
abre(os.path.join(P_SPLIT, "SPL_PECA.CATPart"))
espera(lambda: "SPL_PECA" in j.chip_doc.text(), 6)
confere("percebe a peça", espera(lambda: p.btn_run.text() == "DIVIDIR A PEÇA", 6))
respostas.append(("2", True))
clica(p.btn_run)
confere("termina", espera(lambda: p._stack.currentIndex() == tool_page.PAGINA_RESULTADO, 90), p.lbl_sub.text())
confere("lista as duas partes", p.table.rowCount() == 2)
foto_tela(j, "split3d_resultado")
abre(os.path.join(P_SPLIT, "SPL_PECA.CATPart"))
espera(lambda: "SPL_PECA" in j.chip_doc.text(), 6)
antes = p._report
respostas.append(("", False))
clica(p.btn_again)
confere("cancelar mantém o resultado anterior", espera(lambda: p._stack.currentIndex() == 2 and p._report is antes, 15))

# Compacto.
clica(j.btn_compact)
espera(lambda: False, 0.4)
confere("modo compacto fica estreito", j.width() == 460, f"{j.width()}x{j.height()}")
foto_tela(j, "split3d_compacto")
clica(j.btn_compact)
espera(lambda: False, 0.4)

fechar_tudo()
j.close()
print("RESULTADO:", "TUDO CERTO" if not falhas else f"{len(falhas)} FALHAS: {falhas}")
sys.exit(1 if falhas else 0)
