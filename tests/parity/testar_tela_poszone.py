"""Testa as telas do Position and Zone clicando nelas: percorrer, Part List, mover, OK manual.

Uso (com o CATIA aberto e sem desenhos importantes abertos, porque fecha todos):
    python tests/parity/testar_tela_poszone.py <pasta paridade_poszone_*> [pasta das imagens]
"""
import os
import subprocess
import sys
import tempfile
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "..", "src"))

os.environ["E1DWGTOOLS_OK"] = os.path.join(tempfile.mkdtemp(prefix="ok_manual_"), "ok.json")

import win32com.client as com  # noqa: E402
from PySide6.QtCore import QCoreApplication, QEventLoop, Qt, QTimer  # noqa: E402
from PySide6.QtGui import QColor  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox  # noqa: E402

from engine import part_list as pl  # noqa: E402
from engine import pos_zone as pz  # noqa: E402
from engine.catia_bridge import CatiaBridge  # noqa: E402
from ui_qt import poszone_page as pp  # noqa: E402
from ui_qt import theme as T  # noqa: E402
from ui_qt import tool_page  # noqa: E402
from ui_qt.hub_window import HubWindow  # noqa: E402

P_POS = sys.argv[1]
IMAGENS = sys.argv[2] if len(sys.argv) > 2 else None
falhas = []


def confere(nome, ok, extra=""):
    print(f"[{'OK' if ok else 'FALHOU'}] {nome}{' ' + str(extra) if extra != '' else ''}", flush=True)
    if not ok:
        falhas.append(nome)


def espera(condicao, limite=60.0):
    fim = time.perf_counter() + limite
    while time.perf_counter() < fim:
        QCoreApplication.processEvents(QEventLoop.AllEvents, 50)
        if condicao():
            return True
        time.sleep(0.01)
    return False


def foto(nome):
    if IMAGENS:
        os.makedirs(IMAGENS, exist_ok=True)
        espera(lambda: False, 0.3)
        j.grab().save(os.path.join(IMAGENS, nome + ".png"))


def clica(b):
    QTest.mouseClick(b, Qt.LeftButton)


app = QApplication(sys.argv)
catia = com.GetActiveObject("CATIA.Application")
catia.DisplayFileAlerts = False
ponte = CatiaBridge()
pz.exportar_planilha.__defaults__ = (os.path.join(P_POS, "_Callouts.xlsm"), P_POS + "\\")

avisos = []
QMessageBox.warning = staticmethod(lambda _p, t, m: avisos.append((t, m)))


def fechar_tudo():
    catia.DisplayFileAlerts = False
    while catia.Windows.Count:
        catia.Windows.Item(1).Parent.Close()


def contar_excel():
    return subprocess.run(["tasklist", "/FI", "IMAGENAME eq EXCEL.EXE", "/FO", "CSV", "/NH"], capture_output=True, text=True).stdout.upper().count("EXCEL.EXE")


def script(funcao, *args):
    return catia.SystemService.ExecuteScript(AQUI, 1, "sonda_pos.catvbs", funcao, list(args))


fechar_tudo()
doc = catia.Documents.Open(os.path.join(P_POS, "POS_RICO.CATDrawing"))
cheio = doc.FullName
confere("monta o balão com flag e leader", script("Criar", cheio, "BALOES") == "OK")
ponta_antes = script("Leader", cheio, "BALOES", "58")

j = HubWindow()
j.show()
espera(lambda: "POS_RICO" in j.chip_doc.text(), 10)
p = j.poszonefix_page
c = j.poszone_page
clica(j.pills["Design"])
clica(j.rail_buttons["Pos and Zone Fix"])
confere("Design tem a tela nova", p.isVisible())
confere("percebe o desenho", espera(lambda: p.btn_run.text() == "MAPEAR CALLOUTS", 6))
foto("pos_1_inicio")
clica(p.btn_run)
confere("termina sem abrir planilha", espera(lambda: p._stack.currentIndex() == tool_page.PAGINA_RESULTADO, 90) and p._report.workbook_path == "", p.lbl_sub.text())
r = p._report
confere("o Check recebe a mesma leitura", c._report is r and c._stack.currentIndex() == tool_page.PAGINA_RESULTADO)

