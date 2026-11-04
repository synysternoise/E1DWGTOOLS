"""Prova que cada Check concorda com o seu Fix, no CATIA de verdade.

- Check de Flags: nao altera nada, aponta o que o Fix Flags corrige, e depois do Fix nao aponta nada.
- Font Size Fix: corrige o que o Font Check aponta; depois, o Check nao aponta mais o que foi
  corrigido. O que nao foi corrigido continua igual, e so o tamanho muda.

Uso (com o CATIA aberto e sem desenhos importantes abertos, porque fecha todos):
    python tests/parity/testar_check_e_fix.py <pasta paridade_flags_*> <pasta com FONT_RICO.CATDrawing>
"""
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "..", "src"))

from engine import fix_flags as ff  # noqa: E402
from engine import font_check as fc  # noqa: E402
from engine.catia_bridge import CatiaBridge, REGISTRO, CAMPO  # noqa: E402

falhas = []


def confere(nome, ok, extra=""):
    print(f"[{'OK' if ok else 'FALHOU'}] {nome}{' ' + str(extra) if extra != '' else ''}", flush=True)
    if not ok:
        falhas.append(nome)


b = CatiaBridge()
app = b.app


def abre(caminho):
    app.DisplayFileAlerts = False
    while app.Documents.Count:
        app.Documents.Item(1).Close()
    return app.Documents.Open(caminho)


def foto():
    return app.SystemService.ExecuteScript(AQUI, 1, "sonda_flags.catvbs", "Foto", []).split(REGISTRO)


# ---- Flags ----
abre(os.path.join(sys.argv[1], "FLAGS_RICO.CATDrawing"))
antes = foto()
c1 = ff.check_flags(b)
confere("Check de Flags não altera o desenho", foto() == antes)
confere("Check encontra flags dos dois tipos", c1.objeto > 50 and c1.text_editor > 20 and c1.cadeado > 20, f"{c1.flags} flags, {c1.erradas} para corrigir")
exemplos = {i.before: i.after for i in c1.items if not i.ok}
confere("Check diz como deveria ser", exemplos.get("NL006") == "NL0006" and exemplos.get("AB123") == "AB0123" and exemplos.get(" NL006") == "NL0006", list(exemplos.items())[:3])
confere("flag correta não é apontada", not any(i.before == "NL0006" for i in c1.items if not i.ok))
rep = ff.run_fix_flags(b, lambda *a: True, lambda *a: None)
confere("Check e Fix contam as mesmas flags", c1.flags == rep.flags and c1.ignoradas == rep.ignoradas, f"{c1.flags} x {rep.flags}")
confere("o que o Check aponta é o que o Fix corrige", c1.erradas == rep.corrigidas and c1.certas == rep.ja_corretas, f"{c1.erradas} x {rep.corrigidas}")
c2 = ff.check_flags(b)
confere("depois do Fix, o Check não aponta nada", c2.erradas == 0 and c2.certas == c2.flags, f"{c2.erradas} para corrigir, {c2.certas} corretas")

# ---- Fontes ----
abre(os.path.join(sys.argv[2], "FONT_RICO.CATDrawing"))
a1 = fc.run_font_inspection(b, lambda *x: "A1", lambda *x: None)
confere("há itens fora do padrão para corrigir", a1.total_nok > 5, f"{a1.total_nok} de {a1.total_items}")
antes = {tuple(l.split(CAMPO)[:3]): l.split(CAMPO) for l in foto()}
primeiro = a1.items[0]
alvo = fc.closest_standard(primeiro)
novo = fc.fix_font_size(b, a1, primeiro, alvo)
confere("corrige um item para o padrão escolhido", abs(novo - alvo) <= fc.TOLERANCIA, f"{primeiro.text}: {novo}")
a2 = fc.run_font_inspection(b, lambda *x: "A1", lambda *x: None)
confere("o item corrigido sai da lista, e só ele", a2.total_nok == a1.total_nok - 1, f"{a1.total_nok} -> {a2.total_nok}")
outro = a2.items[0]
segundo = max(outro.padroes, key=lambda p: abs(p - outro.inches))
confere("aceita também o outro padrão da folha", abs(fc.fix_font_size(b, a2, outro, segundo) - segundo) <= fc.TOLERANCIA)
a3 = fc.run_font_inspection(b, lambda *x: "A1", lambda *x: None)
falharam = []
for item in a3.items:
    try:
        fc.fix_font_size(b, a3, item, fc.closest_standard(item))
    except Exception as exc:  # o teste lista o que falhou
        falharam.append((item.text, str(exc)))
confere("corrige todos os pendentes", not falharam, falharam[:3])
a4 = fc.run_font_inspection(b, lambda *x: "A1", lambda *x: None)
confere("depois de corrigir tudo, o Check não aponta nada", a4.total_nok == 0, f"{a4.total_nok} fora do padrão, {a4.total_ok} corretos")
depois = {tuple(l.split(CAMPO)[:3]): l.split(CAMPO) for l in foto()}
# Foto: 0 folha, 1 vista, 2 nome, 3 texto, 4 frame, 5 frame props, 6 cor, 7 cores, 8 bordas, 9-10 tamanho, 11 x, 12 y, 13..
so_tamanho = all(antes[k][:9] == depois[k][:9] and antes[k][11:] == depois[k][11:] for k in antes)
confere("muda só o tamanho: texto, cor, posição e leaders iguais", so_tamanho and antes.keys() == depois.keys())
travada = [v for k, v in depois.items() if k[1] in ("V travada", "V escondida")]
confere("vistas travadas e ocultas não mudam", all(depois[k][9] == antes[k][9] for k in depois if k[1] in ("V travada", "V escondida")) and bool(travada))

while app.Documents.Count:
    app.Documents.Item(1).Close()
print("RESULTADO:", "TUDO CERTO" if not falhas else f"{len(falhas)} FALHAS: {falhas}", flush=True)
sys.stdout.flush()
os._exit(1 if falhas else 0)
