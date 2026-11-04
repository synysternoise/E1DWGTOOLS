"""Testa as telas do Update Template, do Position and Zone e dos Splits, clicando nelas.

Uso (com o CATIA aberto e sem desenhos importantes abertos, porque fecha todos):
    python tests/parity/testar_tela_ferramentas.py <update> <poszone> <splits> <imagens> <flags> <font>

As pastas sao as que os testes de paridade criam (paridade_update_*, paridade_poszone_*, ...).
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
    PAGINA_CHECKFLAGS, PAGINA_FONTFIX, PAGINA_GERAL, PAGINA_POSZONE, PAGINA_SPLIT2D, PAGINA_SPLIT3D, PAGINA_UPDATE, HubWindow,
)

P_UPDATE, P_POS, P_SPLIT = sys.argv[1:4]
IMAGENS = sys.argv[4] if len(sys.argv) > 4 else None
P_FLAGS, P_FONT = sys.argv[5], sys.argv[6]
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
at.run_update_template.__defaults__ = (None, None, at.PASTA_TEMPLATES, None)
at.preview_update.__defaults__ = (at.PASTA_TEMPLATES,)
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
clica(j.rail_buttons["Update Template"])
confere("trilho leva ao Update Template", j._pages.currentIndex() == PAGINA_UPDATE)
confere("sem desenho pede para abrir", espera(lambda: p.btn_run.text() == "PROCURAR DE NOVO", 6), p._intro_title.text())
abre(os.path.join(P_UPDATE, "UPD_RICO.CATDrawing"))
confere("percebe o desenho", espera(lambda: p.btn_run.text() == "EXECUTAR UPDATE TEMPLATE", 6))
confere("mostra a prévia das folhas", espera(lambda: p.tabela_folhas.rowCount() == 4, 15), p.linha_formato._texto.text())
foto_tela(j, "update_1_inicio")
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
clica(p.btn_run)
confere("termina", espera(lambda: p._stack.currentIndex() == tool_page.PAGINA_RESULTADO, 90))
tempo = time.perf_counter() - t0
relogio.stop()
confere("tela continua respondendo", parada["maior"] < 1.0, f'maior parada {parada["maior"]:.2f} s em {tempo:.1f} s')
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
confere("abre nas pendências", p.tabela_pendencias.rowCount() == 2, p.btn_pendencias.text())
confere("leva até a pendência", espera(lambda: "Selecionado" in p.lbl_nav_state.text(), 20), p.lbl_where.text())
clica(p.btn_todos)
confere("lista os callouts em ordem", p.table.rowCount() == 42 and p.table.item(0, 0).text() == "12", p.table.rowCount())
confere("mostra as contagens", p.resumo.valores["Quantidades por chave"].text() == "2")
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
confere("percebe a peça", espera(lambda: p.btn_run.text().startswith("PARTIR EM"), 6))
confere("mostra os Bodies de cada parte", espera(lambda: p.tabela_previa.rowCount() == 2, 15))
foto_tela(j, "split3d_inicio")
p.spin.setValue(3)
confere("o plano acompanha o número de partes", p.tabela_previa.rowCount() == 3 and p.btn_run.text() == "PARTIR EM 3 ARQUIVOS")
p.spin.setValue(2)
clica(p.btn_run)
confere("termina", espera(lambda: p._stack.currentIndex() == tool_page.PAGINA_RESULTADO, 90), p.lbl_sub.text())
confere("lista as duas partes", p.table.rowCount() == 2)
foto_tela(j, "split3d_resultado")

# Compacto.
clica(j.btn_compact)
espera(lambda: False, 0.4)
confere("modo compacto fica estreito", j.width() == 460, f"{j.width()}x{j.height()}")
foto_tela(j, "split3d_compacto")
clica(j.btn_compact)
espera(lambda: False, 0.4)

# ---------------- Check de Flags ----------------
p = j.flagcheck_page
clica(j.pills["Check"])
clica(j.rail_buttons["Check de Flags"])
confere("trilho leva ao Check de Flags", j._pages.currentIndex() == PAGINA_CHECKFLAGS)
abre(os.path.join(P_FLAGS, "FLAGS_RICO.CATDrawing"))
espera(lambda: "FLAGS_RICO" in j.chip_doc.text(), 6)
confere("percebe o desenho", espera(lambda: p.btn_run.text() == "CONFERIR AS FLAGS", 6))
clica(p.btn_run)
confere("termina", espera(lambda: p._stack.currentIndex() == tool_page.PAGINA_RESULTADO, 60), p.lbl_sub.text())
r = p._report
confere("abre no que precisa corrigir", p.table.rowCount() == r.erradas and r.erradas > 0, p.btn_erradas.text())
confere("leva até a flag no CATIA", espera(lambda: "Selecionada" in p.lbl_nav_state.text(), 20), p.lbl_detail.text())
foto_tela(j, "flagcheck_resultado")
clica(p.btn_next)
confere("PRÓXIMO anda na lista", espera(lambda: p.lbl_pos.text().startswith("2 de") and "Selecionada" in p.lbl_nav_state.text(), 20), p.lbl_pos.text())
clica(p.btn_corrigir)
confere("Corrigir leva ao Fix Flags", j.flags_page.isVisible())

# ---------------- Font Size Fix ----------------
p = j.fontfix_page
clica(j.rail_buttons["Font Size Fix"])
confere("trilho leva ao Font Size Fix", j._pages.currentIndex() == PAGINA_FONTFIX)
abre(os.path.join(P_FONT, "FONT_RICO.CATDrawing"))
espera(lambda: "FONT_RICO" in j.chip_doc.text(), 6)
confere("percebe o desenho", espera(lambda: p.btn_run.text() == "ANALISAR AS FONTES", 6))
clica(p.btn_run)
confere("termina", espera(lambda: p._stack.currentIndex() == tool_page.PAGINA_RESULTADO, 60), p.lbl_sub.text())
total = len(p._rows)
confere("lista o que está fora do padrão", total > 5 and p.table.rowCount() == total, total)
confere("leva até o item no CATIA", espera(lambda: "Selecionado" in p.lbl_nav_state.text(), 20), p.lbl_item.text())
foto_tela(j, "fontfix_resultado")
primeiro = p._rows[0]
clica(p.btn_fix)
confere("CORRIGIR ESTE muda a situação", espera(lambda: p._situacao[primeiro.order] == "Corrigido", 20), primeiro.size)
confere("e anda para o próximo", espera(lambda: p.lbl_pos.text().startswith("2 de"), 5), p.lbl_pos.text())
espera(lambda: "Selecionado" in p.lbl_nav_state.text(), 20)
segundo = p._rows[1]
clica(p.btn_alvo[1] if segundo.padroes[1] != p._alvo[segundo.order] else p.btn_alvo[0])
escolhido = p._alvo[segundo.order]
clica(p.btn_keep)
confere("DEIXAR COMO ESTÁ não muda o item", p._situacao[segundo.order] == "Como estava" and segundo.size == p.table.item(1, 3).text())
espera(lambda: "Selecionado" in p.lbl_nav_state.text(), 20)
pendentes = sum(1 for v in p._situacao.values() if v == "Pendente")
confere("o botão mostra os pendentes", p.btn_all.text() == f"CORRIGIR TODOS OS PENDENTES ({pendentes})", p.btn_all.text())
clica(p.btn_all)
confere("corrige os pendentes", espera(lambda: "Pendente" not in p._situacao.values(), 60), p.resumo.valores["Corrigidos"].text())
foto_tela(j, "fontfix_corrigido")
confere("o que ficou como estava continua fora do padrão", p._situacao[segundo.order] == "Como estava")
clica(p.btn_again)
espera(lambda: p._stack.currentIndex() == 1, 5)
confere("nova análise só aponta o que ficou", espera(lambda: p._stack.currentIndex() == 2 and len(p._rows) == 1, 60), len(p._rows))

# ---------------- Sequencia e Visao geral ----------------
s = j.seq_page
clica(j.pills["Design"])
clica(j.rail_buttons["Sequência de aplicação"])
fechar_tudo()
abre(os.path.join(P_UPDATE, "UPD_RICO.CATDrawing"))
espera(lambda: "UPD_RICO" in j.chip_doc.text(), 6)
confere("a sequência libera com o desenho", espera(lambda: s.btn_executar.isEnabled(), 6), s.btn_executar.text())
foto_tela(j, "seq_1_escolha")
clica(s.presets.botoes[1])
confere("Sem Update tira só o Update", s._marcadas() == ["flags", "fontfix"] and s.btn_executar.text() == "EXECUTAR 2 ETAPAS")
clica(s.presets.botoes[0])
confere("Completa marca as três", s._marcadas() == ["update", "flags", "fontfix"])
from ui_qt import fix_flags_page as ffp  # noqa: E402

ffp.FixFlagsPage._perguntar = lambda self, m, t: True
clica(s.btn_executar)
confere("mostra a execução", espera(lambda: s._stack.currentIndex() == 1, 10))
foto_tela(j, "seq_2_rodando")
confere("a sequência termina", espera(lambda: s.lbl_run_titulo.text() == "Sequência concluída", 120), s.lbl_log.text()[-90:])
foto_tela(j, "seq_3_fim")
confere("as etapas guardam o resultado", j.update_page._report is not None and j.flags_page._report is not None and j.fontfix_page._report is not None)
clica(s.btn_fontes)
confere("Revisar leva ao Font Size Fix", j._pages.currentIndex() == PAGINA_FONTFIX)
foto_tela(j, "fontfix_da_sequencia")
clica(j.pills["Check"])
clica(j.rail_buttons["Visão geral"])
g = j.geral_page
abre(os.path.join(P_POS, "POS_RICO.CATDrawing"))
espera(lambda: "POS_RICO" in j.chip_doc.text(), 6)
espera(lambda: g.btn_rodar.isEnabled(), 6)
confere("Visão geral roda os três checks", g.btn_rodar.text() == "RODAR 3 CHECKS", g.btn_rodar.text())
respostas.append(("A1", True))  # este desenho nao tem formato, e o Font Check pergunta
clica(g.btn_rodar)
confere("o resultado aparece", espera(lambda: g._font is not None and g._pos is not None and g._flags is not None, 90), f"{g.card_revisar.numero.text()} para revisar")
espera(lambda: False, 0.5)
foto_tela(j, "check_geral")
confere("o contador da aba soma as pendências", j.contagem_check.text() == str(g.pendencias_font() + g.pendencias_pos() + g.pendencias_flags()), j.contagem_check.text())
try:
    x = com.GetObject(j.poszone_page._report.workbook_path)
    excel = x.Application
    x.Close(False)
    excel.Quit()
except Exception as exc:  # o teste segue; o Excel fica aberto
    print("   nao fechou o Excel:", exc)

fechar_tudo()
j.close()
print("RESULTADO:", "TUDO CERTO" if not falhas else f"{len(falhas)} FALHAS: {falhas}")
sys.exit(1 if falhas else 0)
