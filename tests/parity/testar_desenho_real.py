"""Roda as ferramentas em desenhos que imitam os reais (fotos de 171-54070-801 e 190-40115-403).

A0 com 3 folhas: 9 colunas por folha, numeradas 9 a 1 da esquerda para a direita, linhas F a A de cima
para baixo. A1 com 1 folha: 6 colunas, linhas D a A. Baloes com flag ao lado, numeros sublinhados,
vistas travadas, grade de zonas antiga com o nome real (ZONE A0, ZONES_A0_SHT1).

O desenho comeca como sai de um template antigo (margem 1 a 9 em todas as folhas) e passa por:
Pos e Zone, Update Template, Pos e Zone de novo, Fix Flags, Font Size e Split 2D.

Uso (com o CATIA aberto e sem desenhos importantes abertos, porque fecha todos):
    python tests/parity/testar_desenho_real.py
"""
import os
import sys
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "..", "src"))

import win32com.client as com  # noqa: E402

from engine import atualizar_template as at  # noqa: E402
from engine import fix_flags as ff  # noqa: E402
from engine import font_check as fc  # noqa: E402
from engine import pos_zone as pz  # noqa: E402
from engine import splits as sp  # noqa: E402
from engine.catia_bridge import CatiaBridge  # noqa: E402

CIRCULO, FLAG_ESQ, BORDA = 3, 8, 12
falhas = []
trabalho = tempfile.mkdtemp(prefix="desenho_real_")
os.environ["E1DWGTOOLS_TEMPLATES"] = os.path.join(trabalho, "templates_lidos.json")
os.environ["E1DWGTOOLS_TEMPOS"] = os.path.join(trabalho, "update_tempos.txt")
modelos = os.path.join(trabalho, "templates")
os.mkdir(modelos)

app = com.GetActiveObject("CATIA.Application")
app.DisplayFileAlerts = False


def confere(nome, ok, extra=""):
    print(f"[{'OK' if ok else 'FALHOU'}] {nome}{' ' + str(extra) if extra != '' else ''}", flush=True)
    if not ok:
        falhas.append(nome)


def fechar_tudo():
    while app.Documents.Count:
        app.Documents.Item(1).Close()


class Papel:
    def __init__(self, formato, codigo, largura, altura, colunas, letras):
        self.formato, self.codigo, self.w, self.h, self.colunas, self.letras = formato, codigo, largura, altura, colunas, letras

    def cx(self, coluna):  # a coluna 1 fica na direita
        return self.w - (coluna - 0.5) * self.w / self.colunas

    def cy(self, letra):  # a linha A fica embaixo
        return (self.letras.index(letra) + 0.5) * self.h / len(self.letras)

    def ponto(self, zona):
        return self.cx(int(zona[1:])), self.cy(zona[0])


A0 = Papel("A0", 2, 1189.0, 841.0, 9, "ABCDEF")
A1 = Papel("A1", 3, 841.0, 594.0, 6, "ABCD")


def margem(bg, papel, primeira, numero_da_folha=""):
    """Numeros em cima e embaixo, letras nos lados, formato e numero da folha na legenda."""
    for k in range(1, papel.colunas + 1):
        for y in (5.0, papel.h - 5.0):
            bg.Texts.Add(str(primeira - 1 + k), papel.cx(k), y)
    for letra in papel.letras:
        for x in (5.0, papel.w - 5.0):
            bg.Texts.Add(letra, x, papel.cy(letra))
    t = bg.Texts.Add(papel.formato, papel.w - 12.0, 9.0)
    t.Name = "Text.68"
    bg.Texts.Add("SHEET / OF", papel.w - 40.0, 30.0)
    if numero_da_folha:
        bg.Texts.Add(numero_da_folha, papel.w - 40.0, 22.0)
    bg.Texts.Add("SCALE", papel.w - 160.0, 30.0)
    bg.Texts.Add("1:4", papel.w - 160.0, 22.0)


def folha_nova(doc, indice, papel):
    sh = doc.Sheets.Item(1) if indice == 1 else doc.Sheets.Add(f"Sheet.{indice}")
    sh.PaperSize = papel.codigo
    sh.Orientation = 1
    sh.Activate()
    return sh


