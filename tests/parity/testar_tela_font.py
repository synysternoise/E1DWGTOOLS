"""Testa a tela do Font Size Check clicando nela, com o CATIA de verdade.

Uso (com o CATIA aberto e sem desenhos importantes abertos, porque fecha todos):
    python tests/parity/testar_tela_font.py <pasta dos desenhos de teste> [pasta para as imagens]

Os desenhos saem de montar_fixtures_font.catvbs (o teste de paridade os cria).
"""
import os
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "..", "src"))

import win32com.client as com  # noqa: E402
from PySide6.QtCore import QCoreApplication, QEventLoop, Qt, QTimer  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QInputDialog  # noqa: E402

from engine import font_check as fc  # noqa: E402
from engine.catia_bridge import CAMPO, CatiaBridge  # noqa: E402
from ui_qt import font_size_page as pagina  # noqa: E402
from ui_qt.hub_window import HubWindow  # noqa: E402

PASTA = sys.argv[1]
IMAGENS = sys.argv[2] if len(sys.argv) > 2 else None
falhas = []


def confere(nome, ok, extra=""):
    print(f"[{'OK' if ok else 'FALHOU'}] {nome}{' ' + str(extra) if extra != '' else ''}", flush=True)
    if not ok:
        falhas.append(nome)


def espera(condicao, limite=90.0):
    fim = time.perf_counter() + limite
    while time.perf_counter() < fim:
        QCoreApplication.processEvents(QEventLoop.AllEvents, 50)
        if condicao():
            return True
        time.sleep(0.01)
    return False


def foto(janela, nome):
    if IMAGENS:
        os.makedirs(IMAGENS, exist_ok=True)
        janela.grab().save(os.path.join(IMAGENS, nome + ".png"))


def clica(botao):
    QTest.mouseClick(botao, Qt.LeftButton)


app = QApplication(sys.argv)
catia = com.GetActiveObject("CATIA.Application")
catia.DisplayFileAlerts = False
while catia.Documents.Count:
    catia.Documents.Item(1).Close()


def estado():
    return catia.SystemService.ExecuteScript(AQUI, 1, "sonda_tela.catvbs", "Estado", []).split(CAMPO)


def abre(nome):
    while catia.Documents.Count:
        catia.Documents.Item(1).Close()
    return catia.Documents.Open(os.path.join(PASTA, nome))


j = HubWindow()
j.show()
p = j.font_page

# Sem desenho.
confere("reconhece o CATIA aberto", espera(lambda: "ativo" in j.chip_catia.text()))
espera(lambda: p.btn_analyze.text() == "PROCURAR DE NOVO", 5)
confere("sem desenho pede para abrir", p.btn_analyze.text() == "PROCURAR DE NOVO", p._intro_title.text())
foto(j, "1_sem_desenho")

# Analise do desenho com todos os casos.
doc = abre("FONT_RICO.CATDrawing")
confere("percebe o desenho sozinho", espera(lambda: p.btn_analyze.text() == "ANALISAR", 6))
batidas = [0]
relogio = QTimer()
relogio.timeout.connect(lambda: batidas.__setitem__(0, batidas[0] + 1))
relogio.start(50)
t0 = time.perf_counter()
clica(p.btn_analyze)
confere("mostra a barra durante a analise", espera(lambda: p._stack.currentIndex() == 1, 5))
foto(j, "2_analisando")
confere("termina a analise", espera(lambda: p._stack.currentIndex() == 2))
tempo = time.perf_counter() - t0
relogio.stop()
confere("tela continua respondendo durante a analise", batidas[0] >= tempo * 20 * 0.7, f"{batidas[0]} batidas em {tempo:.1f} s")
confere("leva sozinho ao primeiro item", espera(lambda: "Selecionado" in p.lbl_nav_state.text()))
foto(j, "3_resultado")

# A tela precisa mostrar exatamente o que o motor calcula.
b = CatiaBridge()
rep = fc.run_font_inspection(b, lambda *a: "A1", lambda *a: None)
linhas = [[p.table.item(r, c).text() for c in range(1, 6)] for r in range(p.table.rowCount())]
esperado = [[i.sheet_name, i.view_name, i.text, i.size, i.standard] for i in rep.items]
confere("lista igual ao motor", linhas == esperado, f"{len(linhas)} itens")
confere("resumo", f"{rep.total_items} itens" in p.lbl_sub.text() and rep.drawing_no in p.lbl_sub.text(), p.lbl_sub.text())
confere("filtros", p.btn_nok.text() == f"Fora do padrão ({rep.total_nok})" and p.btn_ok.text() == f"Corretos ({rep.total_ok})"
        and p.btn_all.text() == f"Todos ({rep.total_items})", f"{rep.total_nok}/{rep.total_ok}/{rep.total_items}")

# PROXIMO percorre tudo levando a tela e a selecao.
# A analise feita acima pelo teste limpou a selecao; volta ao primeiro item.
p._select(0)
erros = 0
for i, item in enumerate(rep.items):
    if i:
        clica(p.btn_next)
    ok = espera(lambda: p.lbl_pos.text() == f"{i + 1} de {len(rep.items)}" and "Selecionado" in p.lbl_nav_state.text(), 15)
    e = estado()
    if not ok or e[0] != item.sheet_name or e[4] != "1" or e[5] != item.item_name:
        erros += 1
        print("   diferente:", i, item.sheet_name, item.item_name, e)
