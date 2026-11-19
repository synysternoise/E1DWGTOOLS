"""Testa o Check de Template no CATIA de verdade, com a legenda das fotos do desenho real, e clica na tela.

Uso (com o CATIA aberto e sem desenhos importantes abertos, porque fecha todos):
    python tests/parity/testar_check_template.py [pasta para as fotos da tela]
"""
import os
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "..", "src"))

from PySide6.QtCore import QCoreApplication, QEventLoop, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from engine import template_check as tc  # noqa: E402
from engine.catia_bridge import CatiaBridge  # noqa: E402
from ui_qt import tool_page  # noqa: E402
from ui_qt.hub_window import PAGINA_CHECKTEMPLATE, HubWindow  # noqa: E402

IMAGENS = sys.argv[1] if len(sys.argv) > 1 else None
falhas = []


def confere(nome, ok, extra=""):
    print(f"[{'OK' if ok else 'FALHOU'}] {nome}{' ' + str(extra) if extra != '' else ''}", flush=True)
    if not ok:
        falhas.append(nome)


b = CatiaBridge()
app = b.app


def fechar_tudo():
    app.DisplayFileAlerts = False
    while app.Documents.Count:
        app.Documents.Item(1).Close()


def legenda(fundo, escala, numero, formato, prefixo=None):
    """Mesmo arranjo da legenda real: rotulo em cima, valor na mesma celula."""
    for texto, x, y in (
        ("DRAWING TITLE", 1000, 90), ("LAVATORY INSTL, FWD", 1000, 75), ("DRAWING NUMBER", 1040, 55), ("171-54397-801", 1040, 45),
        ("SCALE", 975, 55), ("SHEET / OF", 1110, 55), ("REV", 915, 25), ("1", 1020, 8), ("2", 700, 8), (formato, 1175, 8),
    ):
        fundo.Texts.Add(texto, x, y)
    if escala is not None:
        fundo.Texts.Add(escala, 975, 45)
    if prefixo is not None:
        fundo.Texts.Add(prefixo, 1100, 45)
    if numero is not None:
        fundo.Texts.Add(numero, 1112, 45)


def folha(doc, i, escala, numero, formato="A0", papel=2, vistas=(), prefixo=None, na_principal=None):
    folhas = doc.Sheets
    sh = folhas.Item(1) if i == 1 else folhas.Add(f"Sheet.{i}")
    sh.PaperSize = papel
    sh.Activate()
    legenda(sh.Views.Item(2), escala, numero, formato, prefixo)
    if na_principal is not None:
        sh.Views.Item(1).Texts.Add(na_principal, 1112, 45)
    for nome, valor in vistas:
        v = sh.Views.Add(nome)
        v.Scale = valor
    sh.Views.Item(1).Activate()
    return sh


def novo(parametro=None):
    doc = app.Documents.Add("Drawing")
    if parametro is not None:
        doc.Parameters.CreateInteger("No_of_Sheets", parametro)
    return doc


def foto(doc):
    """Tudo o que o Check le. Tem que ficar igual depois de rodar."""
    linhas = []
    for i in range(1, doc.Sheets.Count + 1):
        sh = doc.Sheets.Item(i)
        linhas.append((sh.Name, sh.PaperSize, sh.GetPaperWidth(), sh.GetPaperHeight()))
        for k in range(1, sh.Views.Count + 1):
            v = sh.Views.Item(k)
            linhas.append((v.Name, v.Scale, v.x, v.y, v.Texts.Count))
            for n in range(1, v.Texts.Count + 1):
                t = v.Texts.Item(n)
                linhas.append((t.Name, t.Text, t.x, t.y))
    linhas.append(doc.Parameters.Count)
    linhas.append(doc.Selection.Count)
    linhas.append(doc.Sheets.ActiveSheet.Name)
    return linhas


def situacoes(r):
    return {(i.sheet_name, i.regra): i.situacao for i in r.items}


