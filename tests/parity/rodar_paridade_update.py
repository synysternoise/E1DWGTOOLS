"""Compara o Update Template em Python com a macro atual (update.txt do CONSERTO-E1DWGVBA).

Depois de cada execucao, o desenho e fotografado: folhas, papel, vistas, textos, geometria,
parametros e documentos abertos. Em seguida os parametros mudam, para provar que os vinculos
da legenda foram mesmo refeitos, e o desenho e fotografado de novo.

Uso (com o CATIA aberto e sem desenhos importantes abertos, porque fecha todos):
    python tests/parity/rodar_paridade_update.py <pasta do E1DWGVBA> [--so-vba]
"""
from __future__ import annotations

import os
import re
import sys
import tempfile
import time

import pythoncom

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.join(AQUI, "..", "..", "src"))

import apoio  # noqa: E402
from engine import atualizar_template as at  # noqa: E402
from engine.catia_bridge import CAMPO, REGISTRO, CatiaBridge  # noqa: E402

FIM_MODULO = r'''

Public Sub Rodar()
    ConvertTemplate
End Sub
'''


def preparar_fonte(pasta_vba: str, pasta_modelos: str, destino: str) -> None:
    fonte = apoio.trocar_janelas(apoio.ler_fonte(os.path.join(pasta_vba, "update.txt")))
    de = r'"\\nfscad05.sjk.emb\dmuv5\smarteam\b01\v5\DLNames\START_UP\"'
    assert de in fonte
    fonte = fonte.replace(de, '"' + pasta_modelos + '\\"')
    # DoEvents em Excel escondido pode rodar outras coisas; nao muda nada no CATIA.
    fonte = re.sub(r"^\s*DoEvents\s*$", "", fonte, flags=re.M)
    # So no teste: no Excel, "Parameters" e um tipo do proprio Excel. Dentro do CATIA nao ha conflito.
    fonte = re.sub(r"\bAs Parameters\b", "As Object", fonte)
    # Decisao: doc.Saved nao e confiavel, e a macro recusa sempre o template ja aberto. O Python
    # recusa igual, mas nao diz que ele tem alteracoes, porque nao ha como saber.
    velho = '"O template esta aberto com alteracoes:"'
    assert velho in fonte
    fonte = fonte.replace(velho, '"O template ja esta aberto:"')
    apoio.gravar_fonte(fonte, destino)


def foto(bridge) -> list:
    r = bridge.app.SystemService.ExecuteScript(AQUI, 1, "sonda_update.catvbs", "Foto", [])
    if r.startswith("ERRO FOTO"):
        raise RuntimeError(r)
    return r.split(REGISTRO)


def sonda(bridge, funcao):
    return bridge.app.SystemService.ExecuteScript(AQUI, 1, "sonda_update.catvbs", funcao, [])


def abrir(bridge, caminhos) -> None:
    sonda(bridge, "Fechar")
    for c in caminhos:
        bridge.app.Documents.Open(c)


def vba_uma(xl, trabalho, respostas) -> list:
    saida = os.path.join(trabalho, "saida.txt")
    if os.path.exists(saida):
        os.remove(saida)
    xl.Run("Preparar", respostas, saida)
    xl.Run("Rodar")
    if not os.path.exists(saida):
        return []
    with open(saida, encoding="cp1252") as f:
        return f.read().splitlines()


def python_uma(bridge, respostas, pasta_modelos) -> tuple:
    linhas, fila = [], respostas.split(";")

    def ask(pergunta, titulo, sugestao):
        linhas.append(CAMPO.join(["INPUT", titulo, apoio.plano(pergunta), sugestao]))
        return fila.pop(0)

    t0 = time.perf_counter()
    try:
        rep = at.run_update_template(bridge, ask, pasta=pasta_modelos)
        if rep is not None:
            linhas.append(CAMPO.join(["MSG", at.TITULO_RESULTADO, apoio.plano(rep.mensagem)]))
    except at.TemplateError as exc:
        linhas.append(CAMPO.join(["MSG", at.TITULO_ERRO, apoio.plano(exc.mensagem)]))
    return linhas, time.perf_counter() - t0


def normaliza_msgs(linhas: list) -> list:
    # O VBA usa "Erro numero"; o resto so difere em acentos. Melhoria: com o template ja aberto o
    # desenho nao chegou a mudar, e o Python nao avisa que ele pode ter ficado parcialmente convertido.
    aviso = re.compile(r"(<CRLF>)*O desenho pode ter ficado parcialmente convertido\..*$", re.S)
    return [aviso.sub("", apoio.sem_acento(l)) if "ja esta aberto" in apoio.sem_acento(l) else apoio.sem_acento(l) for l in linhas]


def medir_alternando(xl, bridge, trabalho, pasta_modelos, caminhos, respostas, vezes=3) -> None:
    """O CATIA fica mais lento ao longo da sessao: alterna quem roda primeiro e compara as somas."""
    t_vba, t_py = [], []
    for i in range(vezes):
        for lado in (("v", "p") if i % 2 == 0 else ("p", "v")):
            abrir(bridge, caminhos)
            foto(bridge)
            if lado == "v":
                t0 = time.perf_counter()
                vba_uma(xl, trabalho, respostas)
                t_vba.append(time.perf_counter() - t0)
            else:
                t_py.append(python_uma(bridge, respostas, pasta_modelos)[1])
    print("  tempo alternando a ordem: VBA", [round(x, 1) for x in t_vba], "Python", [round(x, 1) for x in t_py], flush=True)
    print(f"  soma: VBA {sum(t_vba):.1f} s, Python {sum(t_py):.1f} s", flush=True)


