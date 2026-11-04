"""Compara o Split 2D e o Split 3D em Python com as macros em vba_referencia.

Cada arquivo gerado e aberto e fotografado: folhas, vistas, travas, textos, Bodies e planos.
O estado do documento original e do CATIA tambem e comparado.

Uso (com o CATIA aberto e sem desenhos importantes abertos, porque fecha todos):
    python tests/parity/rodar_paridade_splits.py
"""
from __future__ import annotations

import os
import re
import shutil
import sys
import tempfile
import time

import pythoncom

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.join(AQUI, "..", "..")
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.join(RAIZ, "src"))

import apoio  # noqa: E402
from engine import splits as sp  # noqa: E402
from engine.catia_bridge import CAMPO, CatiaBridge  # noqa: E402

SCRIPT = "montar_fixtures_splits.catvbs"

# Sem isto, um erro nao tratado abriria uma janela no Excel escondido. E o que o painel faz.
EXTRA = r'''

Public Sub Rodar2D()
    Split2D.ExecutarSplit2D
End Sub

Public Sub Rodar3D()
    On Error GoTo TrataErro
    Split3D.ExecutarSplit3D
    Exit Sub
TrataErro:
    MsgTeste "Erro ao executar o SPLIT 3D:" & vbCrLf & Err.Description, 16, "SPLIT 3D"
End Sub
'''


def preparar(nome: str, destino: str, pasta_downloads: str = "") -> None:
    fonte = apoio.trocar_janelas(apoio.ler_fonte(os.path.join(RAIZ, "vba_referencia", nome)))
    # So no teste: no Excel, Application e o proprio Excel.
    fonte = re.sub(r"\bAs Application\b", "As Object", fonte)
    fonte = re.sub(r"^\s*DoEvents\s*$", "", fonte, flags=re.M)
    if pasta_downloads:
        de = 'Environ$("USERPROFILE") & "\\Downloads\\"'
        assert de in fonte
        fonte = fonte.replace(de, '"' + pasta_downloads + '\\"')
    apoio.gravar_fonte(fonte, destino)


def ss(bridge, funcao, *args):
    r = bridge.app.SystemService.ExecuteScript(AQUI, 1, SCRIPT, funcao, list(args))
    # Documentos internos da area de transferencia: o numero muda a cada colagem.
    return re.sub(r"ccp_dummy\d+", "ccp_dummy", r)


def fotos_da_pasta(bridge, pasta: str) -> list:
    if not os.path.isdir(pasta):
        return ["SEM PASTA"]
    saida = []
    for nome in sorted(os.listdir(pasta)):
        caminho = os.path.join(pasta, nome)
        if os.path.isfile(caminho):
            saida.append(ss(bridge, "FotoArquivo", caminho))
    return saida


def abrir(bridge, caminho) -> None:
    ss(bridge, "Fechar")
    if caminho == "NOVO":
        ss(bridge, "DesenhoNovo")
    elif caminho:
        bridge.app.Documents.Open(caminho)


def vba(xl, trabalho, sub, respostas) -> list:
    saida = os.path.join(trabalho, "saida.txt")
    if os.path.exists(saida):
        os.remove(saida)
    xl.Run("Preparar", respostas, saida)
    xl.Run(sub)
    if not os.path.exists(saida):
        return []
    with open(saida, encoding="cp1252") as f:
        return f.read().splitlines()


def msg(texto):
    return CAMPO.join(["MSG", "", apoio.plano(texto)])


def normaliza(linhas, pasta_a="", pasta_b="") -> list:
    saida = []
    for l in linhas:
        c = l.split(CAMPO)
        if c[0] == "MSG":
            l = CAMPO.join(["MSG", "", c[-1]])
        l = apoio.sem_acento(l)
        if pasta_a:
            l = l.replace(pasta_a, "<PASTA>")
        if pasta_b:
            l = l.replace(pasta_b, "<PASTA>")
        saida.append(l)
    return saida