# ---------------- Sem Part List ----------------
confere("abre no que precisa revisar: os não contados", p.btn_revisar.isChecked() and p.table.rowCount() == len(r.pendencias), p.btn_revisar.text())
confere("leva até o não contado", espera(lambda: "Selecionado" in p.lbl_nav_state.text(), 20), p.lbl_where.text())
clica(p.btn_todos)
n_linhas = len(r.callouts) + len(r.pendencias)
confere("lista tudo, sem linha inventada", p.table.rowCount() == n_linhas, p.table.rowCount())
confere("mesmas informações da planilha", [p.table.horizontalHeaderItem(i).text() for i in range(5)] == ["", "POS", "ZONA", "QTD", "VISTA ORIGEM"])
confere("sem Part List, as colunas dele ficam escondidas", p.table.isColumnHidden(pp.COL_PL_ZONA) and p.table.isColumnHidden(pp.COL_PN))
primeira = r.callouts and sorted(r.callouts, key=lambda x: float(x.number))[0]
confere("em ordem e com os dados do callout", p.table.item(0, pp.COL_POS).text() == primeira.number and p.table.item(0, pp.COL_ZONA).text() == primeira.zone and p.table.item(0, pp.COL_QTD).text() == str(primeira.qty) and p.table.item(0, pp.COL_VISTA).text() == f"{primeira.sheet} - {primeira.view}", p.table.item(0, pp.COL_ZONA).text())
foto("pos_2_sem_part_list")

# ---------------- A seta percorre cada balao ----------------
p.table.setCurrentCell(0, pp.COL_POS)
li = p._rows[0]
total = len(li.occs)
confere("a posição 12 tem vários balões", total >= 3, total)
for n in range(total):
    espera(lambda: f"{n + 1} de {total}" in p.lbl_where.text() and "Selecionado" in p.lbl_nav_state.text(), 20)
    o = li.occs[n]
    sel = script("Selecionado", cheio)
    confere(f"balão {n + 1} de {total} selecionado no CATIA", sel.split("|")[-1] == o.item_name and p.lbl_ocorrencia.text() == f"{n + 1} de {total}", f"{o.sheet}/{o.view} {sel}")
    if n < total - 1:
        clica(p.btn_next)
clica(p.btn_next)
confere("depois do último balão vai para a próxima posição", espera(lambda: p.lbl_pos.text().startswith("2 de") and "Selecionado" in p.lbl_nav_state.text(), 20), p.lbl_detail.text())
clica(p.btn_prev)
confere("voltar cai no último balão da anterior", espera(lambda: p.lbl_pos.text().startswith("1 de") and f"{total} de {total}" in p.lbl_where.text(), 20), p.lbl_where.text())
espera(lambda: "Selecionado" in p.lbl_nav_state.text(), 20)

# ---------------- Part List ----------------
callouts = {x.number: x for x in r.callouts}
leitor = com.DispatchEx("Excel.Application")
leitor.Visible = False
leitor.DisplayAlerts = False
wb = leitor.Workbooks.Add()
ws = wb.Worksheets(1)
ws.Name = "COMPONENT"
zona_58 = callouts["58"].zone
zonas_folha = pz.zonas_da_folha(r, callouts["58"].sheet)
alvo = next(z for z in zonas_folha if z[1:] != zona_58[1:] and z[0] != zona_58[0])
linhas = []
for x in r.callouts:
    zona = x.zone.split(";")[0].strip() or "A001"
    qtd = x.qty
    if x.number == "58":
        zona = alvo
    if x.number in ("21", "22"):
        qtd += 1
    linhas.append((f"PN{x.number}", x.number, zona, qtd))
linhas.append(("PN-EXTRA", "9999", "F008", 3))
for i, (pn, pos, zona, qtd) in enumerate(linhas, 5):
    ws.Cells(i, pl.COL_PN).Value = pn
    ws.Cells(i, pl.COL_POSICAO).NumberFormat = "@"
    ws.Cells(i, pl.COL_POSICAO).Value = pos
    ws.Cells(i, pl.COL_ZONA).Value = zona
    ws.Cells(i, pl.COL_QUANTIDADE).Value = qtd
sap = os.path.join(P_POS, "sap_teste.xlsx")
if os.path.exists(sap):
    os.remove(sap)
wb.SaveAs(sap, FileFormat=51)
wb.Close(False)
leitor.Quit()

