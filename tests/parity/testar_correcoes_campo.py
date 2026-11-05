"""Testa o que apareceu no primeiro uso em desenho real, no PC da empresa.

- Template: converter um desenho e, com ele aberto, converter outro do mesmo formato.
- Font: texto oculto nao entra na lista.
- HUB: as consultas repetidas nao falam com o CATIA enquanto nada muda.

Uso (com o CATIA aberto e sem desenhos importantes abertos, porque fecha todos):
    python tests/parity/testar_correcoes_campo.py <pasta paridade_update_*> <pasta com FONT_RICO.CATDrawing>
"""
import os
import shutil
import sys
import tempfile

import pywintypes

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.join(AQUI, "..", "..", "src"))

from engine import atualizar_template as at  # noqa: E402
from engine import font_check as fc  # noqa: E402
from engine.catia_bridge import CatiaBridge, titulo_janela_catia  # noqa: E402
from ui_qt.catia_worker import CatiaWorker  # noqa: E402

P_UPDATE, P_FONT = sys.argv[1:3]
MODELOS = os.path.join(P_UPDATE, "templates")
falhas = []


def confere(nome, ok, extra=""):
    print(f"[{'OK' if ok else 'FALHOU'}] {nome}{' ' + str(extra) if extra != '' else ''}", flush=True)
    if not ok:
        falhas.append(nome)


b = CatiaBridge()
app = b.app
T = tempfile.mkdtemp(prefix="campo_")


def copia(origem, nome):
    destino = os.path.join(T, nome)
    shutil.copy(origem, destino)
    return destino


def fechar_tudo():
    # Pelas janelas: o template carregado sem janela nao fecha com Close. Sai junto com os desenhos.
    app.DisplayFileAlerts = False
    while app.Windows.Count:
        app.Windows.Item(1).Parent.Close()
    app.DisplayFileAlerts = True


def nomes():
    return [app.Documents.Item(i).Name for i in range(1, app.Documents.Count + 1)]


def foto():
    return app.SystemService.ExecuteScript(AQUI, 1, "sonda_update.catvbs", "Foto", [])


def so_o_desenho(texto, nome):
    """A foto cita o nome do arquivo e os documentos abertos, que aqui mudam de proposito."""
    return [l.replace(nome, "DESENHO") for l in texto.split(chr(30)) if not l.startswith("ABERTOS")]


def converte():
    return at.run_update_template(b, lambda *a: "A1", pasta=MODELOS)


# ---------------- Template no 2o desenho do mesmo formato ----------------
RICO = os.path.join(P_UPDATE, "UPD_RICO.CATDrawing")
fechar_tudo()
app.Documents.Open(copia(RICO, "SOZINHO.CATDrawing"))
converte()
sozinho = so_o_desenho(foto(), "SOZINHO.CATDrawing")
modelo_a1 = os.path.join(MODELOS, "E1_DRAWING TEMPLATE_SHEET A1_CATIAV5R32_REV01.CATDrawing")

fechar_tudo()
app.Documents.Open(copia(RICO, "PRIMEIRO.CATDrawing"))
converte()
ficou = [n for n in nomes() if "TEMPLATE_SHEET" in n]
confere("reproduz: o template fica carregado depois de converter", len(ficou) == 2, ficou)
confere("mas sem janela", all("TEMPLATE_SHEET" not in app.Windows.Item(i).Name for i in range(1, app.Windows.Count + 1)))
app.Documents.Open(copia(RICO, "SEGUNDO.CATDrawing"))
try:
    r = converte()
    confere("o segundo desenho do mesmo formato converte", r is not None, r.sheets if r else "")
except at.TemplateError as exc:
    confere("o segundo desenho do mesmo formato converte", False, exc)
confere("o ativo continua sendo o segundo", app.ActiveDocument.Name == "SEGUNDO.CATDrawing", app.ActiveDocument.Name)
segundo = so_o_desenho(foto(), "SEGUNDO.CATDrawing")
difs = [(x, y) for x, y in zip(sozinho, segundo) if x != y]
confere("o resultado é igual ao de um desenho convertido sozinho", not difs and len(sozinho) == len(segundo), f"{len(sozinho)} linhas" if not difs else difs[:4])
confere("o template continua sem janela", all("TEMPLATE_SHEET" not in app.Windows.Item(i).Name for i in range(1, app.Windows.Count + 1)))
confere("a tela do CATIA fica ligada", bool(app.RefreshDisplay) and bool(app.Interactive) and bool(app.DisplayFileAlerts))
# Um terceiro, para garantir que nao acumula nada.
app.Documents.Open(copia(RICO, "TERCEIRO.CATDrawing"))
try:
    confere("e um terceiro também", converte() is not None)
except at.TemplateError as exc:
    confere("e um terceiro também", False, exc)