def caso_2d(xl, bridge, trabalho, nome, caminho, baixa_vba, baixa_py, travadas=0) -> int:
    for pasta in (baixa_vba, baixa_py):
        shutil.rmtree(pasta, ignore_errors=True)
        os.makedirs(pasta)
    abrir(bridge, caminho)
    t0 = time.perf_counter()
    m_vba = vba(xl, trabalho, "Rodar2D", "")
    t_vba = time.perf_counter() - t0
    e_vba = ss(bridge, "Estado")

    abrir(bridge, caminho)
    linhas = []
    t0 = time.perf_counter()
    try:
        rep = sp.run_split_2d(bridge, lambda m: linhas.append(msg(m)), lambda m: linhas.append(msg(m)), downloads=baixa_py)
        if rep is not None:
            linhas.append(msg(rep.mensagem))
    except sp.SplitError as exc:
        linhas.append(msg(exc.mensagem))
    t_py = time.perf_counter() - t0
    e_py = ss(bridge, "Estado")

    f_vba = [f for p in sorted(os.listdir(baixa_vba)) for f in fotos_da_pasta(bridge, os.path.join(baixa_vba, p))]
    f_py = [f for p in sorted(os.listdir(baixa_py)) for f in fotos_da_pasta(bridge, os.path.join(baixa_py, p))]

    falha = 0
    if normaliza(m_vba, baixa_vba, baixa_py) != normaliza(linhas, baixa_vba, baixa_py):
        falha = 1
        print(f"  mensagens:\n    VBA: {m_vba}\n    PY : {linhas}")
    if e_vba != e_py:
        falha = 1
        print(f"  estado:\n    VBA: {e_vba}\n    PY : {e_py}")
    if f_vba != f_py:
        falha = 1
        print(f"  arquivos ({len(f_vba)} x {len(f_py)}):")
        for a, b in zip(f_vba, f_py):
            if a != b:
                print(f"    VBA: {a}\n    PY : {b}")
    print(f"[{'DIFERENTE' if falha else 'IGUAL'}] 2D, {nome}: {len(f_py)} arquivos; VBA {t_vba:.1f} s, Python {t_py:.2f} s", flush=True)
    return falha


def caso_3d(xl, bridge, trabalho, nome, caminho, respostas) -> int:
    pasta = os.path.join(os.path.dirname(caminho), "SPLIT_PARTS") if caminho and caminho != "NOVO" else ""
    if pasta:
        shutil.rmtree(pasta, ignore_errors=True)
    abrir(bridge, caminho)
    t0 = time.perf_counter()
    m_vba = vba(xl, trabalho, "Rodar3D", respostas)
    t_vba = time.perf_counter() - t0
    # A macro nao devolve a tela nem os alertas depois de um erro; o Python devolve.
    e_vba = ss(bridge, "Estado")
    f_vba = fotos_da_pasta(bridge, pasta) if pasta else []
    if pasta:
        shutil.rmtree(pasta, ignore_errors=True)

    abrir(bridge, caminho)
    linhas, fila = [], respostas.split(";")

    def ask(p, t, d):
        linhas.append(CAMPO.join(["INPUT", t, apoio.plano(p), d]))
        return fila.pop(0)

    t0 = time.perf_counter()
    try:
        rep = sp.run_split_3d(bridge, ask, lambda m: linhas.append(msg(m)))
        if rep is not None:
            linhas.append(msg(rep.mensagem))
    except sp.SplitError as exc:
        linhas.append(msg(exc.mensagem))
    t_py = time.perf_counter() - t0
    e_py = ss(bridge, "Estado")
    f_py = fotos_da_pasta(bridge, pasta) if pasta else []

    falha = 0
    a, b = normaliza(m_vba), normaliza(linhas)
    # O texto do erro de "nenhum documento" vem do CATIA e muda conforme o cliente.
    if caminho is None:
        a = [l.split("<CRLF>")[0] for l in a]
        b = [l.split("<CRLF>")[0] for l in b]
    if a != b:
        falha = 1
        print(f"  mensagens:\n    VBA: {m_vba}\n    PY : {linhas}")
    if e_vba != e_py and caminho:
        falha = 1
        print(f"  estado:\n    VBA: {e_vba}\n    PY : {e_py}")
    if f_vba != f_py:
        falha = 1
        print(f"  arquivos ({len(f_vba)} x {len(f_py)}):")
        for x, y in zip(f_vba, f_py):
            if x != y:
                print(f"    VBA: {x}\n    PY : {y}")
    print(f"[{'DIFERENTE' if falha else 'IGUAL'}] 3D, {nome}: {len(f_py)} arquivos; VBA {t_vba:.1f} s, Python {t_py:.2f} s", flush=True)
    return falha