QFileDialog.getOpenFileNames = staticmethod(lambda *a, **k: ([sap.replace("\\", "/")], ""))
excels_antes = contar_excel()
clica(p.btn_carregar)
confere("mostra que está lendo", "Lendo" in p.linha_pl._texto.text() and not p.btn_carregar.isEnabled())
confere("carrega o Part List nas duas telas", espera(lambda: p._part is not None and c._part is not None, 60), p.linha_pl._texto.text())
confere("o Excel da leitura fecha", espera(lambda: contar_excel() == excels_antes, 20), f"{excels_antes} -> {contar_excel()}")
parte = p._part
comp = pl.comparar(r.callouts, parte.registros)
esperado = sum(1 for x in comp.desenho.values() if not (x.posicao and x.zona and x.quantidade)) + 1 + len(r.pendencias)
confere("com Part List, as colunas aparecem", not p.table.isColumnHidden(pp.COL_PL_ZONA) and not p.table.isColumnHidden(pp.COL_PN))
confere("conta o que revisar igual à comparação", p.card_revisar.numero.text() == str(esperado), f"{p.card_revisar.numero.text()} de {esperado}")
foto("pos_3_part_list")


def linha_de(pagina, numero):
    clica(pagina.btn_todos)
    return next(i for i, li in enumerate(pagina._rows) if li.numero == numero and li.tipo == pp.CALLOUT)


i = linha_de(p, "22")
confere("quantidade errada fica vermelha na tabela", p.table.item(i, pp.COL_QTD).foreground().color() == QColor(T.RED) and p.table.item(i, pp.COL_ZONA).foreground().color() == QColor(T.GREEN))
i = linha_de(p, "21")
confere("duas zonas no desenho: fica verde se uma bater", ";" in callouts["21"].zone and p.table.item(i, pp.COL_ZONA).foreground().color() == QColor(T.GREEN) and p.table.item(i, pp.COL_PL_ZONA).foreground().color() == QColor(T.GREEN), callouts["21"].zone)
p.table.setCurrentCell(i, pp.COL_POS)
confere("com a zona batendo, não sugere mover os outros balões", not p.btn_mover.isEnabled(), p.btn_mover.text())
i = next(n for n, li in enumerate(p._rows) if li.tipo == pp.SO_PART_LIST)
p.table.setCurrentCell(i, pp.COL_POS)
confere("só no Part List: nada para percorrer", p.lbl_where.text() == "Sem balão no desenho" and p.lbl_nav_state.text() == "" and p.table.item(i, pp.COL_PN).text() == "PN-EXTRA", p.lbl_detail.text())


# ---------------- Mover ----------------
def leitura():
    folha = pz.parse_sheet(ponte.call(pz.SCRIPT, "LerFolha", cheio, 1))
    return {(v.name, t.index): (t.x, t.y, t.text) for v in folha.views for t in v.texts}


antes = leitura()
i = linha_de(p, "58")
p.table.setCurrentCell(i, pp.COL_POS)
espera(lambda: "Selecionado" in p.lbl_nav_state.text(), 20)
confere("sugere a zona do Part List", p.combo_zona.currentText() == alvo and p.btn_mover.text() == f"MOVER PARA {alvo}", p.btn_mover.text())
confere("avisa o que anda junto", "NI1008" in p.lbl_junto.text() and "42" in p.lbl_junto.text(), p.lbl_junto.text())
foto("pos_4_mover")
clica(p.btn_mover)
confere("o movimento termina", espera(lambda: not p._movendo, 20))
occ58 = next(o for o in r.occs if o.number == "58")
confere("a zona mudou na tela", occ58.zone == alvo and next(x for x in r.callouts if x.number == "58").zone == alvo, occ58.zone)
depois = leitura()
mudaram = {k for k in antes if antes[k][:2] != depois[k][:2]}
textos_movidos = {antes[k][2] for k in mudaram}
confere("só o balão, a flag e o número mudaram de lugar", textos_movidos == {"58", "NI1008", "42"}, sorted(textos_movidos))
deltas = {(round(depois[k][0] - antes[k][0], 4), round(depois[k][1] - antes[k][1], 4)) for k in mudaram}
confere("os três andaram igual", len(deltas) == 1, deltas)
confere("nenhum texto mudou de conteúdo", all(antes[k][2] == depois[k][2] for k in antes) and len(antes) == len(depois))
ponta_depois = script("Leader", cheio, "BALOES", "58")
confere("a ponta do leader continua onde estava", ponta_depois == ponta_antes and not ponta_antes.startswith("ERRO"), f"{ponta_antes} -> {ponta_depois}")
rel2 = pz.analisar_desenho(ponte, lambda *a: None)
novo = next(o for o in rel2.occs if o.number == "58")
confere("lendo o desenho de novo dá a mesma zona", novo.zone == alvo, novo.zone)
confere("nada mais mudou na contagem", [(x.number, x.qty) for x in rel2.callouts] == [(x.number, x.qty) for x in r.callouts])
foto("pos_5_movido")

