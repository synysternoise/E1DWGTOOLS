"""Testa a tela do Fix Flags clicando nela, com o CATIA de verdade.

Uso (com o CATIA aberto e sem desenhos importantes abertos, porque fecha todos):
    python tests/parity/testar_tela_flags.py <pasta dos desenhos de teste> [pasta para as imagens]

Os desenhos saem de montar_fixtures_flags.catvbs (o teste de paridade os cria).
"""
import os
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "..", "src"))

import win32com.client as com  # noqa: E402
from PySide6.QtCore import QCoreApplication, QEventLoop, Qt, QTimer  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from engine import fix_flags as ff  # noqa: E402
from engine.catia_bridge import CAMPO, REGISTRO, CatiaBridge  # noqa: E402
from ui_qt import fix_flags_page as pagina  # noqa: E402
from ui_qt.hub_window import PAGINA_FLAGS, PAGINA_GERAL, PAGINA_SEQUENCIA, PAGINA_SPLIT3D, HubWindow  # noqa: E402

PASTA = sys.argv[1]
IMAGENS = sys.argv[2] if len(sys.argv) > 2 else None
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
    catia.SystemService.ExecuteScript(AQUI, 1, "sonda_flags.catvbs", "Fechar", [])


def abre(nome):
    fechar_tudo()
    return catia.Documents.Open(os.path.join(PASTA, nome))


def foto_desenho():
    return catia.SystemService.ExecuteScript(AQUI, 1, "sonda_flags.catvbs", "Foto", []).split(REGISTRO)


def estado():
    return catia.SystemService.ExecuteScript(AQUI, 1, "sonda_tela.catvbs", "Estado", []).split(CAMPO)


fechar_tudo()
j = HubWindow()
j.show()
p = j.flags_page

# Abas.
clica(j.pills["Envio"])
confere("aba Envio mostra o Split 3D", j._pages.currentIndex() == PAGINA_SPLIT3D)
clica(j.pills["Check"])
confere("aba Check mostra a Visão geral", j._pages.currentIndex() == PAGINA_GERAL)
clica(j.pills["Design"])
confere("aba Design mostra a Sequência", j._pages.currentIndex() == PAGINA_SEQUENCIA)
clica(j.rail_buttons["Fix Flags"])
confere("o trilho leva ao Fix Flags", j._pages.currentIndex() == PAGINA_FLAGS)
clica(j.pills["Check"])
clica(j.pills["Design"])
confere("a aba lembra a ferramenta escolhida", j._pages.currentIndex() == PAGINA_FLAGS)

# Sem desenho.
confere("reconhece o CATIA aberto", espera(lambda: "ativo" in j.chip_catia.text(), 10))
confere("sem desenho pede para abrir", espera(lambda: p.btn_run.text() == "PROCURAR DE NOVO", 6), p._intro_title.text())
foto_tela(j, "flags_1_sem_desenho")

# Peca aberta nao libera.
abre("NAO_E_DESENHO.CATPart")
espera(lambda: "NAO_E_DESENHO" in j.chip_doc.text(), 6)
confere("peça aberta não libera", p.btn_run.text() == "PROCURAR DE NOVO", p._intro_title.text())

# Janela real de confirmacao: o padrao e o Nao, e responder Nao nao muda nada.
abre("FLAGS_RICO.CATDrawing")
confere("percebe o desenho sozinho", espera(lambda: p.btn_run.text() == "CORRIGIR FLAGS", 6))
foto_tela(j, "flags_2_inicio")
antes = foto_desenho()
visto = {}


def responde_a_janela(sim):
    caixa = QApplication.activeModalWidget()
    if not isinstance(caixa, QMessageBox):
        QTimer.singleShot(50, lambda: responde_a_janela(sim))
        return
    visto["padrao"] = caixa.defaultButton().text()
    visto["texto"] = caixa.text()
    visto["titulo"] = caixa.windowTitle()
    if IMAGENS:
        caixa.grab().save(os.path.join(IMAGENS, "flags_3_confirmacao.png"))
    if sim:
        alvo = next(b for b in caixa.buttons() if b.text() == "Sim")
        QTest.mouseClick(alvo, Qt.LeftButton)
    else:
        QTest.keyClick(caixa, Qt.Key_Escape)