def caso(xl, bridge, trabalho, pasta_modelos, nome, caminhos, respostas, so_vba) -> int:
    abrir(bridge, caminhos)
    antes = foto(bridge) if caminhos and caminhos[-1].lower().endswith(".catdrawing") else []
    t0 = time.perf_counter()
    vba = vba_uma(xl, trabalho, respostas)
    t_vba = time.perf_counter() - t0
    f_vba = foto(bridge) if antes else []
    v_vba = []
    if antes:
        sonda(bridge, "TestarVinculos")
        v_vba = foto(bridge)
    if so_vba:
        print(f"--- {nome} ({t_vba:.1f} s)")
        for l in vba:
            print("    ", l.replace(CAMPO, " | ")[:700])
        if antes:
            print("     mudaram:", len(set(f_vba) ^ set(antes)), "linhas da foto de", len(antes), "->", len(f_vba))
            print("     vinculos:", [l.split(CAMPO)[4] for l in v_vba if l.startswith("TEXTO") and "NOVO-PN" in l][:6])
        return 0

    abrir(bridge, caminhos)
    antes_py = foto(bridge) if antes else []
    falha = 0
    if antes_py != antes:
        falha = 1
        print("  o desenho nao partiu do mesmo estado nos dois lados")
    py, t_py = python_uma(bridge, respostas, pasta_modelos)
    f_py = foto(bridge) if antes else []
    v_py = []
    if antes:
        sonda(bridge, "TestarVinculos")
        v_py = foto(bridge)

    if normaliza_msgs(vba) != normaliza_msgs(py):
        falha = 1
        print(f"  mensagens diferentes:\n    VBA: {vba}\n    PY : {py}")
    for rot, a, b in (("depois de rodar", f_vba, f_py), ("depois de mudar os parametros", v_vba, v_py)):
        difs = [(x, y) for x, y in zip(a, b) if x != y]
        if difs or len(a) != len(b):
            falha = 1
            print(f"  foto diferente {rot}: {len(difs)} linhas, {len(a)} x {len(b)}")
            for x, y in difs[:12]:
                print(f"    VBA: {x!r}\n    PY : {y!r}")
    links = sum(1 for l in v_py if l.startswith("TEXTO") and "NOVO-PN" in l)
    print(f"[{'DIFERENTE' if falha else 'IGUAL'}] {nome}: {len(f_py)} linhas na foto, {links} textos ligados ao PN; VBA {t_vba:.1f} s, Python {t_py:.2f} s", flush=True)
    return falha


def main() -> int:
    pasta_vba = sys.argv[1]
    so_vba = "--so-vba" in sys.argv
    trabalho = tempfile.mkdtemp(prefix="paridade_update_")
    modelos = os.path.join(trabalho, "templates")
    pythoncom.CoInitialize()
    bridge = CatiaBridge()
    r = bridge.app.SystemService.ExecuteScript(AQUI, 1, "montar_fixtures_update.catvbs", "Montar", [trabalho])
    print("Desenhos de teste:", r, trabalho, flush=True)
    if not r.startswith("OK"):
        return 1
    fonte = os.path.join(trabalho, "update_teste.txt")
    preparar_fonte(pasta_vba, modelos, fonte)
    xl, wb = apoio.abrir_excel({"ConversorTemplate": fonte}, extra=FIM_MODULO.replace("ConvertTemplate", "ConversorTemplate.ConvertTemplate"))
    relogio = apoio.vigia(xl, 900)
    arq = lambda n: os.path.join(trabalho, n)  # noqa: E731
    modelo = lambda f, s="REV01": os.path.join(modelos, f"E1_DRAWING TEMPLATE_SHEET {f}_CATIAV5R32_{s}.CATDrawing")  # noqa: E731
    casos = [
        ("sem documento", [], ""),
        ("documento nao e desenho", [arq("NAO_E_DESENHO.CATPart")], ""),
        ("sem formato, cancela", [arq("UPD_SEM_FORMATO.CATDrawing")], ";"),
        ("sem formato, formato invalido", [arq("UPD_SEM_FORMATO.CATDrawing")], "Z9"),
        ("sem formato, responde a1, faltam parametros", [arq("UPD_SEM_FORMATO.CATDrawing")], " a1 "),
        ("varios formatos, ZONE travada e numero na Main View", [arq("UPD_RICO.CATDrawing")], ""),
        ("papel do usuario E3 e 3A0", [arq("UPD_PAPEL_USUARIO.CATDrawing")], ""),
        ("template vazio", [arq("UPD_TEMPLATE_VAZIO.CATDrawing")], ""),
        ("template ja aberto, sem alteracao", [modelo("A1"), modelo("A0"), arq("UPD_RICO.CATDrawing")], ""),
    ]
    falhas = 0
    try:
        for nome, caminhos, respostas in casos:
            falhas += caso(xl, bridge, trabalho, modelos, nome, caminhos, respostas, so_vba)
        if not so_vba:
            medir_alternando(xl, bridge, trabalho, modelos, [arq("UPD_RICO.CATDrawing")], "")
        sonda(bridge, "Fechar")
    finally:
        relogio.cancel()
        wb.Close(False)
        xl.Quit()
    print("RESULTADO:", "TUDO IGUAL" if not falhas else f"{falhas} COM DIFERENCA")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
