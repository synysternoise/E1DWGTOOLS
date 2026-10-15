"""Metodo 1 de troca de template: swap do BACKGROUND (frame + etiqueta).

Trabalha NO proprio desenho (in-place): para cada folha, copia o conteudo do
Background do template e cola no Background do desenho, apagando o antigo. A
geometria/cotas/anotacoes do desenho ficam intactas. Folha 1 usa o background
da folha 1 do template; folha 2 em diante usa o da folha 2 (etiqueta de
continuacao). Os parametros do desenho (PN e infos linkadas) sao preservados,
entao os textos da etiqueta linkados por nome resolvem para os valores reais.

Reusa helpers de engine.update_template.
"""
from __future__ import annotations

import os
from typing import Optional

from engine.update_template import (
    SHEET_NUMBER_TEXT_NAME,  # noqa: F401  (documenta a intencao)
    TEMPLATE_FOLDER,
    TOTAL_SHEETS_PARAM,
    FormatResolver,
    ProgressCallback,
    StatusCallback,
    UpdateTemplateCancelled,
    UpdateTemplateError,
    _find_background_view,
    _update_sheet_numbers,
    find_template_by_format,
    get_format_from_background,
    get_running_catia,
    is_valid_template_format,
    normalize_template_format,
)


def _select_view_contents(selection, view) -> int:
    """Seleciona todo o conteudo (geometria + textos) de uma view. Retorna qtd."""
    count = 0
    try:
        geo = view.GeometricElements
        for i in range(1, geo.Count + 1):
            selection.Add(geo.Item(i))
            count += 1
    except Exception:
        pass
    try:
        texts = view.Texts
        for i in range(1, texts.Count + 1):
            selection.Add(texts.Item(i))
            count += 1
    except Exception:
        pass
    return count


def swap_template_background(
    progress_callback: Optional[ProgressCallback] = None,
    format_resolver: Optional[FormatResolver] = None,
    template_folder: str = TEMPLATE_FOLDER,
    status_callback: Optional[StatusCallback] = None,
) -> str:
    """Troca o template copiando o background do template para o desenho ativo."""
    def report(pct: int) -> None:
        if progress_callback:
            progress_callback(max(0, min(100, int(pct))))

    def say(msg: str, level: str = "info") -> None:
        if status_callback:
            status_callback(msg, level)

    report(0)
    say("Conectando ao CATIA...", "info")
    app_com = get_running_catia()
    source_doc = None
    template_doc = None

    try:
        if app_com.Documents.Count == 0:
            raise UpdateTemplateError(1001, "Nenhum documento aberto.")
        source_doc = app_com.ActiveDocument
        if not str(source_doc.Name).lower().endswith(".catdrawing"):
            raise UpdateTemplateError(1002, "O documento ativo nao e um CATDrawing.")
        source_sheets = source_doc.Sheets
        if source_sheets.Count == 0:
            raise UpdateTemplateError(1003, "O documento nao possui folhas.")
        say(f"Documento ativo: {source_doc.Name}", "ok")

        app_com.DisplayFileAlerts = False
        app_com.Interactive = False
        report(5)

        # --- formato --------------------------------------------------
        fmt = get_format_from_background(source_sheets.Item(1))
        if not is_valid_template_format(fmt):
            app_com.Interactive = True
            fmt = normalize_template_format(format_resolver() if format_resolver else "")
            if not fmt:
                raise UpdateTemplateCancelled()
            if not is_valid_template_format(fmt):
                raise UpdateTemplateError(
                    1004, f"Formato invalido: {fmt}. Use 3A0, A0, A1, A2, A3 ou E3.")
            app_com.Interactive = False
        fmt = normalize_template_format(fmt)
        say(f"Formato: {fmt}", "ok")
        report(10)

        # --- localiza e abre o template -------------------------------
        say(f"Procurando template na pasta: {template_folder}", "info")
        full_path = find_template_by_format(template_folder, fmt)
        if not full_path:
            raise UpdateTemplateError(
                1005, f"Template nao encontrado para o formato {fmt}.\n"
                      f"Pasta pesquisada:\n{template_folder}")
        template_name = os.path.basename(full_path)
        say(f"Template encontrado: {template_name}", "ok")

        template_doc = None
        for doc in app_com.Documents:
            if str(doc.Name).lower() == template_name.lower() and hasattr(doc, "Sheets"):
                template_doc = doc
                break
        if template_doc is None:
            template_doc = app_com.Documents.Open(full_path)
        if template_doc is None:
            raise UpdateTemplateError(1006, "Nao foi possivel abrir o template.")
        template_sheets = template_doc.Sheets
        say("Template aberto. Trocando o fundo das folhas...", "info")
        report(20)

        # --- swap do background folha a folha -------------------------
        n = source_sheets.Count
        for k in range(1, n + 1):
            # Folha 1 -> template folha 1; folha 2+ -> template folha 2 (etiqueta).
            t_index = 1 if k == 1 else min(2, template_sheets.Count)
            say(f"Folha {k}: aplicando fundo do template (folha {t_index})", "info")

            t_bg = _find_background_view(template_sheets.Item(t_index))
            s_bg = _find_background_view(source_sheets.Item(k))
            if t_bg is None or s_bg is None:
                say(f"  Background nao encontrado na folha {k} — pulando.", "warn")
                continue

            # 1) copia o conteudo do background do template
            template_doc.Activate()
            t_bg.Activate()
            t_sel = template_doc.Selection
            t_sel.Clear()
            copied = _select_view_contents(t_sel, t_bg)
            if copied == 0:
                say("  Fundo do template vazio — nada a copiar.", "warn")
                t_sel.Clear()
                continue
            t_sel.Copy()
            t_sel.Clear()

            # 2) apaga o fundo atual do desenho e cola o do template
            source_doc.Activate()
            s_bg.Activate()
            s_sel = source_doc.Selection
            s_sel.Clear()
            if _select_view_contents(s_sel, s_bg) > 0:
                s_sel.Delete()
            s_sel.Clear()
            s_bg.Activate()
            s_sel.Paste()
            s_sel.Clear()
            report(20 + int(60 * k / n))

        # --- numeracao das folhas e total -----------------------------
        say("Atualizando numeração das folhas e total...", "info")
        _update_sheet_numbers(source_sheets)
        try:
            source_doc.Parameters.Item(TOTAL_SHEETS_PARAM).ValuateFromString(
                str(source_sheets.Count))
        except Exception:
            pass
        report(92)

        source_doc.Update()
        say("Troca de template (background) concluída.", "ok")
        report(100)
        return fmt

    except UpdateTemplateCancelled:
        raise
    except Exception:
        try:
            app_com.Interactive = True
            app_com.DisplayFileAlerts = True
            if source_doc is not None:
                source_doc.Activate()
        except Exception:
            pass
        raise
    finally:
        # Fecha o template aberto (sem salvar; alertas desligados).
        try:
            if template_doc is not None:
                template_doc.Close()
        except Exception:
            pass
        try:
            app_com.Interactive = True
            app_com.DisplayFileAlerts = True
        except Exception:
            pass