def vista(sh, nome, x, y, escala):
    v = sh.Views.Add(nome)
    v.x, v.y, v.Scale = x, y, escala
    v.Activate()
    return v


def texto(v, s, sx, sy, mm=5.0):
    """sx, sy: posicao na folha. A vista tem origem e escala proprias, como no desenho real."""
    t = v.Texts.Add(s, (sx - v.x) / v.Scale, (sy - v.y) / v.Scale)
    t.SetFontSize(0, 0, mm)
    t.AnchorPosition = 5
    return t


def balao(v, s, sx, sy):
    t = texto(v, s, sx, sy)
    p = t.TextProperties
    p.FrameType = CIRCULO
    p.Update()
    return t


def sublinhado(v, s, sx, sy):
    t = texto(v, s, sx, sy)
    p = t.TextProperties
    p.Underline = 1
    p.Update()
    return t


def flag(v, s, sx, sy, pelo_editor=True):
    t = texto(v, s, sx, sy)
    if pelo_editor:
        t.SetParameterOnSubString(BORDA, 1, len(s), FLAG_ESQ)
    else:
        p = t.TextProperties
        p.FrameType = FLAG_ESQ
        p.Update()
    return t


def grade_antiga(sh):
    for nome in ("ZONE A0", "ZONES_A0_SHT1"):
        v = vista(sh, nome, 0, 0, 1)
        v.Texts.Add("GRADE VELHA", 300, 300)
        v.LockStatus = True


def salvar(doc, nome):
    caminho = os.path.join(trabalho, nome)
    doc.SaveAs(caminho)
    return caminho


def ler_zonas():
    rep = pz.analisar_desenho(CatiaBridge(), lambda m, t: print("    aviso:", m.replace("\r\n", " | ")))
    return {c.number: (c.zone, c.qty) for c in rep.callouts}


def confere_zonas(nome, lidas, esperadas):
    errados = {n: (lidas.get(n), z) for n, z in esperadas.items() if lidas.get(n, ("", 0))[0] != z}
    confere(nome, not errados, errados if errados else f"{len(esperadas)} posições")


# ---------------------------------------------------------------------
# Template A0, como o da empresa: margem 9 a 1 e grade de zonas com o formato no nome
# ---------------------------------------------------------------------
fechar_tudo()
doc = app.Documents.Add("Drawing")
sh = folha_nova(doc, 1, A0)
bg = sh.Views.Item(2)
bg.Activate()
margem(bg, A0, 1, "1 / 1")
v = vista(sh, "ZONE A0", 0, 0, 1)
for letra in A0.letras:
    for k in range(1, A0.colunas + 1):
        v.Texts.Add(f"{letra}{k:03d}", A0.cx(k), A0.cy(letra))
v.LockStatus = True
v = vista(sh, "ZONES_A0_SHT1", 0, 0, 1)
for k in (6, 7, 8):
    v.Texts.Add(f"F{k}", A0.cx(k), A0.cy("F") + 30)
v.LockStatus = True
sh.Views.Item(1).Activate()
doc.SaveAs(os.path.join(modelos, "E1_DRAWING TEMPLATE_SHEET A0_CATIAV5R32_REV01.CATDrawing"))
doc.Close()

# ---------------------------------------------------------------------
# Desenho A0 de 3 folhas, ainda com o template antigo: margem 1 a 9 em todas as folhas
# ---------------------------------------------------------------------
doc = app.Documents.Add("Drawing")
ESPERADO = {}

sh = folha_nova(doc, 1, A0)
sh.Views.Item(2).Activate()
margem(sh.Views.Item(2), A0, 1, "1 / 3")
mv = sh.Views.Item(1)
mv.Activate()
nota = mv.Texts.Add("SEQUENCE OF INSTALLATION: NOTA NA MAIN VIEW", 150, 120)
nota.SetFontSize(0, 0, 3.0)
v = vista(sh, "1E2", 400, 500, 0.5)
for numero, zona in (("8", "E006"), ("9", "F006"), ("10", "E005"), ("11", "F005")):
    x, y = A0.ponto(zona)
    balao(v, numero, x, y)
    flag(v, "NL003", x + 22, y, pelo_editor=(numero != "9"))
    ESPERADO[numero] = zona
