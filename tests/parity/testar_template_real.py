"""Roda o Update Template nos desenhos e templates de montar_template_real.catvbs e mostra o resultado.

Para cada variante do campo SHEET/OF do template A1 (v1, v2, v3) e cada desenho (1 e 3 folhas):
- avisos da conversao;
- o que fica no campo SHEET/OF de cada folha e o Text.1 da Main View;
- se o template continua carregado no CATIA depois de fechado (sinal de vinculo com ele);
- se os campos seguem os parametros do desenho: muda No_of_Sheets, Drawing_No, Thickness e Material_Code e le de novo;
- dittos (de qual documento vem o componente) e tabelas da folha 1;
- se o desenho convertido, salvo e reaberto sozinho, puxa o template junto (vinculo gravado no arquivo).
O desenho convertido e salvo como <desenho>_conv_v<n>.CATDrawing, para abrir e conferir.

Uso (fecha todos os documentos do CATIA):
    python tests/parity/testar_template_real.py <pasta de montar_template_real> [v1 v2 v3]
"""
from __future__ import annotations

import os
import sys
import tempfile

import pythoncom

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "..", "src"))

from engine import atualizar_template as at  # noqa: E402
from engine.catia_bridge import CatiaBridge  # noqa: E402

CAMPO_X = (790.0, 830.0)  # celula SHEET/OF da legenda
CAMPO_Y = (25.0, 45.0)


def fechar_tudo(app) -> None:
    """De tras para frente e com limite: um documento ainda ligado a outro nao sai da memoria no Close."""
    app.DisplayFileAlerts = False
    for _ in range(10):
        total = app.Documents.Count
        if not total:
            break
        for i in range(total, 0, -1):
            try:
                app.Documents.Item(i).Close()
            except Exception:  # noqa: BLE001
                pass
    app.DisplayFileAlerts = True


def textos(vista):
    ts = vista.Texts
    for i in range(1, ts.Count + 1):
        yield ts.Item(i)


def ler_folhas(doc) -> list:
    saida = []
    for i in range(1, doc.Sheets.Count + 1):
        sh = doc.Sheets.Item(i)
        bg = sh.Views.Item(2)
        campo = sorted(
            (round(t.x, 1), str(t.Text), str(t.Name))
            for t in textos(bg)
            if CAMPO_X[0] <= t.x <= CAMPO_X[1] and CAMPO_Y[0] <= t.y <= CAMPO_Y[1] and "/ OF" not in str(t.Text)
        )
        pn = [str(t.Text) for t in textos(bg) if abs(t.x - 740) < 0.01 and abs(t.y - 34) < 0.01]
        num = [str(t.Text) for t in textos(sh.Views.Item(1)) if str(t.Name) == "Text.1"]
        sobra = sorted({str(t.Text) for t in textos(bg) if "XX" in str(t.Text)})
        extra = sorted(str(t.Text) for t in textos(bg) if str(t.Text).startswith(("ESP ", "MAT ")))
        saida.append((str(sh.Name), campo, pn, num, sobra, extra, dittos(bg), tabelas(bg)))
    return saida


def dittos(bg) -> list:
    saida = []
    try:
        cs = bg.Components
        total = cs.Count
    except Exception:  # noqa: BLE001
        return ["(sem Components)"]
    for i in range(1, total + 1):
        c = cs.Item(i)
        try:
            ref = c.CompRef
            origem = f"{ref.Name} em {ref.Parent.Parent.Parent.Parent.Name}"
        except Exception as exc:  # noqa: BLE001
            origem = f"ref ilegivel ({exc})"
        saida.append(origem)
    return saida


def tabelas(bg) -> list:
    saida = []
    try:
        tb = bg.Tables
        total = tb.Count
    except Exception:  # noqa: BLE001
        return []
    for i in range(1, total + 1):
        t = tb.Item(i)
        try:
            saida.append(f"{t.GetCellString(1, 1)}={t.GetCellString(2, 1)}")
        except Exception as exc:  # noqa: BLE001
            saida.append(f"? ({exc})")
    return saida


