"""Le um template real e grava como a legenda dele e montada. Nao altera nem salva o template.

Feito em 18/11/2026 para descobrir por que o A1 converte com "1 XX" no SHEET/OF e continua ligado ao
template: em casa, templates montados com o campo "1/XX" de tres jeitos convertem certo.

Grava em %APPDATA%\\E1DWGTools\\sonda_template_<formato>.txt:
- parametros do template (nome, tipo, valor) e se aceitam o marcador da leitura dos vinculos;
- todos os textos do Background da folha 1 (nome, texto, x, y);
- o que a conversao leu: textos ligados a cada parametro e qual texto ela acha que e o SHEET/OF;
- views da folha 1 e quantos dittos (componentes 2D) e tabelas cada uma tem.

Uso, com o CATIA aberto e o template FECHADO:
    python tests\\parity\\sonda_template_real.py A1
"""
from __future__ import annotations

import os
import sys

import pythoncom

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "..", "src"))

from engine import atualizar_template as at  # noqa: E402
from engine.catia_bridge import CatiaBridge  # noqa: E402


def tipo(objeto) -> str:
    try:
        return objeto._oleobj_.GetTypeInfo().GetDocumentation(-1)[0]
    except Exception:  # noqa: BLE001 - so diagnostico
        return "?"


def main() -> int:
    formato = (sys.argv[1] if len(sys.argv) > 1 else "A1").upper()
    pasta = sys.argv[2] if len(sys.argv) > 2 else at.PASTA_TEMPLATES
    destino = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "E1DWGTools", f"sonda_template_{formato}.txt")
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    linhas = []
    pythoncom.CoInitialize()
    app = CatiaBridge().app
    caminho = at.find_template(pasta, formato)
    linhas.append(f"Template: {caminho or '(nao encontrado em ' + pasta + ')'}")
    if not caminho:
        return gravar(destino, linhas)
    app.DisplayFileAlerts = False
    modelo = app.Documents.Open(caminho)
    try:
        folha = at.drawing_sheets(modelo)[0]
        fundo = folha.Views.Item(2)
        linhas.append(f"Folha 1: {folha.Name}  papel {folha.GetPaperWidth()} x {folha.GetPaperHeight()}")

        linhas.append("\n== PARAMETROS (nome | tipo | valor)")
        ps = modelo.Parameters
        for i in range(1, ps.Count + 1):
            p = ps.Item(i)
            try:
                valor = p.ValueAsString()
            except Exception as exc:  # noqa: BLE001
                valor = f"ERRO {exc}"
            linhas.append(f"{p.Name} | {tipo(p)} | {valor!r}")

        linhas.append("\n== VIEWS DA FOLHA 1 (nome | textos | dittos | tabelas)")
        for i in range(1, folha.Views.Count + 1):
            v = folha.Views.Item(i)
            cont = []
            for nome in ("Texts", "Components", "Tables"):
                try:
                    cont.append(str(getattr(v, nome).Count))
                except Exception:  # noqa: BLE001
                    cont.append("?")
            linhas.append(f"{v.Name} | " + " | ".join(cont))

        linhas.append("\n== TEXTOS DO BACKGROUND (nome | texto | x | y)")
        ts = fundo.Texts
        for i in range(1, ts.Count + 1):
            t = ts.Item(i)
            linhas.append(f"{t.Name} | {str(t.Text)!r} | {t.x:.2f} | {t.y:.2f}")

        linhas.append("\n== O QUE A CONVERSAO LE (vinculos: texto -> parametros)")
        links = at.map_text_links(modelo.Parameters, fundo)
        for chave, l in links.items():
            linhas.append(f"{chave} | {l.template_text!r} | {l.parametros} | {l.x:.2f} | {l.y:.2f}")
        chave = at.link_key_for_parameter(links, at.SHEET_COUNT_PARAMETER)
        linhas.append(f"\nTexto ligado a {at.SHEET_COUNT_PARAMETER}: {chave or '(nenhum)'}")
        if not chave:
            chave = at.sheet_field_without_link(fundo, folha.GetPaperWidth(), links)
            linhas.append(f"Campo SHEET/OF escolhido pela posicao: {chave or '(NENHUM - a folha 1 fica com XX)'}")
        if chave:
            l = links[chave]
            linhas.append(f"  vira: {l.template_text!r} com {l.parametros}; prefixos: {at.sheet_field_prefixes(fundo, l)}")
    finally:
        modelo.Close()  # sem salvar: os parametros ja voltaram ao valor original
        app.DisplayFileAlerts = True
    return gravar(destino, linhas)


def gravar(destino, linhas) -> int:
    with open(destino, "w", encoding="utf-8") as f:
        f.write("\n".join(linhas) + "\n")
    print("Gravado em", destino)
    return 0


if __name__ == "__main__":
    sys.exit(main())