QTimer.singleShot(50, lambda: responde_a_janela(False))
clica(p.btn_run)
espera(lambda: "padrao" in visto, 15)
confere("botão padrão da confirmação é Não", visto.get("padrao") == "Não", visto.get("padrao"))
confere("confirmação com o texto certo", visto.get("texto") == ff.CONFIRMACAO.replace("\r\n", "\n") and visto.get("titulo") == ff.TITULO_CONFIRMA)
confere("Esc volta para o início", espera(lambda: p._stack.currentIndex() == 0, 15))
confere("responder Não não muda o desenho", foto_desenho() == antes)

# Correcao de verdade.
visto.clear()
# O que importa e o maior tempo com a tela parada, nao quantas batidas couberam.
parada = {"ultima": time.perf_counter(), "maior": 0.0}


def batida():
    agora = time.perf_counter()
    parada["maior"] = max(parada["maior"], agora - parada["ultima"])
    parada["ultima"] = agora


relogio = QTimer()
relogio.timeout.connect(batida)
parada["ultima"] = time.perf_counter()
relogio.start(50)
t0 = time.perf_counter()
QTimer.singleShot(50, lambda: responde_a_janela(True))
clica(p.btn_run)
confere("termina a correção", espera(lambda: p._stack.currentIndex() == 2))
tempo = time.perf_counter() - t0
relogio.stop()
confere("tela continua respondendo", parada["maior"] < 1.0, f'maior parada {parada["maior"]:.2f} s em {tempo:.1f} s')
rep = p._report
print("   ", rep.mensagem.replace("\r\n", " | "))
confere("leva sozinho à primeira flag", espera(lambda: "Selecionada" in p.lbl_nav_state.text(), 20), p.lbl_where.text())
foto_tela(j, "flags_4_resultado")

confere("lista bate com os contadores", rep.corrigidas + rep.ja_corretas + rep.falhas + rep.erros >= rep.flags and len(rep.items) == rep.flags)
confere("filtros", p.btn_fixed.text() == f"Corrigidas ({rep.corrigidas})" and p.btn_ok.text() == f"Já corretas ({rep.ja_corretas})"
        and p.btn_all.text() == f"Todas ({len(rep.items)})", f"{rep.corrigidas}/{rep.ja_corretas}/{len(rep.items)}")
confere("contagens completas na tela", f"{rep.textos} textos" in p.lbl_sub.text() and f"{rep.cadeado} fixas" in p.lbl_counts.text())

depois = foto_desenho()
confere("o desenho mudou", depois != antes)
por_chave = {tuple(x.split(CAMPO)[:3]): x.split(CAMPO) for x in depois}
erradas = [i for i in rep.items if por_chave[(i.sheet_name, i.view_name, i.item_name)][3] != i.after.replace("\r", "<CR>").replace("\n", "<LF>")]
confere("coluna DEPOIS mostra o texto real do desenho", not erradas, erradas[:3])

# Todas as flags, com o PROXIMO.
clica(p.btn_all)
confere("filtro Todas", p.table.rowCount() == len(rep.items))
espera(lambda: "Selecionada" in p.lbl_nav_state.text(), 20)
erros = 0
for i, item in enumerate(rep.items):
    if i:
        clica(p.btn_next)
    ok = espera(lambda: p.lbl_pos.text() == f"{i + 1} de {len(rep.items)}" and "Selecionada" in p.lbl_nav_state.text(), 20)
    e = estado()
    if not ok or e[0] != item.sheet_name or e[4] != "1" or e[5] != item.item_name:
        erros += 1
        print("   diferente:", i, item.sheet_name, item.view_name, item.item_name, p.lbl_detail.text(), e)
confere("PRÓXIMO seleciona a flag certa, em todas as vistas", erros == 0, f"{len(rep.items)} flags")
clica(p.btn_next)
confere("do último volta para o primeiro", espera(lambda: p.lbl_pos.text() == f"1 de {len(rep.items)}", 5))
espera(lambda: "Selecionada" in p.lbl_nav_state.text(), 20)
clica(p.btn_prev)
confere("ANTERIOR do primeiro vai para o último", espera(lambda: p.lbl_pos.text() == f"{len(rep.items)} de {len(rep.items)}", 5))
espera(lambda: "Selecionada" in p.lbl_nav_state.text(), 20)

# Cliques em sequencia.
for _ in range(6):
    clica(p.btn_next)
