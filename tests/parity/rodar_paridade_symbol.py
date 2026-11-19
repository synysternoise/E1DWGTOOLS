"""Compara o Symbol Shape Converter em Python com a macro vba/symbolconvert.txt (CATMain11).

Monta um desenho com leaders de todos os simbolos, em duas folhas, na Main View, no Background e
numa vista trancada. Roda a macro numa copia e o Python em outra e compara simbolo por simbolo.

Uso (com o CATIA aberto e sem desenhos importantes abertos, porque fecha todos):
    python tests/parity/rodar_paridade_symbol.py
"""
from __future__ import annotations

import os
import sys
import tempfile
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.join(AQUI, "..", "..")
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.join(RAIZ, "src"))

import apoio  # noqa: E402
from engine import symbol_shape as ss  # noqa: E402
from engine.catia_bridge import CAMPO, CatiaBridge, CatiaError  # noqa: E402

EXTRA = r'''

Public Sub RodarSymbol()
    SymbolConvert.CATMain11
End Sub
'''
# Simbolos postos nos leaders: os cinco que a macro conhece e outros que ela nao pode tocar.
SIMBOLOS = (18, 19, 31, 16, 17, 20, 1, 2, 5, 12, 25)
ESPERADO = {18: 20, 19: 20, 31: 20, 16: 17}
falhas = 0


def confere(nome: str, ok: bool, detalhe="") -> None:
    global falhas
    falhas += 0 if ok else 1
    print(("  ok      " if ok else "  FALHOU  ") + nome + ("" if ok else f"   {detalhe}"), flush=True)


def fechar_tudo(app) -> None:
    while app.Documents.Count:
        app.Documents.Item(1).Close()


def texto_com_leaders(vista, rotulo: str, x: float, y: float, simbolos) -> None:
    t = vista.Texts.Add(rotulo, x, y)
    for n, simbolo in enumerate(simbolos):
        leader = t.Leaders.Add(x - 20.0 - 5.0 * n, y - 15.0)
        leader.HeadSymbol = simbolo


def montar(app, caminho: str, com_simbolos: bool = True) -> None:
    fechar_tudo(app)
    doc = app.Documents.Add("Drawing")
    folhas = doc.Sheets
    folhas.Add("Sheet.2")
    for f in range(1, folhas.Count + 1):
        sh = folhas.Item(f)
        vistas = sh.Views
        livre = vistas.Add("LIVRE")
        livre.x, livre.y = 200.0, 200.0
        trancada = vistas.Add("TRANCADA")
        trancada.x, trancada.y = 500.0, 200.0
        for i, simbolo in enumerate(SIMBOLOS if com_simbolos else (17, 20, 1)):
            texto_com_leaders(livre, f"L{simbolo}", 0.0, 12.0 * i, (simbolo,))
            texto_com_leaders(trancada, f"T{simbolo}", 0.0, 12.0 * i, (simbolo,))
        if com_simbolos:
            texto_com_leaders(livre, "DOIS", 60.0, 0.0, (18, 16))  # dois leaders no mesmo texto
            texto_com_leaders(vistas.Item(1), "MAIN", 100.0, 500.0, (19,))  # Main View
            texto_com_leaders(vistas.Item(2), "FUNDO", 100.0, 520.0, (31,))  # Background View
        livre.Texts.Add("SEM LEADER", 80.0, 40.0)
        trancada.LockStatus = True
    doc.SaveAs(caminho)
    doc.Close()


def foto(app) -> list:
    """Uma linha por leader: folha, vista, trava, texto, numero do leader e simbolo."""
    doc = app.ActiveDocument
    linhas = []
    for f in range(1, doc.Sheets.Count + 1):
        sh = doc.Sheets.Item(f)
        for v in range(1, sh.Views.Count + 1):
            vista = sh.Views.Item(v)
            for t in range(1, vista.Texts.Count + 1):
                texto = vista.Texts.Item(t)
                for l in range(1, texto.Leaders.Count + 1):
                    linhas.append((sh.Name, vista.Name, bool(vista.LockStatus), texto.Text, l, texto.Leaders.Item(l).HeadSymbol))
    return linhas