# ---- Desenho certo, como o das fotos ----
fechar_tudo()
doc = novo(3)
folha(doc, 1, "1:4", "1 / 3", vistas=(("VIEW LOOKING FWD", 0.25), ("ZONE A0", 1.0), ("Isometric view", 0.05), ("ZONES_A0_SHT1", 1.0)))
folha(doc, 2, "1:4", "2", vistas=(("PLAN VIEW", 0.5), ("ZONE A0[2]", 1.0), ("2F7", 0.25), ("1F7", 0.25), ("ZONES_A0_SHT1[2]", 1.0)))
# Folha 3: o numero fica na Main View, sem nada no Background.
folha(doc, 3, "1:4", None, vistas=(("1C33", 0.25), ("SECTION A-A", 0.5)), na_principal="3")
doc.Sheets.Item(2).Activate()
antes = foto(doc)
r = tc.conferir_template(b)
confere("não altera nada no desenho, nem a folha ativa", foto(doc) == antes)
confere("desenho certo: nada apontado", r.errados == 0 and r.conferir == 0, situacoes(r) if r.errados or r.conferir else f"{r.certos} certos")
confere("confere 3 itens por folha e o total", r.certos == 10 and r.total_folhas == 3, r.certos)
lidos = {(i.sheet_name, i.regra): i.lido for i in r.items}
confere("lê o que está na legenda", lidos[("Sheet.1", tc.NUMERACAO)] == "1 / 3" and lidos[("Sheet.3", tc.NUMERACAO)] == "3" and lidos[("Sheet.2", tc.ESCALA)] == "1:4" and lidos[("Sheet.1", tc.FORMATO)] == "A0", lidos)

# ---- VIEW LOOKING conta, isometrica e PLAN VIEW nao ----
fechar_tudo()
doc = novo(3)
folha(doc, 1, "1:4", "1 / 3", vistas=(("VIEW LOOKING FWD", 0.5), ("Isometric view", 0.25)))
folha(doc, 2, "1:4", "2", vistas=(("PLAN VIEW", 0.25), ("Isometric view", 0.25)))
folha(doc, 3, "1:4", "3", vistas=(("VIEW LOOKING AFT", 0.25), ("PLAN VIEW", 0.5), ("Isometric view", 0.1)))
s = situacoes(tc.conferir_template(b))
confere("VIEW LOOKING em outra escala é erro, mesmo com a isométrica batendo", s[("Sheet.1", tc.ESCALA)] == tc.ERRADO, s)
confere("só PLAN VIEW e isométrica: conferir", s[("Sheet.2", tc.ESCALA)] == tc.CONFERIR, s)
confere("VIEW LOOKING certa: PLAN VIEW e isométrica diferentes não atrapalham", s[("Sheet.3", tc.ESCALA)] == tc.CERTO, s)

# ---- Papel de verdade ----
fechar_tudo()
doc = novo()
for i, (formato, papel) in enumerate((("A0", 2), ("A1", 3), ("A2", 4), ("A3", 5), ("A0", 3)), 1):
    folha(doc, i, "1:4", "1/5" if i == 1 else str(i), formato=formato, papel=papel, vistas=(("2F7", 0.25),))
s = situacoes(tc.conferir_template(b))
confere("cada formato bate com o papel do CATIA", all(s[(f"Sheet.{i}", tc.FORMATO)] == tc.CERTO for i in range(1, 5)), s)
confere("etiqueta A0 em papel A1 é erro", s[("Sheet.5", tc.FORMATO)] == tc.ERRADO)
confere("desenho sem No_of_Sheets não acusa", ("Sheet.1", tc.TOTAL) not in s)

# ---- Tudo errado ----
fechar_tudo()
doc = novo(5)
folha(doc, 1, "1:2", "1 / 5", vistas=(("2F7", 0.25),))
folha(doc, 2, "1:4", "2 / 3", vistas=(("2F7", 0.25), ("1F7", 0.5)))
# Folha 3: numero na Main View e o total antigo ainda no Background.
folha(doc, 3, "NTS", "3", vistas=(("PLAN VIEW", 0.5),), na_principal="4")
r = tc.conferir_template(b)
s = situacoes(r)
confere("total do parâmetro errado", s[("Sheet.1", tc.TOTAL)] == tc.ERRADO)
confere("primeira folha com total errado", s[("Sheet.1", tc.NUMERACAO)] == tc.ERRADO)
confere("segunda folha com 2/3", s[("Sheet.2", tc.NUMERACAO)] == tc.ERRADO)
confere("número repetido na Main View", s[("Sheet.3", tc.NUMERACAO)] == tc.ERRADO, [i.lido for i in r.items if i.sheet_name == "Sheet.3"])
confere("escala que não bate é erro", s[("Sheet.1", tc.ESCALA)] == tc.ERRADO)
confere("só parte das vistas bate: conferir", s[("Sheet.2", tc.ESCALA)] == tc.CONFERIR)
confere("sem vista para comparar: conferir", s[("Sheet.3", tc.ESCALA)] == tc.CONFERIR)