justa = flag(v, "NI865", *A0.ponto("D005"))
justa.WrappingWidth = 0  # largura justa: o codigo cresce e nao pode partir em duas linhas
texto(v, "GROUND JUMPER REF", *A0.ponto("D006"))
grade_antiga(sh)

sh = folha_nova(doc, 2, A0)
sh.Views.Item(2).Activate()
margem(sh.Views.Item(2), A0, 1, "2")
v = vista(sh, "1F22", 100, 100, 1)
x, y = A0.ponto("F008")
balao(v, "2", x, y)
flag(v, "NL003", x + 22, y)
x, y = A0.ponto("C003")
balao(v, "2", x, y)
x, y = A0.ponto("D006")
balao(v, "7", x, y)
x, y = A0.ponto("C007")
sublinhado(v, "7", x, y)  # sublinhado so conta quantidade: nao da zona
flag(v, "NL003", x + 22, y)
texto(v, "7 REF", *A0.ponto("B007"))
texto(v, "P/N 170-90166-403 FORA DO PADRAO", *A0.ponto("E008"), mm=3.0)
v.LockStatus = True  # como no desenho real: vistas travadas
ESPERADO["2"] = "F028; C023"
ESPERADO["7"] = "D026"
grade_antiga(sh)

sh = folha_nova(doc, 3, A0)
sh.Views.Item(2).Activate()
margem(sh.Views.Item(2), A0, 1, "3")
v = vista(sh, "VIEW LOOKING AFT", 0, 0, 1)
x, y = A0.ponto("B003")
for i, numero in enumerate(("3", "4", "5", "30")):
    balao(v, numero, x, y + 30 - 14 * i)
    ESPERADO[numero] = "B033"
flag(v, "NI012", x + 22, y + 30)
flag(v, "NL005", x + 22, y - 12)
x, y = A0.ponto("E005")
balao(v, "6", x, y)
flag(v, "NL006", x + 22, y, pelo_editor=False)
balao(v, "31", x, y - 40)
ESPERADO["6"] = "E035"
ESPERADO["31"] = "E035"
v.LockStatus = True
grade_antiga(sh)
doc.Sheets.Item(1).Activate()
caminho_a0 = salvar(doc, "171-54070-801.CATDrawing")

print("\n== A0 de 3 folhas, template antigo (margem 1 a 9 em todas as folhas)")
antes = ler_zonas()
confere_zonas("zona de cada balão, com a dezena da folha", antes, ESPERADO)
confere("sublinhado conta quantidade e não dá zona", antes.get("7") == ("D026", 2), antes.get("7"))
confere("flag ao lado do balão não vira callout", not [n for n in antes if n.startswith("N")], sorted(antes))

print("\n== Update Template")
vistas_antes = {sh.Name: [(sh.Views.Item(j).Name, bool(sh.Views.Item(j).LockStatus)) for j in range(3, sh.Views.Count + 1)]
                for sh in (doc.Sheets.Item(i) for i in range(1, 4))}