clica(p.btn_desfazer)
espera(lambda: not p._movendo, 20)
volta = leitura()
confere("DESFAZER devolve cada texto ao lugar", all(abs(antes[k][0] - volta[k][0]) < 1e-6 and abs(antes[k][1] - volta[k][1]) < 1e-6 for k in antes))
confere("e a zona volta", occ58.zone == zona_58, occ58.zone)

# Vista girada e com escala.
i = linha_de(p, "51")
p.table.setCurrentCell(i, pp.COL_POS)
espera(lambda: "Selecionado" in p.lbl_nav_state.text(), 20)
occ51 = next(o for o in r.occs if o.number == "51")
destino = next(z for z in zonas_folha if z != occ51.zone)
p.combo_zona.setCurrentText(destino)
clica(p.btn_mover)
espera(lambda: not p._movendo, 20)
rel2 = pz.analisar_desenho(ponte, lambda *a: None)
confere("vista girada: a zona lida é a pedida", next(o for o in rel2.occs if o.number == "51").zone == destino, destino)
clica(p.btn_desfazer)
espera(lambda: not p._movendo, 20)

# Vista travada: nao move e avisa.
i = linha_de(p, "21")
p.table.setCurrentCell(i, pp.COL_POS)
li = p._rows[i]
n_trav = next(n for n, o in enumerate(li.occs) if o.view == "REPETIDOS")
p._ir(i, n_trav)
espera(lambda: "Selecionado" in p.lbl_nav_state.text(), 20)
o = li.occs[n_trav]
p.combo_zona.setCurrentText(next(z for z in zonas_folha if z != o.zone))
antes = leitura()
avisos.clear()
clica(p.btn_mover)
espera(lambda: not p._movendo, 20)
confere("vista travada não move e avisa", leitura() == antes and any("travada" in a[1] for a in avisos), avisos[:1])

# Sublinhado nao tem zona.
i = next((n for n, li in enumerate(p._rows) if li.occs and li.occs[0].source != pz.SOURCE_BALLOON), None)
if i is not None:
    p.table.setCurrentCell(i, pp.COL_POS)
    confere("sublinhado não oferece mover", not p.btn_mover.isEnabled() and "sublinhado" in p.lbl_junto.text(), p.lbl_junto.text())

# ---------------- OK manual ----------------
i = linha_de(p, "21")
p.table.setCurrentCell(i, pp.COL_POS)
espera(lambda: "Selecionado" in p.lbl_nav_state.text(), 20)
antes_rev = int(p.card_revisar.numero.text())
clica(p.btn_ok)
li = next(x for x in p._todas if x.numero == "21" and x.tipo == pp.CALLOUT)
confere("marca OK manual", li.estado == pp.MANUAL and int(p.card_revisar.numero.text()) == antes_rev - 1 and p.card_manual.numero.text() == "1", li.manual)
confere("vai junto para o Check", next(x for x in c._todas if x.numero == "21" and x.tipo == pp.CALLOUT).estado == pp.MANUAL)
confere("diz quem e onde marcou", "OK manual" in p.lbl_lugar.text() and "Design" in p.lbl_lugar.text(), p.lbl_lugar.text())
foto("pos_6_ok_manual")
confere("o botão vira tirar", p.btn_ok.text() == "TIRAR O OK")
clica(j.pills["Check"])
clica(j.rail_buttons["Position and Zone"])
confere("o Check abre com o mesmo resultado", c.isVisible() and c.lbl_sub.text() == p.lbl_sub.text())
confere("o Check não move balão", not hasattr(c, "btn_mover"))
clica(c.btn_pendencias)
badge_antes = j.rail_badges["Position and Zone"].text()
clica(c.btn_ok)
espera(lambda: False, 0.3)
confere("o Check também marca OK, até no não contado", c.card_manual.numero.text() == "2" and j.rail_badges["Position and Zone"].text() == str(int(badge_antes) - 1), f"{badge_antes} -> {j.rail_badges['Position and Zone'].text()}")
foto("pos_7_check")
clica(c.btn_again)
espera(lambda: c._stack.currentIndex() == 1, 5)
confere("mapear de novo mantém os OKs e o Part List", espera(lambda: c._stack.currentIndex() == 2, 90) and c.card_manual.numero.text() == "2" and c._part is not None, c.card_manual.numero.text())
espera(lambda: False, 0.5)
clica(c.btn_todos)
li = next(i for i, x in enumerate(c._rows) if x.numero == "21" and x.tipo == pp.CALLOUT)
c.table.setCurrentCell(li, pp.COL_POS)
clica(c.btn_ok)
confere("tirar o OK volta a pedir revisão", next(x for x in c._todas if x.numero == "21" and x.tipo == pp.CALLOUT).estado == pp.ERRO)