# ---- Legenda sem os rotulos ----
fechar_tudo()
doc = novo()
sh = doc.Sheets.Item(1)
sh.PaperSize = 2
sh.Views.Item(2).Texts.Add("A0", 1175, 8)
s = situacoes(tc.conferir_template(b))
confere("campo não achado não vira certo nem errado", s[("Sheet.1", tc.NUMERACAO)] == tc.CONFERIR and s[("Sheet.1", tc.ESCALA)] == tc.CONFERIR, s)

# ---- A tela ----
fechar_tudo()
doc = novo(3)  # 2 folhas: o parametro e o campo da folha 1 estao errados
folha(doc, 1, "1:4", "1 / 3", vistas=(("2F7", 0.25),))
folha(doc, 2, "1:4", "2", vistas=(("1F7", 0.25),))
doc.Sheets.Item(1).Activate()

qt = QApplication(sys.argv)


def espera(condicao, limite=60.0):
    fim = time.perf_counter() + limite
    while time.perf_counter() < fim:
        QCoreApplication.processEvents(QEventLoop.AllEvents, 50)
        if condicao():
            return True
        time.sleep(0.01)
    return False


def clica(botao):
    QTest.mouseClick(botao, Qt.LeftButton)


def foto_tela(nome):
    if IMAGENS:
        os.makedirs(IMAGENS, exist_ok=True)
        j.grab().save(os.path.join(IMAGENS, nome + ".png"))


j = HubWindow()
j.show()
p = j.templatecheck_page
g = j.geral_page
clica(j.pills["Check"])
clica(j.rail_buttons["Check de Template"])
confere("trilho leva ao Check de Template", j._pages.currentIndex() == PAGINA_CHECKTEMPLATE)
confere("percebe o desenho", espera(lambda: p.btn_run.text() == "CONFERIR O TEMPLATE", 10), p.btn_run.text())
antes = foto(doc)
clica(p.btn_run)
confere("termina", espera(lambda: p._stack.currentIndex() == tool_page.PAGINA_RESULTADO), p.lbl_sub.text())
confere("abre no que precisa revisar", p.table.rowCount() == 2 and p.card_errados.numero.text() == "2", [p.table.item(n, 2).text() for n in range(p.table.rowCount())])
linha_numero = next(n for n, i in enumerate(p._rows) if i.regra == tc.NUMERACAO)
confere("mostra lido e esperado", p.table.item(linha_numero, 3).text() == "1 / 3" and p.table.item(linha_numero, 4).text() == "1/2")
confere("mostra a folha no CATIA", espera(lambda: "Folha aberta" in p.lbl_nav_state.text(), 20), p.lbl_where.text())
foto_tela("template_resultado")
clica(p.btn_todos)
confere("o filtro Todos mostra tudo", p.table.rowCount() == len(p._report.items), p.table.rowCount())
confere("o selo do trilho conta os errados", j.rail_badges["Check de Template"].text() == "2", j.rail_badges["Check de Template"].text())
confere("Visão geral recebe o resultado", g._template is p._report and "2 errados" in g.linha_template.lbl_resultado.text(), g.linha_template.lbl_resultado.text())
sh2 = doc.Sheets.Item(2)
linha = next(n for n, i in enumerate(p._rows) if i.sheet_name == "Sheet.2")
p.table.setCurrentCell(linha, 2)
confere("clicar na linha abre a folha certa", espera(lambda: doc.Sheets.ActiveSheet.Name == "Sheet.2" and "Folha aberta" in p.lbl_nav_state.text(), 20), doc.Sheets.ActiveSheet.Name)
doc.Sheets.Item(1).Activate()
agora = foto(doc)
confere("a tela não altera o desenho", agora == antes)
clica(j.rail_buttons["Visão geral"])
espera(lambda: False, 0.3)
foto_tela("template_visao_geral")
clica(g.linha_template.btn_revisar)
confere("Revisar volta para o Check de Template", j._pages.currentIndex() == PAGINA_CHECKTEMPLATE)
clica(j.btn_compact)
espera(lambda: False, 0.4)
foto_tela("template_compacto")
confere("no compacto dá para ver lido e esperado", j.width() == 460 and not p.table.isColumnHidden(3) and not p.table.isColumnHidden(4) and p.table.columnViewportPosition(4) + p.table.columnWidth(4) <= p.table.viewport().width(), j.width())
clica(j.btn_compact)
espera(lambda: False, 0.4)

fechar_tudo()
espera(lambda: False, 3)
j.close()
print("RESULTADO:", "TUDO CERTO" if not falhas else f"{len(falhas)} FALHAS: {falhas}", flush=True)
sys.stdout.flush()
os._exit(1 if falhas else 0)
