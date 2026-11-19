"""Check de Template em legenda de template antigo, como a do desenho 171-43473-801 das fotos.

Tres arranjos, todos com SCALE 1/4 e 3 folhas A0:
  1. Rotulos dentro de um componente 2D (ditto) do Background e valores soltos por cima.
  2. Sem rotulo nenhum (a moldura e so desenho): o campo e achado pela posicao.
  3. Rotulo escrito "SHEET: OF", com dois-pontos.

Uso (com o CATIA aberto e sem desenhos importantes abertos, porque fecha todos):
    python tests/parity/testar_legenda_antiga.py
"""
from __future__ import annotations

import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "..", "src"))

from engine import template_check as tc  # noqa: E402
from engine.catia_bridge import CatiaBridge  # noqa: E402

falhas = []
b = CatiaBridge()
app = b.app
# Canto da legenda num A0 deitado (1189 x 841), como na foto: SCALE, DRAWING NUMBER e SHEET OF na mesma linha.
X_ESCALA, X_NUMERO, X_FOLHA, Y_ROTULO, Y_VALOR = 975.0, 1040.0, 1112.0, 55.0, 45.0


def confere(nome, ok, extra=""):
    print(f"[{'OK' if ok else 'FALHOU'}] {nome}{' ' + str(extra) if not ok else ''}", flush=True)
    if not ok:
        falhas.append(nome)


def fechar_tudo():
    app.DisplayFileAlerts = False
    while app.Documents.Count:
        app.Documents.Item(1).Close()


def valores(fundo, escala, numero):
    for texto, x, y in (
        ("GALLEY INSTL, G1", 1040, 75), ("171-43473-801", X_NUMERO, Y_VALOR), (escala, X_ESCALA, Y_VALOR),
        ("A0", 1175, 8), ("21", 1100, 6), ("22", 960, 6), ("23", 820, 6), ("A", 1182, 60),
    ):
        fundo.Texts.Add(texto, x, y)
    for pedaco, x in numero:
        fundo.Texts.Add(pedaco, x, Y_VALOR)


def desenho(arranjo: str):
    fechar_tudo()
    doc = app.Documents.Add("Drawing")
    doc.Parameters.CreateInteger("No_of_Sheets", 3)
    folhas = doc.Sheets
    moldura = None
    if arranjo == "ditto":
        detalhe = folhas.AddDetail("LEGENDA")
        moldura = detalhe.Views.Add("MOLDURA")
        for texto, x, y in (("SCALE", -65.0, 10.0), ("DRAWING NUMBER", 0.0, 10.0), ("SHEET OF", 72.0, 10.0), ("DRAWING TITLE", 0.0, 40.0)):
            moldura.Texts.Add(texto, x, y)
    for i in (1, 2, 3):
        sh = folhas.Item(i) if i == 1 else folhas.Add(f"Sheet.{i}")
        sh.PaperSize = 2
        sh.Orientation = 1
        fundo = sh.Views.Item(2)
        valores(fundo, "1/4", (("1 /", X_FOLHA - 6), ("3", X_FOLHA + 4)) if i == 1 else ((str(i), X_FOLHA),))
        if arranjo == "ditto":
            fundo.Components.Add(moldura, X_NUMERO, Y_ROTULO - 10.0)
        elif arranjo == "dois_pontos":
            fundo.Texts.Add("SCALE", X_ESCALA, Y_ROTULO)
            fundo.Texts.Add("SHEET: OF", X_FOLHA, Y_ROTULO)
        v = sh.Views.Add("Front view")
        v.Scale = 0.25
        z = sh.Views.Add("ZONE A0")
        z.Scale = 1.0
    return doc


def lidos(r):
    return {(i.sheet_name, i.regra): (i.lido, i.situacao, i.detalhe) for i in r.items}


for arranjo, titulo, pela_posicao in (
    ("ditto", "Rótulos dentro de um componente 2D", False),
    ("sem_rotulo", "Sem rótulo nenhum", True),
    ("dois_pontos", "Rótulo SHEET: OF", False),
):
    print(f"\n{titulo}", flush=True)
    try:
        desenho(arranjo)
    except Exception as exc:  # o CATIA de teste pode nao criar o componente
        confere("monta o desenho", False, exc)
        continue
    r = lidos(tc.conferir_template(b))
    for i, esperado in ((1, "1 / 3"), (2, "2"), (3, "3")):
        lido, situacao, detalhe = r[(f"Sheet.{i}", tc.NUMERACAO)]
        confere(f"folha {i}: lê o número {esperado} e dá Certo", lido == esperado and situacao == tc.CERTO, (lido, situacao, detalhe))
        confere(f"folha {i}: avisa quando achou pela posição", (tc.PELA_POSICAO in detalhe) == pela_posicao, detalhe)
        lido, situacao, detalhe = r[(f"Sheet.{i}", tc.ESCALA)]
        confere(f"folha {i}: lê a escala 1/4 e dá Certo", lido == "1/4" and situacao == tc.CERTO, (lido, situacao, detalhe))
        confere(f"folha {i}: formato A0 certo", r[(f"Sheet.{i}", tc.FORMATO)][1] == tc.CERTO, r[(f"Sheet.{i}", tc.FORMATO)])

print("\nEscala da legenda diferente da vista", flush=True)
doc = desenho("sem_rotulo")
doc.Sheets.Item(2).Views.Item(3).Scale = 0.5
r = lidos(tc.conferir_template(b))
confere("acusa a folha 2", r[("Sheet.2", tc.ESCALA)][1] == tc.ERRADO, r[("Sheet.2", tc.ESCALA)])
confere("as outras continuam certas", r[("Sheet.1", tc.ESCALA)][1] == tc.CERTO and r[("Sheet.3", tc.ESCALA)][1] == tc.CERTO)

fechar_tudo()
print("\nRESULTADO:", "TUDO CERTO" if not falhas else f"{len(falhas)} FALHAS: {falhas}", flush=True)
sys.exit(1 if falhas else 0)