rep = at.run_update_template(CatiaBridge(), lambda *a: "A0", pasta=modelos + "\\")
print("    avisos:", rep.warnings)
confere("sem aviso de margem não encontrada", not [w for w in rep.warnings if "margem" in w.lower()], rep.warnings)
for i, primeira in ((1, 1), (2, 21), (3, 31)):
    sh = doc.Sheets.Item(i)
    bg = sh.Views.Item(2)
    numeros = []
    for k in range(1, bg.Texts.Count + 1):
        t = bg.Texts.Item(k)
        if str(t.Text).isdigit() and (t.y < 10 or t.y > A0.h - 10):
            numeros.append((round(t.x), round(t.y), int(t.Text)))
    baixo = [n for x, y, n in sorted(numeros) if y < 10]
    cima = [n for x, y, n in sorted(numeros) if y > 10]
    certo = list(range(primeira + 8, primeira - 1, -1))
    confere(f"folha {i}: margem {certo[0]} a {certo[-1]}, da esquerda para a direita, em cima e embaixo",
            baixo == certo and cima == certo, (baixo, cima))
    nomes = [str(sh.Views.Item(j).Name) for j in range(3, sh.Views.Count + 1)]
    textos_grade = [str(sh.Views.Item(j).Texts.Item(k).Text) for j in range(3, sh.Views.Count + 1)
                    if at.is_aux_view(str(sh.Views.Item(j).Name)) for k in range(1, sh.Views.Item(j).Texts.Count + 1)]
    confere(f"folha {i}: grade velha apagada e uma só grade nova", "GRADE VELHA" not in textos_grade
            and sum(1 for n in nomes if at.is_aux_view(n)) == 2, nomes)
    rotulo = f"E{at.numero_na_folha(5, i):03d}"
    curto = f"F{at.numero_na_folha(6, i)}"
    confere(f"folha {i}: grade com {rotulo} e {curto}", rotulo in textos_grade and curto in textos_grade
            and (i == 1 or ("E005" not in textos_grade and "F6" not in textos_grade)))
    do_usuario = [(n, t) for n, t in vistas_antes[sh.Name] if not at.is_aux_view(n)]
    agora = [(str(sh.Views.Item(j).Name), bool(sh.Views.Item(j).LockStatus)) for j in range(3, sh.Views.Count + 1)]
    confere(f"folha {i}: vistas do desenho intactas e com a mesma trava", all(v in agora for v in do_usuario), agora)

print("\n== Pos e Zone depois do Update (margem já com a dezena: 21 a 29, 31 a 39)")
depois = ler_zonas()
confere_zonas("mesma zona de antes, sem somar a dezena duas vezes", depois, ESPERADO)
confere("mesmas quantidades de antes", {n: q for n, (z, q) in depois.items()} == {n: q for n, (z, q) in antes.items()})

print("\n== Fix Flags")


def flags_do_desenho():
    saida = []
    for i in range(1, 4):
        sh = doc.Sheets.Item(i)
        for j in range(3, sh.Views.Count + 1):
            v = sh.Views.Item(j)
            if at.is_aux_view(str(v.Name)):
                continue
            for k in range(1, v.Texts.Count + 1):
                t = v.Texts.Item(k)
                s = str(t.Text)
                if s[:2] in ("NL", "NI") and s[2:].isdigit():
                    saida.append((sh.Name, str(v.Name), s, t.TextProperties.Color))
    return saida


f_antes = flags_do_desenho()
largura_antes = justa.WrappingWidth
rep = ff.run_fix_flags(CatiaBridge(), lambda m, t: True, lambda m, t: None)
f_depois = flags_do_desenho()
print("   ", rep.mensagem.replace("\r\n", " | ")[:260])
confere("todas as flags com 4 números, também nas vistas travadas", all(len(s) == 6 for _, _, s, _ in f_depois),
        [(f, v, s) for f, v, s, _ in f_depois if len(s) != 6])
confere("nenhuma flag foi pintada", [c for *_, c in f_antes] == [c for *_, c in f_depois])
confere("flag com largura justa não parte em duas linhas", justa.WrappingWidth > largura_antes and str(justa.Text) == "NI0865",
        (round(largura_antes, 1), round(justa.WrappingWidth, 1)))
confere("vistas continuam travadas", bool(doc.Sheets.Item(2).Views.Item(3).LockStatus) and bool(doc.Sheets.Item(3).Views.Item(3).LockStatus))
com_flags = ler_zonas()
confere("Pos e Zone igual depois do Fix Flags", com_flags == depois, {n: (com_flags.get(n), depois.get(n)) for n in depois if com_flags.get(n) != depois.get(n)})