alvo = p._rows[p._current]
ok = espera(lambda: "Selecionada" in p.lbl_nav_state.text(), 20)
confere("cliques seguidos terminam na flag certa", ok and estado()[5] == alvo.item_name, alvo.item_name)

# Modo compacto.
clica(j.btn_compact)
espera(lambda: False, 0.4)
confere("modo compacto fica estreito e por cima", j.width() == 460 and bool(j.windowFlags() & Qt.WindowStaysOnTopHint), f"{j.width()}x{j.height()}")
foto_tela(j, "flags_5_compacto")
clica(p.btn_next)
confere("navega no modo compacto", espera(lambda: "Selecionada" in p.lbl_nav_state.text(), 20))
clica(j.btn_compact)
espera(lambda: False, 0.4)
confere("volta ao tamanho normal", j.width() == 1180 and not (j.windowFlags() & Qt.WindowStaysOnTopHint))

# Flag apagada.
clica(p.btn_all)
espera(lambda: "Selecionada" in p.lbl_nav_state.text(), 20)
clica(p.btn_next)
espera(lambda: "Selecionada" in p.lbl_nav_state.text(), 20)
item = p._rows[p._current]
catia.ActiveDocument.Selection.Delete()
clica(p.btn_prev)
espera(lambda: "Selecionada" in p.lbl_nav_state.text(), 20)
clica(p.btn_next)
confere("flag apagada avisa", espera(lambda: p.lbl_detail.text() == pagina.NAO_ENCONTRADO, 20), item.item_name)
foto_tela(j, "flags_6_apagada")

# Sem resposta da janela: rodar de novo e parar no meio.
pagina.FixFlagsPage._perguntar = lambda self, m, t: True
abre("FLAGS_RICO.CATDrawing")
espera(lambda: "FLAGS_RICO" in j.chip_doc.text(), 6)
clica(p.btn_again)
espera(lambda: p._stack.currentIndex() == 1, 5)
clica(p.btn_stop)
antes_rep = p._report
confere("PARAR interrompe entre folhas", espera(lambda: p._stack.currentIndex() == 2 and p._report is not antes_rep) and p._report.stopped, p.lbl_sub.text())
foto_tela(j, "flags_7_parado")
espera(lambda: "Selecionada" in p.lbl_nav_state.text(), 20)

# Nao ha flags.
abre("FLAGS_SEM.CATDrawing")
espera(lambda: "FLAGS_SEM" in j.chip_doc.text(), 6)
antes_rep = p._report
clica(p.btn_again)
ok = espera(lambda: p._stack.currentIndex() == 2 and p._report is not antes_rep, 30)
confere("sem flags avisa", ok and p.lbl_detail.text() == "Nenhuma flag reconhecida neste desenho", p.lbl_detail.text())
confere("sem flags, navegação desligada", not p.btn_next.isEnabled() and not p.btn_prev.isEnabled())
foto_tela(j, "flags_8_sem_flags")

# Desenho fechado no meio: mostra o erro e o que ja tinha sido feito.
j.close()
abre("FLAGS_RICO.CATDrawing")
b = CatiaBridge()
try:
    ff.run_fix_flags(b, lambda *a: True, lambda *a: None, progress=lambda i, n: fechar_tudo())
    interrompido = None
except ff.FixInterrompido as exc:
    interrompido = exc
confere("desenho fechado no meio interrompe e guarda o que foi feito",
        interrompido is not None and interrompido.number == 1003 and interrompido.report.textos > 0,
        interrompido and interrompido.mensagem.replace("\r\n", " | "))
j2 = HubWindow()
j2.show()
clica(j2.pills["Design"])
clica(j2.rail_buttons["Fix Flags"])
j2.flags_page.on_failed(interrompido.mensagem, interrompido.report)
espera(lambda: False, 0.5)
confere("tela mostra o erro junto com o que foi feito", j2.flags_page._stack.currentIndex() == 2 and j2.flags_page.lbl_error.isVisible()
        and "interrompido" in j2.flags_page.lbl_error.text())
foto_tela(j2, "flags_9_interrompido")
j2.close()

fechar_tudo()
print("RESULTADO:", "TUDO CERTO" if not falhas else f"{len(falhas)} FALHAS: {falhas}")
sys.exit(1 if falhas else 0)