# Aberto pela pessoa, com janela, continua recusado: pode ter alteracoes. E o desenho nao foi tocado.
fechar_tudo()
app.Documents.Open(modelo_a1)
app.Documents.Open(copia(RICO, "COM_JANELA.CATDrawing"))
antes = foto()
try:
    converte()
    confere("template aberto pela pessoa é recusado", False)
except at.TemplateError as exc:
    confere("template aberto pela pessoa é recusado", "já está aberto" in exc.mensagem)
    confere("sem dizer que o desenho pode ter mudado, porque não mudou", not exc.modified and "parcialmente" not in exc.mensagem, exc.mensagem[-120:])
confere("e o desenho fica igual", antes == foto())
confere("a tela do CATIA fica ligada depois do erro", bool(app.RefreshDisplay) and bool(app.Interactive) and bool(app.DisplayFileAlerts))


# Um passo que falha ao fechar nao pode impedir os outros, como na macro.
class Falha:
    def __call__(self):
        raise pywintypes.com_error(-1, "falha", None, None)


class Modelo:
    Selection = type("S", (), {"Clear": Falha()})()
    fechou = False

    def Close(self):
        Modelo.fechou = True


class Desenho:
    ativou = False

    def Activate(self):
        Desenho.ativou = True


c = at._Conversao(b, None, None)
c.doc = Desenho()
c.fechar_template(Modelo())
confere("fecha o template mesmo se limpar a seleção falhar", Modelo.fechou and Desenho.ativou)

# ---------------- Font: texto oculto ----------------
fechar_tudo()
doc = app.Documents.Open(copia(os.path.join(P_FONT, "FONT_RICO.CATDrawing"), "FONT_OCULTO.CATDrawing"))
ANALISA = dict(ask_format=lambda *a: "A1", warn=lambda *a: None)
r1 = fc.run_font_inspection(b, **ANALISA)
confere("sem nada oculto, não cita ocultos", r1.total_hidden == 0 and "cultos" not in r1.mensagem)
alvos = [i for i in r1.items if not i.is_dim][:2]
confere("tem textos fora do padrão para o teste", len(alvos) == 2, [a.text for a in alvos])
sel = doc.Selection
for a in alvos:
    v = next(doc.Sheets.Item(i) for i in range(1, doc.Sheets.Count + 1) if doc.Sheets.Item(i).Name == a.sheet_name).Views.Item(a.view_index)
    sel.Clear()
    sel.Add(v.Texts.Item(a.item_index))
    sel.VisProperties.SetShow(1)
sel.Clear()
r2 = fc.run_font_inspection(b, **ANALISA)
confere("texto oculto sai da lista", r2.total_nok == r1.total_nok - 2 and not any((i.sheet_name, i.view_index, i.item_index) == (a.sheet_name, a.view_index, a.item_index) for i in r2.items for a in alvos), f"{r1.total_nok} -> {r2.total_nok}")
confere("e do total, com aviso", r2.total_items == r1.total_items - 2 and r2.total_hidden == 2 and "2 ocultos ignorados" in r2.resumo, r2.resumo.replace("\r\n", " | "))
confere("o resto continua igual", r2.total_ok == r1.total_ok)
confere("a seleção fica vazia", sel.Count == 0)

# ---------------- HUB nao insiste no CATIA ----------------
titulo = titulo_janela_catia()
confere("lê o título do CATIA sem falar com ele", titulo == "CATIA V5 - [FONT_OCULTO.CATDrawing]", titulo)
w = CatiaWorker()
chamadas = []
poll_real = w.poll
w.poll = lambda: (chamadas.append(1), poll_real())
w.poll_leve()
confere("na primeira vez, pergunta ao CATIA", len(chamadas) == 1)
for _ in range(5):
    w.poll_leve()
confere("com o mesmo título, não pergunta de novo", len(chamadas) == 1, len(chamadas))
app.Documents.Open(copia(os.path.join(P_UPDATE, "UPD_PAPEL_USUARIO.CATDrawing"), "OUTRO.CATDrawing"))
w.poll_leve()
confere("com outro desenho, pergunta", len(chamadas) == 2, titulo_janela_catia())
fechar_tudo()
w.poll_leve()
confere("sem desenho, pergunta uma vez", len(chamadas) == 3, titulo_janela_catia())
w.janela_ativa = False
for _ in range(3):
    w.poll_leve()
confere("sem desenho e fora do HUB, não insiste", len(chamadas) == 3, len(chamadas))
w.janela_ativa = True
w.poll_leve()
confere("voltando ao HUB, pergunta", len(chamadas) == 4, len(chamadas))

fechar_tudo()
print("RESULTADO:", "TUDO CERTO" if not falhas else f"{len(falhas)} FALHAS: {falhas}", flush=True)
sys.stdout.flush()
os._exit(1 if falhas else 0)