print("\n== Font Size")
rep = fc.run_font_inspection(CatiaBridge(), lambda *a: "A0", lambda *a: None)
fora = [(i.sheet_name, i.view_name, i.text[:30]) for i in rep.items]
confere("acha o texto fora do padrão na vista travada", any(v == "1F22" and "170-90166" in t for _, v, t in fora), fora)
confere("não lista a Main View nem o Background", not [f for f in fora if f[1] in ("Main View", "Background View")], fora)
confere("não lista a grade de zonas do template", not [f for f in fora if at.is_aux_view(f[1])], [f for f in fora if at.is_aux_view(f[1])][:3])
confere("lista só o que está fora do padrão no desenho", len(fora) == 1, fora)
item = next(i for i in rep.items if i.view_name == "1F22")
novo = fc.fix_font_size(CatiaBridge(), rep, item, fc.closest_standard(item))
confere("corrige na vista travada e tranca de volta", abs(novo - fc.closest_standard(item)) <= fc.TOLERANCIA
        and bool(doc.Sheets.Item(2).Views.Item(3).LockStatus), novo)

print("\n== Split 2D")
doc.Save()
baixar = os.path.join(trabalho, "downloads")
os.mkdir(baixar)
rep = sp.run_split_2d(CatiaBridge(), lambda m: print("    aviso:", m), lambda m: print("    info:", m), downloads=baixar)
pasta = rep.folder if hasattr(rep, "folder") else os.path.join(baixar, "171-54070-801")
arquivos = sorted(os.listdir(os.path.join(baixar, os.listdir(baixar)[0])))
confere("um arquivo por folha", len(arquivos) == 3, arquivos)
fechar_tudo()
soltas = []
for nome in arquivos:
    d = app.Documents.Open(os.path.join(baixar, os.listdir(baixar)[0], nome))
    if d.Sheets.Count != 1:
        soltas.append((nome, "folhas", d.Sheets.Count))
    sh = d.Sheets.Item(1)
    for j in range(1, sh.Views.Count + 1):
        v = sh.Views.Item(j)
        if str(v.Name) != "Background View" and not v.LockStatus:
            soltas.append((nome, str(v.Name)))
    d.Close()
confere("todas as vistas dos arquivos exportados estão travadas", not soltas, soltas)

# ---------------------------------------------------------------------
# A1 de 1 folha: 6 colunas e linhas A a D
# ---------------------------------------------------------------------
print("\n== A1 de 1 folha (6 colunas, linhas A a D)")
doc = app.Documents.Add("Drawing")
sh = folha_nova(doc, 1, A1)
sh.Views.Item(2).Activate()
margem(sh.Views.Item(2), A1, 1, "1 / 1")
v = vista(sh, "TAPE PATTERN", 200, 300, 0.125)
x, y = A1.ponto("C003")
balao(v, "6", x, y)
flag(v, "NL0001", x + 22, y)
flag(v, "NL0003", x + 46, y)
sublinhado(v, "6", *A1.ponto("D003"))
sublinhado(v, "6", *A1.ponto("C005"))
v = vista(sh, "1B6", 600, 150, 1)
x, y = A1.ponto("B002")
balao(v, "4", x, y)
balao(v, "5", x, y - 14)
flag(v, "NI1008", x - 30, y)
texto(v, "TRIM TO FIT", x - 20, y - 30)
balao(v, "3", *A1.ponto("B001"))
balao(v, "2", *A1.ponto("A001"))
texto(v, "4\n5\nREF", *A1.ponto("B003"))
salvar(doc, "190-40115-403.CATDrawing")
lidas = ler_zonas()
confere_zonas("zona de cada balão no A1", lidas, {"6": "C003", "4": "B002", "5": "B002", "3": "B001", "2": "A001"})
confere("balão 6 com dois sublinhados: quantidade 3, zona só do balão", lidas.get("6") == ("C003", 3), lidas.get("6"))
rep = ff.run_fix_flags(CatiaBridge(), lambda m, t: True, lambda m, t: None)
confere("flags já com 4 números não são tocadas", rep is None or rep.corrigidas == 0, getattr(rep, "corrigidas", None))
fechar_tudo()

print("\nPasta do teste:", trabalho)
print("RESULTADO:", "TUDO CERTO" if not falhas else f"{len(falhas)} FALHAS: {falhas}", flush=True)
sys.exit(1 if falhas else 0)