def main() -> int:
    trabalho = tempfile.mkdtemp(prefix="paridade_splits_")
    pythoncom.CoInitialize()
    bridge = CatiaBridge()
    r = ss(bridge, "Montar", trabalho)
    print("Documentos de teste:", r, trabalho, flush=True)
    if not r.startswith("OK"):
        return 1
    baixa_vba = os.path.join(trabalho, "baixa_vba")
    baixa_py = os.path.join(trabalho, "baixa_py")
    f2, f3 = os.path.join(trabalho, "s2.txt"), os.path.join(trabalho, "s3.txt")
    preparar("SPLIT 2D", f2, baixa_vba)
    preparar("SPLIT 3D", f3)
    xl, wb = apoio.abrir_excel(
        {"Split2D": f2, "Split3D": f3},
        referencias=("InfTypeLib.tlb", "DraftingTypeLib.tlb", "MecModTypeLib.tlb", "PartTypeLib.tlb", "ProductStructureTypeLib.tlb"),
        extra=EXTRA,
    )
    relogio = apoio.vigia(xl, 900)
    arq = lambda n: os.path.join(trabalho, n)  # noqa: E731
    falhas = 0
    try:
        falhas += caso_2d(xl, bridge, trabalho, "sem documento", None, baixa_vba, baixa_py)
        falhas += caso_2d(xl, bridge, trabalho, "peca aberta", arq("SPL_PECA.CATPart"), baixa_vba, baixa_py)
        falhas += caso_2d(xl, bridge, trabalho, "desenho sem salvar", "NOVO", baixa_vba, baixa_py)
        falhas += caso_2d(xl, bridge, trabalho, "quatro folhas, vistas destravadas", arq("SPL_DESENHO.CATDrawing"), baixa_vba, baixa_py)
        falhas += caso_2d(xl, bridge, trabalho, "tudo ja travado", arq("SPL_TRAVADO.CATDrawing"), baixa_vba, baixa_py)
        peca = arq("SPL_PECA.CATPart")
        falhas += caso_3d(xl, bridge, trabalho, "sem documento", None, "2")
        falhas += caso_3d(xl, bridge, trabalho, "desenho aberto", arq("SPL_DESENHO.CATDrawing"), "2")
        falhas += caso_3d(xl, bridge, trabalho, "sem Bodies", arq("SPL_SEM_BODIES.CATPart"), "2")
        falhas += caso_3d(xl, bridge, trabalho, "cancela", peca, ";")
        falhas += caso_3d(xl, bridge, trabalho, "texto sem numero", peca, "abc")
        falhas += caso_3d(xl, bridge, trabalho, "uma parte", peca, "1")
        falhas += caso_3d(xl, bridge, trabalho, "duas partes, sobra um Body", peca, "2")
        falhas += caso_3d(xl, bridge, trabalho, "3 partes escrito com texto", peca, "3 partes")
        falhas += caso_3d(xl, bridge, trabalho, "2,5 vira 2", peca, "2.5")
        falhas += caso_3d(xl, bridge, trabalho, "mais partes que Bodies", peca, "99")
        ss(bridge, "Fechar")
    finally:
        relogio.cancel()
        wb.Close(False)
        xl.Quit()
    print("RESULTADO:", "TUDO IGUAL" if not falhas else f"{falhas} COM DIFERENCA")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