def mostrar(rotulo, folhas) -> None:
    print(f"    {rotulo}:")
    for k, (nome, campo, pn, num, sobra, extra, dts, tbs) in enumerate(folhas):
        txt = " + ".join(f"{v!r} ({n})" for _x, v, n in campo) or "(vazio)"
        print(f"      {nome}: SHEET/OF = {txt}; Main View Text.1 = {num or '-'}; Nº desenho = {pn}; com XX: {sobra or '-'}")
        if k == 0 and (extra or dts or tbs):
            print(f"        textos ESP/MAT: {extra or '-'}; dittos: {dts or '-'}; tabelas: {tbs or '-'}")


def rodar(app, bridge, pasta, desenho, variante) -> None:
    fechar_tudo(app)
    caminho = os.path.join(pasta, desenho + ".CATDrawing")
    doc = app.Documents.Open(caminho)
    modelos = os.path.join(pasta, f"templates_{variante}")
    print(f"\n=== {desenho} com template {variante}")
    try:
        rep = at.run_update_template(bridge, lambda *a: "A1", pasta=modelos)
    except at.TemplateError as exc:
        print("    ERRO:", exc.mensagem.replace("\r\n", " | "))
        return
    for aviso in rep.warnings:  # inclui o aviso de desenho ainda ligado ao template
        print("    aviso:", aviso)
    if not rep.warnings:
        print("    (sem avisos)")
    doc = app.ActiveDocument
    abertos = [str(app.Documents.Item(i).Name) for i in range(1, app.Documents.Count + 1)]
    ligado = any("TEMPLATE" in n.upper() for n in abertos)
    print(f"    documentos carregados depois: {abertos}  -> {'AINDA LIGADO AO TEMPLATE' if ligado else 'sem template carregado'}")
    mostrar("depois da conversao", ler_folhas(doc))
    novos = {"No_of_Sheets": "7", "Drawing_No": "NOVO-PN", "Thickness": "7mm", "Material_Code": "ST"}
    velhos = {n: doc.Parameters.Item(n).ValueAsString() for n in novos}
    for n, v in novos.items():
        doc.Parameters.Item(n).ValuateFromString(v)
    doc.Update()
    mostrar("depois de mudar No_of_Sheets=7, Drawing_No=NOVO-PN, Thickness=7mm, Material_Code=ST", ler_folhas(doc))
    for n, v in velhos.items():
        doc.Parameters.Item(n).ValuateFromString(v)
    doc.Update()
    saida = os.path.join(pasta, f"{desenho}_conv_{variante}.CATDrawing")
    app.DisplayFileAlerts = False
    doc.SaveAs(saida)
    app.DisplayFileAlerts = True
    fechar_tudo(app)
    app.DisplayFileAlerts = False
    app.Documents.Open(saida)
    app.DisplayFileAlerts = True
    abertos = [str(app.Documents.Item(i).Name) for i in range(1, app.Documents.Count + 1)]
    ligado = any("TEMPLATE" in n.upper() for n in abertos)
    print(f"    reaberto sozinho, carrega: {abertos}  -> {'PUXA O TEMPLATE (vinculo no arquivo)' if ligado else 'nao puxa o template'}")


def main() -> int:
    pasta = sys.argv[1]
    variantes = [v for v in sys.argv[2:]] or [f"v{n}" for n in range(1, 8)]
    trabalho = tempfile.mkdtemp(prefix="template_real_")
    os.environ["E1DWGTOOLS_TEMPLATES"] = os.path.join(trabalho, "templates_lidos.json")
    os.environ["E1DWGTOOLS_TEMPOS"] = os.path.join(trabalho, "update_tempos.txt")
    pythoncom.CoInitialize()
    bridge = CatiaBridge()
    app = bridge.app
    for v in variantes:
        for desenho in ("TESTE_A1_1FOLHA", "TESTE_A1_3FOLHAS"):
            rodar(app, bridge, pasta, desenho, v)
    fechar_tudo(app)
    return 0


if __name__ == "__main__":
    sys.exit(main())
