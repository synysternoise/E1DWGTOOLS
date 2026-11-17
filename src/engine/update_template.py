"""Conversao de CATDrawing para o novo template (porte de UPDATETEMPLATE.bas).

Sem interface grafica: interacao (formato manual, mensagens) e feita via
callbacks, para que a GUI possa ser plugada depois.
"""
from __future__ import annotations

import os
import time
from typing import Callable, Optional

from engine.documento import eh_desenho

ProgressCallback = Callable[[int], None]
FormatResolver = Callable[[], Optional[str]]
StatusCallback = Callable[[str, str], None]  # (mensagem, nivel)

TEMPLATE_FOLDER = r"\\nfscad05.sjk.emb\dmuv5\smarteam\b01\v5\DLNames\START_UP"
VALID_FORMATS = ("3A0", "A0", "A1", "A2", "A3", "E3")
FORMAT_TEXT_NAME = "Text.68"
SHEET_NUMBER_TEXT_NAME = "Text.75"
TOTAL_SHEETS_PARAM = "No_of_Sheets"
TEMPLATE_PREFIX = "E1_DRAWING TEMPLATE_SHEET {fmt}_CATIAV5R32"


def get_running_catia():
    """Conecta a uma instancia de CATIA JA aberta (nao inicia o CATIA).

    Usa GetActiveObject de proposito: Dispatch iniciaria o CATIA, o que
    atrapalharia a deteccao de 'CATIA aberto ou nao'. Levanta se nao houver.
    """
    import win32com.client
    return win32com.client.GetActiveObject("CATIA.Application")


class UpdateTemplateError(Exception):
    """Erro de negocio (equivale aos Err.Raise 1000-1102 do VBA)."""

    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code


class UpdateTemplateCancelled(Exception):
    """Operacao cancelada pelo usuario (resolver de formato retornou vazio)."""


# ----------------------------------------------------------------------
# Helpers puros (sem CATIA)
# ----------------------------------------------------------------------
def normalize_template_format(raw: Optional[str]) -> str:
    value = (raw or "").upper().strip()
    for ch in ("\r\n", "\r", "\n", "\t", "\xa0"):
        value = value.replace(ch, "")
    return value.strip()


def is_valid_template_format(fmt: Optional[str]) -> bool:
    return normalize_template_format(fmt) in VALID_FORMATS


def is_transferable_view(name: str) -> bool:
    """Ignora Main View, Background View e views com ZONE no nome."""
    n = (name or "").strip().upper()
    return bool(n) and n not in ("MAIN VIEW", "BACKGROUND VIEW") and "ZONE" not in n


def find_template_by_format(folder: str, fmt: str) -> str:
    prefix = TEMPLATE_PREFIX.format(fmt=normalize_template_format(fmt)).lower()
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return ""
    for fname in names:
        if fname.lower().endswith(".catdrawing") and fname.lower().startswith(prefix):
            return os.path.join(folder, fname)
    return ""


# ----------------------------------------------------------------------
# Helpers COM (acesso direto via com_object onde o wrapper pycatia e limitado)
# ----------------------------------------------------------------------
def _iter_com(collection):
    for i in range(1, collection.Count + 1):
        try:
            yield collection.Item(i)
        except Exception:
            continue


def _find_background_view(sheet_com):
    try:
        return sheet_com.Views.Item("Background View")
    except Exception:
        pass
    for view in _iter_com(sheet_com.Views):
        try:
            if "BACKGROUND" in str(view.Name).strip().upper():
                return view
        except Exception:
            continue
    return None


def _find_text_by_name(view_com, text_name: str):
    if view_com is None:
        return None
    try:
        texts = view_com.Texts
        for txt in _iter_com(texts):
            try:
                if str(txt.Name).strip().lower() == text_name.strip().lower():
                    return txt
            except Exception:
                continue
    except Exception:
        pass
    return None