def vba(xl, trabalho: str) -> list:
    saida = os.path.join(trabalho, "saida.txt")
    if os.path.exists(saida):
        os.remove(saida)
    xl.Run("Preparar", "", saida)
    xl.Run("RodarSymbol")
    if not os.path.exists(saida):
        return []
    with open(saida, encoding="cp1252") as f:
        return [l.split(CAMPO)[-1] for l in f.read().splitlines()]


def caso(xl, bridge, trabalho: str, nome: str, caminho: str, espera_trocas) -> None:
    print(f"\n{nome}", flush=True)
    app = bridge.app
    fechar_tudo(app)
    app.Documents.Open(caminho)
    antes = foto(app)
    t0 = time.perf_counter()
    m_vba = vba(xl, trabalho)
    t_vba = time.perf_counter() - t0
    f_vba = foto(app)
    app.ActiveDocument.Close()

    app.Documents.Open(caminho)
    t0 = time.perf_counter()
    rep = ss.run_symbol_shape(bridge)
    t_py = time.perf_counter() - t0
    f_py = foto(app)
    app.ActiveDocument.Close()

    certo = [a[:5] + (ESPERADO.get(a[5], a[5]),) for a in antes]
    confere("o desenho de teste tem leaders", len(antes) > 0, len(antes))
    confere("a macro converte pela regra", f_vba == certo, [x for x in zip(f_vba, certo) if x[0] != x[1]][:3])
    confere("o Python deixa o desenho igual ao da macro", f_py == f_vba, [x for x in zip(f_py, f_vba) if x[0] != x[1]][:3])
    confere("a mensagem é a mesma", [apoio.sem_acento(rep.mensagem)] == [apoio.sem_acento(m) for m in m_vba], (rep.mensagem, m_vba))
    trocas = sum(1 for a, d in zip(antes, f_py) if a != d)
    confere("a contagem bate com o que mudou", rep.convertidos == trocas == espera_trocas, (rep.convertidos, trocas, espera_trocas))
    confere("leaders lidos", rep.leaders == len(antes), (rep.leaders, len(antes)))
    print(f"  tempo: macro {t_vba:.2f} s, Python {t_py:.2f} s", flush=True)


def main() -> int:
    trabalho = tempfile.mkdtemp(prefix="paridade_symbol_")
    bridge = CatiaBridge()
    app = bridge.app
    cheio = os.path.join(trabalho, "SYM_CHEIO.CATDrawing")
    limpo = os.path.join(trabalho, "SYM_LIMPO.CATDrawing")  # a tela usa o SYM_CHEIO desta pasta
    montar(app, cheio)
    montar(app, limpo, com_simbolos=False)

    fonte = os.path.join(trabalho, "symbolconvert.bas")
    apoio.gravar_fonte(apoio.trocar_janelas(apoio.ler_fonte(os.path.join(RAIZ, "vba", "symbolconvert.txt"))), fonte)
    xl, wb = apoio.abrir_excel({"SymbolConvert": fonte}, extra=EXTRA)
    vigia = apoio.vigia(xl, 240)
    try:
        # Por folha: 4 de cada vista (18, 19, 31, 16), 2 do texto de dois leaders, Main e Background.
        caso(xl, bridge, trabalho, "Desenho com todos os símbolos", cheio, 2 * (4 + 4 + 2 + 1 + 1))
        caso(xl, bridge, trabalho, "Desenho sem nada para converter", limpo, 0)

        print("\nSem desenho ativo", flush=True)
        fechar_tudo(app)
        try:
            ss.run_symbol_shape(bridge)
            confere("avisa que não há desenho", False)
        except CatiaError as exc:
            confere("avisa que não há desenho", True, str(exc))
    finally:
        vigia.cancel()
        wb.Close(False)
        xl.Quit()
        fechar_tudo(app)
    print("\nRESULTADO:", "TUDO IGUAL" if not falhas else f"{falhas} DIFERENTE(S)", flush=True)
    print("Pasta:", trabalho, flush=True)
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