confere("PRÓXIMO seleciona o item certo no CATIA", erros == 0, f"{len(rep.items)} itens")
clica(p.btn_next)
confere("do último volta para o primeiro", espera(lambda: p.lbl_pos.text() == f"1 de {len(rep.items)}", 5))
espera(lambda: "Selecionado" in p.lbl_nav_state.text(), 15)
clica(p.btn_prev)
confere("ANTERIOR do primeiro vai para o último", espera(lambda: p.lbl_pos.text() == f"{len(rep.items)} de {len(rep.items)}", 5))
espera(lambda: "Selecionado" in p.lbl_nav_state.text(), 15)

# Cliques em sequencia: a tela nao fica para tras nem aceita resposta antiga.
for _ in range(6):
    clica(p.btn_next)
alvo = p._rows[p._current]
ok = espera(lambda: "Selecionado" in p.lbl_nav_state.text(), 15)
confere("cliques seguidos terminam no item certo", ok and estado()[5] == alvo.item_name, alvo.item_name)

# Filtros.
clica(p.btn_ok)
confere("filtro Corretos", p.table.rowCount() == rep.total_ok and espera(lambda: "Selecionado" in p.lbl_nav_state.text(), 15))
confere("item correto também é levado no CATIA", estado()[5] == rep.ok_items[0].item_name)
foto(j, "4_corretos")
clica(p.btn_all)
confere("filtro Todos", p.table.rowCount() == rep.total_items)
espera(lambda: "Selecionado" in p.lbl_nav_state.text(), 15)
clica(p.btn_nok)
espera(lambda: "Selecionado" in p.lbl_nav_state.text(), 15)

# Modo compacto.
clica(j.btn_compact)
espera(lambda: False, 0.4)
confere("modo compacto fica estreito e por cima", j.width() == 460 and bool(j.windowFlags() & Qt.WindowStaysOnTopHint), f"{j.width()}x{j.height()}")
foto(j, "5_compacto")
clica(p.btn_next)
confere("navega no modo compacto", espera(lambda: p.lbl_pos.text() == f"2 de {len(rep.items)}", 5) and espera(lambda: "Selecionado" in p.lbl_nav_state.text(), 15))
clica(j.btn_compact)
espera(lambda: False, 0.4)
confere("volta ao tamanho normal", j.width() == 1180 and not (j.windowFlags() & Qt.WindowStaysOnTopHint))

# Item apagado.
item = p._rows[p._current]
doc.Selection.Delete()
clica(p.btn_prev)
espera(lambda: "Selecionado" in p.lbl_nav_state.text(), 15)
clica(p.btn_next)
confere("item apagado avisa", espera(lambda: p.lbl_detail.text() == pagina.NAO_ENCONTRADO, 15), item.item_name)
foto(j, "6_apagado")

# Parar no meio.
doc = abre("FONT_RICO.CATDrawing")
espera(lambda: "FONT_RICO" in j.chip_doc.text(), 6)
clica(p.btn_again)
espera(lambda: p._stack.currentIndex() == 1, 5)
clica(p.btn_stop)
confere("PARAR interrompe entre folhas", espera(lambda: p._stack.currentIndex() == 2) and p._report.stopped, p.lbl_sub.text())
foto(j, "7_parado")
espera(lambda: "Selecionado" in p.lbl_nav_state.text(), 15)

# Sem formato: pergunta, recusa o invalido e aceita o valido, pela janela real de pedido.
respostas = iter([("Z9", True), ("a2", True)])
avisos = []
pagina.QInputDialog.getText = staticmethod(lambda *a, **k: next(respostas))
pagina.QMessageBox.warning = staticmethod(lambda _p, t, m: avisos.append(m))
abre("FONT_SEMFORMATO.CATDrawing")
espera(lambda: "SEMFORMATO" in j.chip_doc.text(), 6)
antes = p._report
clica(p.btn_again)
ok = espera(lambda: p._report is not antes)
confere("pede o formato e recusa o inválido", ok and avisos == ["Formato 'Z9' não reconhecido."] and "A2" in p.lbl_sub.text(), p.lbl_sub.text())
espera(lambda: "Selecionado" in p.lbl_nav_state.text(), 15)

# Cancelar o pedido nao muda nada.
pagina.QInputDialog.getText = staticmethod(lambda *a, **k: ("", False))
antes = p._report
clica(p.btn_again)
espera(lambda: p._stack.currentIndex() == 1, 3)
ok = espera(lambda: p._stack.currentIndex() == 2, 15)
confere("cancelar mantém o resultado anterior", ok and p._report is antes)

# Tudo dentro do padrao.
abre("FONT_TUDOOK.CATDrawing")
espera(lambda: "TUDOOK" in j.chip_doc.text(), 6)
clica(p.btn_again)
espera(lambda: p._stack.currentIndex() == 1, 3)
ok = espera(lambda: p._stack.currentIndex() == 2 and p.lbl_detail.text() == "Nenhum item fora do padrão", 20)
confere("tudo certo avisa e mostra o padrão", ok and "A1" in p.lbl_where.text(), p.lbl_where.text())
confere("sem itens, navegação desligada", not p.btn_next.isEnabled() and not p.btn_prev.isEnabled())
foto(j, "8_tudo_certo")

while catia.Documents.Count:
    catia.Documents.Item(1).Close()
j.close()
print("RESULTADO:", "TUDO CERTO" if not falhas else f"{len(falhas)} FALHAS: {falhas}")
sys.exit(1 if falhas else 0)