def get_format_from_background(sheet_com) -> str:
    """Text.68 primeiro; depois qualquer texto cujo conteudo seja um formato."""
    bg = _find_background_view(sheet_com)
    if bg is None:
        return ""
    try:
        texts = list(_iter_com(bg.Texts))
    except Exception:
        return ""

    def _value(txt) -> str:
        try:
            return normalize_template_format(str(txt.Text))
        except Exception:
            return ""

    for txt in texts:
        try:
            is_68 = str(txt.Name).strip().lower() == FORMAT_TEXT_NAME.lower()
        except Exception:
            is_68 = False
        if is_68 and is_valid_template_format(_value(txt)):
            return _value(txt)
    for txt in texts:
        if is_valid_template_format(_value(txt)):
            return _value(txt)
    return ""


def _update_sheet_numbers(target_sheets) -> None:
    """A partir da folha 2, grava o indice da folha em Text.75 do Background."""
    for idx in range(2, target_sheets.Count + 1):
        sheet = target_sheets.Item(idx)
        bg = _find_background_view(sheet)
        if bg is None:
            raise UpdateTemplateError(
                1101, f"A Background View nao foi encontrada na folha {idx} ({sheet.Name}).")
        txt = _find_text_by_name(bg, SHEET_NUMBER_TEXT_NAME)
        if txt is None:
            raise UpdateTemplateError(
                1102,
                f"O DrawingText {SHEET_NUMBER_TEXT_NAME} nao foi encontrado no "
                f"Background da folha {idx} ({sheet.Name}).")
        txt.Text = str(idx)