# ---------------- Excel, para quem quiser ----------------
r2 = c._report
clica(c.btn_excel)
confere("ABRIR NO EXCEL cria a cópia", espera(lambda: bool(r2.workbook_path) and os.path.isfile(r2.workbook_path), 60), r2.workbook_path)
espera(lambda: j._busy is False, 30)
try:
    x = com.GetObject(r2.workbook_path)
    ws = x.Worksheets("Dados_Callouts")
    confere("a planilha tem a tabela", ws.Range("A4").Value == float(sorted(r2.callouts, key=lambda k: float(k.number))[0].number), ws.Range("A4").Value)
    excel = x.Application
    x.Close(False)
    excel.Quit()
except Exception as exc:  # noqa: BLE001
    confere("a planilha abre", False, exc)

# ---------------- Clean SAP e compacto ----------------


def responder_sim():
    caixa = QApplication.activeModalWidget()
    if caixa is not None:
        next(b for b in caixa.buttons() if b.text() == "Sim").click()


QTimer.singleShot(300, responder_sim)
clica(c.btn_limpar)
confere("LIMPAR esquece o Part List e mantém o desenho", espera(lambda: c._part is None and p._part is None, 5) and c.card_ok.numero.text() == "0" and len(c._report.callouts) > 0)
confere("sem Part List não sobra linha só do SAP", not any(x.tipo == pp.SO_PART_LIST for x in c._todas))

clica(j.pills["Design"])
clica(j.rail_buttons["Pos and Zone Fix"])
espera(lambda: False, 0.3)
clica(j.btn_compact)
espera(lambda: False, 0.5)
confere("no compacto dá para percorrer e mover", j.width() == 460 and p.btn_next.isVisible() and p.table.isVisible(), f"{j.width()}x{j.height()}")
foto("pos_8_compacto")
clica(j.btn_compact)
espera(lambda: False, 0.5)
confere("sai do compacto com o painel ao lado", p._lateral.width() == 300, p._lateral.width())
confere("sai do compacto com as colunas no tamanho certo", p.table.columnWidth(pp.COL_ZONA) == 84 and p.table.horizontalScrollBar().value() == 0 and p.table.columnWidth(pp.COL_VISTA) > 84, p.table.columnWidth(pp.COL_ZONA))

# ---------------- Fechar o HUB devolve o CATIA limpo ----------------
p.table.setCurrentCell(0, pp.COL_POS)
espera(lambda: "Selecionado" in p.lbl_nav_state.text(), 20)
confere("antes de fechar há seleção", catia.ActiveDocument.Selection.Count >= 1, catia.ActiveDocument.Selection.Count)
t0 = time.perf_counter()
j.close()
confere("o HUB fecha sem esperar", time.perf_counter() - t0 < 2, f"{time.perf_counter() - t0:.2f} s")
confere("fechar tira a seleção", catia.ActiveDocument.Selection.Count == 0, catia.ActiveDocument.Selection.Count)
confere("fechar deixa o CATIA ligado", bool(catia.Interactive) and bool(catia.DisplayFileAlerts) and bool(catia.RefreshDisplay))
fechar_tudo()
print("RESULTADO:", "TUDO CERTO" if not falhas else f"{len(falhas)} FALHAS: {falhas}", flush=True)
sys.stdout.flush()
os._exit(1 if falhas else 0)