# ----------------------------------------------------------------------
# Funcao principal
# ----------------------------------------------------------------------
def update_template(
    progress_callback: Optional[ProgressCallback] = None,
    format_resolver: Optional[FormatResolver] = None,
    template_folder: str = TEMPLATE_FOLDER,
    status_callback: Optional[StatusCallback] = None,
) -> str:
    """Converte o CATDrawing ativo para o template do formato correspondente.

    CONVERSAO REAL (porte do VBA via COM): le o desenho ativo, localiza o
    template na pasta, copia as views, injeta parametros e atualiza.

    format_resolver: chamado quando o formato nao e detectado no Background
        (substitui a InputBox do VBA). Deve retornar o formato ou vazio/None
        para cancelar (levanta UpdateTemplateCancelled).
    status_callback: recebe (mensagem, nivel) para log na UI.
    Retorna o formato identificado.
    """
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

    try:
        # --- validacoes iniciais -------------------------------------
        if app_com.Documents.Count == 0:
            raise UpdateTemplateError(1001, "Nenhum documento aberto.")
        active = app_com.ActiveDocument
        if not eh_desenho(active):
            raise UpdateTemplateError(1002, "O documento ativo nao e um CATDrawing.")

        source_doc = active
        say(f"Documento ativo: {source_doc.Name}", "ok")
        source_sheets = source_doc.Sheets
        if source_sheets.Count == 0:
            raise UpdateTemplateError(1003, "O documento nao possui folhas.")

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
                    1004, f"Formato invalido: {fmt}. Utilize somente 3A0, A0, A1, A2, A3 ou E3.")
            app_com.Interactive = False
        fmt = normalize_template_format(fmt)
        say(f"Formato: {fmt}", "ok")
        report(10)

        # --- template -------------------------------------------------
        say(f"Procurando template na pasta: {template_folder}", "info")
        full_path = find_template_by_format(template_folder, fmt)
        if not full_path:
            raise UpdateTemplateError(
                1005, f"Template nao encontrado para o formato {fmt}.\n"
                      f"Pasta pesquisada:\n{template_folder}")
        template_name = os.path.basename(full_path)
        say(f"Template encontrado: {template_name}", "ok")

        # --- captura parametros do original ---------------------------
        params: dict[str, str] = {}
        src_params = source_doc.Parameters
        for i in range(1, src_params.Count + 1):
            p = src_params.Item(i)
            name = str(p.Name)
            if "\\" in name:
                name = name.rsplit("\\", 1)[1]
            if name not in params:
                params[name] = str(p.ValueAsString())
        say(f"Parâmetros capturados: {len(params)}", "ok")
        report(15)

        # --- abre ou localiza o template ------------------------------
        target_doc = None
        for doc in app_com.Documents:
            if str(doc.Name).lower() == template_name.lower() and hasattr(doc, "Sheets"):
                target_doc = doc
                break
        if target_doc is None:
            target_doc = app_com.Documents.Open(full_path)
        if target_doc is None:
            raise UpdateTemplateError(1006, "Nao foi possivel abrir o template de destino.")
        target_doc.Activate()
        target_sheets = target_doc.Sheets
        say("Template aberto. Transferindo views...", "info")
        report(25)

        # --- isola views transferiveis --------------------------------
        for s in _iter_com(source_sheets):
            for view in _iter_com(s.Views):
                if is_transferable_view(str(view.Name)):
                    try:
                        view.GenerativeBehavior.Isolate()
                    except Exception:
                        pass
        report(35)

        # --- root do template -----------------------------------------
        try:
            target_root = target_doc.GetItem("CATIADrawingDrawing1")
        except Exception:
            target_root = target_doc

        # --- cria folhas adicionais -----------------------------------
        sel_target = target_doc.Selection
        while target_sheets.Count < source_sheets.Count:
            sel_target.Clear()
            sel_target.Add(target_sheets.Item(1))
            sel_target.Copy()
            sel_target.Clear()
            sel_target.Add(target_root)
            sel_target.Paste()
        report(45)

        # --- copia views ----------------------------------------------
        sel_source = source_doc.Selection
        sel_target = target_doc.Selection
        total = source_sheets.Count
        for s in range(1, total + 1):
            src_sheet = source_sheets.Item(s)
            tgt_sheet = target_sheets.Item(s)
            tgt_sheet.Name = src_sheet.Name
            for v in range(1, src_sheet.Views.Count + 1):
                src_view = src_sheet.Views.Item(v)
                if not is_transferable_view(str(src_view.Name)):
                    continue
                x, y = src_view.x, src_view.y
                sel_source.Clear()
                sel_source.Add(src_view)
                sel_source.Copy()
                sel_target.Clear()
                sel_target.Add(tgt_sheet)
                sel_target.Paste()
                new_view = tgt_sheet.Views.Item(tgt_sheet.Views.Count)
                new_view.x = x
                new_view.y = y
            report(45 + int(35 * s / total))

        # --- remove folhas excedentes ---------------------------------
        sel_del = target_doc.Selection
        for d in range(target_sheets.Count, source_sheets.Count, -1):
            sel_del.Clear()
            sel_del.Add(target_sheets.Item(d))
            sel_del.Delete()
        report(85)

        # --- injeta parametros ----------------------------------------
        tgt_params = target_doc.Parameters
        for key, value in params.items():
            try:
                tgt_params.Item(key).ValuateFromString(value)
            except Exception:
                pass
        try:
            tgt_params.Item(TOTAL_SHEETS_PARAM).ValuateFromString(str(target_sheets.Count))
        except Exception:
            pass
        report(92)

        # --- numeracao das folhas e update ----------------------------
        say("Atualizando numeração das folhas e parâmetros...", "info")
        _update_sheet_numbers(target_sheets)
        target_doc.Update()
        say("Conversão concluída com sucesso.", "ok")
        report(100)
        return fmt

    except UpdateTemplateCancelled:
        # Cancelamento: volta ao desenho original, sem erro.
        try:
            if source_doc is not None:
                source_doc.Activate()
        except Exception:
            pass
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
        try:
            app_com.Interactive = True
            app_com.DisplayFileAlerts = True
        except Exception:
            pass


# ----------------------------------------------------------------------
# Simulacao (percorre as mesmas etapas do VBA, sem templates/rede)
# ----------------------------------------------------------------------
StatusCallback = Callable[[str, str], None]  # (mensagem, nivel)


def simulate_update_template(
    snapshot=None,
    chosen_format: str = "",
    progress_callback: Optional[ProgressCallback] = None,
    status_callback: Optional[StatusCallback] = None,
    delay: float = 0.25,
) -> str:
    """Simula a conversao do VBA usando o desenho REAL aberto, se houver.

    Nao acessa a pasta de templates da empresa nem altera nenhum sistema:
    as etapas de localizar template, copiar views e atualizar sao encenadas
    com time.sleep() e reportadas via callbacks. 'snapshot' e um
    DrawingSnapshot (engine.drawing_snapshot); quando ausente/vazio, a
    simulacao usa dados genericos apenas para demonstrar o fluxo.
    Retorna o formato usado.
    """
    def prog(pct: float) -> None:
        if progress_callback:
            progress_callback(max(0, min(100, int(pct))))

    def say(msg: str, level: str = "info") -> None:
        if status_callback:
            status_callback(msg, level)

    prog(0)
    say("Iniciando simulação do Update Template (nenhum arquivo será alterado).", "info")
    time.sleep(delay)

    has_drawing = bool(snapshot and getattr(snapshot, "has_drawing", False))
    if has_drawing:
        say(f"Documento ativo: {snapshot.name}", "ok")
    elif snapshot and getattr(snapshot, "connected", False):
        say("CATIA aberto, mas sem CATDrawing ativo — dados genéricos.", "warn")
    else:
        say("CATIA não detectado — simulando com dados genéricos.", "warn")
    time.sleep(delay)
    prog(8)

    # --- formato ------------------------------------------------------
    fmt = normalize_template_format(chosen_format)
    if not is_valid_template_format(fmt) and snapshot:
        fmt = normalize_template_format(getattr(snapshot, "detected_format", ""))
    if not is_valid_template_format(fmt):
        fmt = "A0"
    say(f"Formato identificado: {fmt}", "ok")
    prog(15)
    time.sleep(delay)

    # --- localizar template (simulado) --------------------------------
    template_name = TEMPLATE_PREFIX.format(fmt=fmt) + ".CATDrawing"
    say(f"Procurando template: {template_name}", "info")
    say("Pasta de templates (indisponível fora da rede da empresa):", "warn")
    say(f"   {TEMPLATE_FOLDER}", "muted")
    time.sleep(delay * 2)
    say("[SIMULAÇÃO] Template considerado encontrado.", "ok")
    prog(28)

    # --- capturar parametros do original ------------------------------
    n_params = len(snapshot.parameters) if has_drawing else 0
    say(f"Capturando parâmetros do desenho ({n_params})...", "info")
    time.sleep(delay * 2)
    prog(38)

    # --- isolar / copiar views ----------------------------------------
    if has_drawing:
        steps = [(s.name, sum(1 for v in s.views if is_transferable_view(v.name)))
                 for s in snapshot.sheets]
    else:
        steps = [("Sheet.1", 3), ("Sheet.2", 1)]
    total_views = sum(n for _, n in steps) or 1
    say(f"Transferindo views para o template ({total_views} no total)...", "info")
    base, span = 38.0, 42.0  # 38% -> 80%
    done = 0
    for sname, n in steps:
        say(f"  Folha '{sname}': {n} view(s) transferível(is)", "info")
        for _ in range(n):
            time.sleep(delay)
            done += 1
            prog(base + span * done / total_views)
    prog(80)

    # --- numeracao / parametros / update ------------------------------
    say("Atualizando numeração das folhas (Text.75)...", "info")
    time.sleep(delay * 1.5)
    prog(88)
    say(f"Atualizando total de folhas (No_of_Sheets = {len(steps)})...", "info")
    time.sleep(delay)
    prog(94)
    say("Injetando parâmetros e atualizando o desenho...", "info")
    time.sleep(delay * 1.5)
    prog(100)
    say("Simulação concluída. Nenhum sistema real foi alterado.", "ok")
    return fmt


def mock_update_template(callback_progresso: Optional[ProgressCallback] = None) -> str:
    """Compatibilidade: simulacao simples enviando inteiros de 0 a 100."""
    return simulate_update_template(
        progress_callback=callback_progresso, status_callback=None, delay=0.05)


if __name__ == "__main__":
    simulate_update_template(
        progress_callback=lambda p: print(f"{p}%"),
        status_callback=lambda m, lvl: print(f"[{lvl}] {m}"),
        delay=0.02)
