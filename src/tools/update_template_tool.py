"""Ferramenta 1: Update Template (conversao de desenhos).

Espelha o CATDrawing realmente aberto no CATIA e, no botao Executar, roda a
conversao REAL (engine.update_template.update_template) — o porte do VBA via
COM. Em uma maquina sem os templates/rede da empresa, a execucao falha de
forma honesta (ex.: 'Template nao encontrado') em vez de simular sucesso.
"""
from __future__ import annotations

import threading

import customtkinter as ctk
from PIL import Image, ImageTk

from engine.catia_capture import capture_active_sheet, get_active_sheet_name
from engine.drawing_snapshot import DrawingSnapshot, get_catia_state, get_snapshot
from engine.update_template import VALID_FORMATS
from ui import theme as T

TOOL_NAME = "Update Template"
ORDER = 0
POLL_MS = 2000  # intervalo do polling de estado do CATIA (abrir/fechar ao vivo)

_LEVEL_COLOR = {
    "info": T.TEXT,
    "ok": T.GREEN,
    "warn": T.WARN,
    "error": T.DANGER,
    "muted": T.MUTED_TEXT,
}


class Tool(ctk.CTkFrame):
    # Subclasses (outras ferramentas) sobrescrevem estes.
    HEADER_TITLE = "Update Template"
    HEADER_SUBTITLE = "Conversão de desenhos para o template E1"

    def __init__(self, master, hub=None, on_execute=None):
        super().__init__(master, fg_color="transparent")
        self._hub = hub
        self._snapshot: DrawingSnapshot | None = None
        self._sheet_index = 0
        self._running = False
        self._last_key = None
        self._poll_id = None
        self._preview_img = None  # PIL.Image da captura atual (p/ refit no resize)
        self._photo = None        # ref viva do ImageTk.PhotoImage
        self.selected_format = ""
        self._format_buttons: dict[str, ctk.CTkButton] = {}

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0, minsize=400)
        self.grid_rowconfigure(0, weight=1)

        self._build_preview()
        self._build_assistant()
        self.refresh()
        self._poll_id = self.after(POLL_MS, self._poll)

    # ------------------------------------------------------------------
    # Polling: reconhece abrir/fechar o CATIA enquanto o app esta aberto
    # ------------------------------------------------------------------
    def _poll(self) -> None:
        self._poll_id = None
        if not self.winfo_exists():
            return
        if self._running:
            # Nao sondar durante a conversao (CATIA ocupado => falso negativo).
            self._poll_id = self.after(POLL_MS, self._poll)
            return
        try:
            state = get_catia_state()
            key = (state.connected, state.has_drawing, state.name)
            if key != self._last_key:
                self.refresh()            # estado mudou -> leitura completa
            elif self._hub:
                self._hub.set_status(state)  # sem mudanca -> so atualiza o chip
        except Exception:
            pass
        if self.winfo_exists():
            self._poll_id = self.after(POLL_MS, self._poll)

    def destroy(self) -> None:
        if self._poll_id is not None:
            try:
                self.after_cancel(self._poll_id)
            except Exception:
                pass
            self._poll_id = None
        super().destroy()

    # ------------------------------------------------------------------
    # Esquerda: espelho do desenho aberto
    # ------------------------------------------------------------------
    def _build_preview(self) -> None:
        left = ctk.CTkFrame(self, fg_color=T.PANEL, corner_radius=12,
                            border_width=1, border_color=T.BORDER)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        left.grid_rowconfigure(1, weight=1)
        left.grid_columnconfigure(0, weight=1)

        head = ctk.CTkFrame(left, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 0))
        self._title = ctk.CTkLabel(head, text="", text_color=T.MUTED,
                                   font=ctk.CTkFont(size=12, weight="bold"))
        self._title.pack(side="left")
        ctk.CTkButton(head, text="↻", width=32, height=28, fg_color=T.CARD,
                      hover_color=T.BORDER, text_color=T.CYAN,
                      command=self.refresh).pack(side="right")
        self._sheet_menu = ctk.CTkOptionMenu(
            head, values=["-"], width=120, height=28, fg_color=T.CARD,
            button_color=T.BORDER, text_color=T.TEXT, command=self._on_sheet_selected)
        self._sheet_menu.pack(side="right", padx=8)

        self._canvas = ctk.CTkCanvas(left, bg=T.PANEL, highlightthickness=0)
        self._canvas.grid(row=1, column=0, sticky="nsew", padx=14, pady=14)
        self._canvas.bind("<Configure>", lambda _e: self._on_canvas_resize())

    # ------------------------------------------------------------------
    # Direita: painel "assistente"
    # ------------------------------------------------------------------
    def _build_assistant(self) -> None:
        right = ctk.CTkFrame(self, fg_color=T.PANEL, corner_radius=12,
                             border_width=1, border_color=T.BORDER, width=400)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_propagate(False)
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        head = ctk.CTkFrame(right, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 6))
        ctk.CTkLabel(head, text=self.HEADER_TITLE, text_color=T.TEXT,
                     font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(head, text=self.HEADER_SUBTITLE,
                     text_color=T.MUTED, font=ctk.CTkFont(size=11)).pack(anchor="w")
        chips = ctk.CTkFrame(head, fg_color="transparent")
        chips.pack(anchor="w", pady=(10, 0))
        self._catia_chip = self._chip(chips, "CATIA")
        self._chip(chips, "TEMPLATES")

        body = ctk.CTkScrollableFrame(right, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=8)

        self._checks = ctk.CTkFrame(body, fg_color="transparent")
        self._checks.pack(fill="x", padx=6)

        ctk.CTkLabel(body, text="Resumo da análise", text_color=T.TEXT,
                     font=ctk.CTkFont(size=12, weight="bold")
                     ).pack(anchor="w", padx=8, pady=(14, 4))
        self._summary = ctk.CTkFrame(body, fg_color=T.CARD, corner_radius=8,
                                     border_width=1, border_color=T.BORDER)
        self._summary.pack(fill="x", padx=6)

        ctk.CTkLabel(body, text="O formato está correto?", text_color=T.TEXT,
                     font=ctk.CTkFont(size=12, weight="bold")
                     ).pack(anchor="w", padx=8, pady=(16, 4))
        grid = ctk.CTkFrame(body, fg_color="transparent")
        grid.pack(fill="x", padx=6)
        grid.grid_columnconfigure((0, 1, 2), weight=1, uniform="fmt")
        for i, fmt in enumerate(VALID_FORMATS):
            btn = ctk.CTkButton(
                grid, text=fmt, height=34, fg_color=T.CARD, hover_color=T.BORDER,
                border_width=1, border_color=T.BORDER, text_color=T.TEXT,
                font=ctk.CTkFont(size=11, weight="bold"),
                command=lambda f=fmt: self._select_format(f))
            btn.grid(row=i // 3, column=i % 3, padx=3, pady=3, sticky="ew")
            self._format_buttons[fmt] = btn

        ctk.CTkLabel(body, text="Log da simulação", text_color=T.TEXT,
                     font=ctk.CTkFont(size=12, weight="bold")
                     ).pack(anchor="w", padx=8, pady=(16, 4))
        self._log = ctk.CTkTextbox(body, height=150, fg_color=T.CARD,
                                   border_width=1, border_color=T.BORDER,
                                   text_color=T.TEXT, font=ctk.CTkFont(size=11),
                                   wrap="word", activate_scrollbars=True)
        self._log.pack(fill="x", padx=6, pady=(0, 6))
        for lvl, color in _LEVEL_COLOR.items():
            self._log._textbox.tag_config(lvl, foreground=color)
        self._log.configure(state="disabled")

        foot = ctk.CTkFrame(right, fg_color="transparent")
        foot.grid(row=2, column=0, sticky="ew", padx=16, pady=(4, 14))
        self._execute = ctk.CTkButton(
            foot, text="EXECUTAR UPDATE TEMPLATE", height=44, fg_color=T.CYAN,
            hover_color=T.CYAN_DARK, text_color="#04202B",
            font=ctk.CTkFont(size=12, weight="bold"), command=self._handle_execute)
        self._execute.pack(fill="x")
        self._progress = ctk.CTkProgressBar(foot, height=8, fg_color=T.CARD,
                                            progress_color=T.CYAN)
        self._progress.pack(fill="x", pady=(10, 0))
        self._progress.set(0)
        self._progress_label = ctk.CTkLabel(foot, text="0%", text_color=T.MUTED,
                                            font=ctk.CTkFont(size=11))
        self._progress_label.pack(pady=(2, 0))

    @staticmethod
    def _chip(parent, text: str) -> ctk.CTkLabel:
        lbl = ctk.CTkLabel(parent, text=f"●  {text}", text_color=T.MUTED, fg_color=T.CARD,
                           corner_radius=10, font=ctk.CTkFont(size=10, weight="bold"),
                           padx=8, height=22)
        lbl.pack(side="left", padx=(0, 6))
        return lbl

    # ------------------------------------------------------------------
    # Dados (estado real do CATIA)
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        snap = get_snapshot()
        self._snapshot = snap
        self._last_key = (snap.connected, snap.has_drawing, snap.name)
        if self._hub:
            self._hub.set_status(snap)

        names = [s.name for s in snap.sheets] or ["-"]
        self._sheet_menu.configure(values=names)
        # Sincroniza com a folha ativa do CATIA (evita trocar a folha do usuario).
        self._sheet_index = 0
        if snap.has_drawing:
            active = get_active_sheet_name()
            if active and active in names:
                self._sheet_index = names.index(active)
        self._sheet_menu.set(names[self._sheet_index])
        if snap.has_drawing:
            self._title.configure(text=snap.name, text_color=T.TEXT)
        else:
            self._title.configure(text=snap.message or "Nenhum desenho", text_color=T.MUTED)
        self._catia_chip.configure(text_color=T.GREEN if snap.connected else T.MUTED)

        n_views = sum(len(s.views) for s in snap.sheets)
        if snap.has_drawing:
            checks = [
                ("CATIA em execução", True),
                (f"Desenho detectado: {snap.name}", True),
                (f"Formato: {snap.detected_format or 'não identificado'}",
                 bool(snap.detected_format)),
                (f"Folhas: {len(snap.sheets)}  ·  Views: {n_views}", bool(snap.sheets)),
            ]
        else:
            checks = [
                ("CATIA em execução", snap.connected),
                (snap.message or "Nenhum CATDrawing ativo", False),
            ]
        self._fill_checks(checks)
        self._fill_summary([
            ("Documento", snap.name or "—"),
            ("Formato", snap.detected_format or "—"),
            ("Folhas", str(len(snap.sheets))),
            ("Views", str(n_views)),
            ("Parâmetros", str(len(snap.parameters))),
        ])
        self._select_format(snap.detected_format)
        self._update_preview(recapture=True)

    def _fill_checks(self, items) -> None:
        for w in self._checks.winfo_children():
            w.destroy()
        for text, ok in items:
            row = ctk.CTkFrame(self._checks, corner_radius=6,
                               fg_color=T.GREEN_BG if ok else T.CARD,
                               border_width=1,
                               border_color=T.GREEN_BORDER if ok else T.BORDER)
            row.pack(fill="x", pady=3)
            ctk.CTkLabel(row, text="✔" if ok else "!", width=22, height=22,
                         corner_radius=11, fg_color=T.GREEN if ok else T.WARN,
                         text_color="#04140C", font=ctk.CTkFont(size=11, weight="bold")
                         ).pack(side="left", padx=8, pady=7)
            ctk.CTkLabel(row, text=text, text_color=T.TEXT, anchor="w", justify="left",
                         font=ctk.CTkFont(size=11, weight="bold"), wraplength=300
                         ).pack(side="left", fill="x", expand=True, padx=(0, 8))

    def _fill_summary(self, rows) -> None:
        for w in self._summary.winfo_children():
            w.destroy()
        for key, value in rows:
            r = ctk.CTkFrame(self._summary, fg_color="transparent")
            r.pack(fill="x", padx=10, pady=3)
            ctk.CTkLabel(r, text=key, text_color=T.MUTED,
                         font=ctk.CTkFont(size=11)).pack(side="left")
            ctk.CTkLabel(r, text=value, text_color=T.TEXT,
                         font=ctk.CTkFont(size=11, weight="bold")).pack(side="right")

    def _select_format(self, fmt: str) -> None:
        self.selected_format = fmt if fmt in VALID_FORMATS else ""
        for f, btn in self._format_buttons.items():
            on = f == self.selected_format
            btn.configure(fg_color=T.BRAND if on else T.CARD,
                          border_color=T.CYAN if on else T.BORDER)

    def _on_sheet_selected(self, name: str) -> None:
        if self._snapshot:
            for i, s in enumerate(self._snapshot.sheets):
                if s.name == name:
                    self._sheet_index = i
        self._update_preview(recapture=True)

    def _on_canvas_resize(self) -> None:
        # Redimensionou: reaproveita a imagem ja capturada (nao recaptura).
        if self._preview_img is not None:
            self._draw_image()
        else:
            self._render_schematic()

    def _update_preview(self, recapture: bool = True) -> None:
        """Mostra a captura real da folha ativa; cai no esquema se falhar."""
        self._preview_img = None
        snap = self._snapshot
        if recapture and snap and snap.has_drawing:
            sheet_name = None
            if snap.sheets and 0 <= self._sheet_index < len(snap.sheets):
                sheet_name = snap.sheets[self._sheet_index].name
            path = capture_active_sheet(sheet_name)
            if path:
                try:
                    with Image.open(path) as im:
                        self._preview_img = im.convert("RGB").copy()
                except Exception:
                    self._preview_img = None
        if self._preview_img is not None:
            self._draw_image()
        else:
            self._render_schematic()

    def _draw_image(self) -> None:
        c = self._canvas
        c.delete("all")
        cw, ch = max(c.winfo_width(), 50), max(c.winfo_height(), 50)
        img = self._preview_img.copy()
        img.thumbnail((cw - 24, ch - 24), Image.LANCZOS)  # ajusta mantendo proporcao
        self._photo = ImageTk.PhotoImage(img)  # guardar ref p/ nao ser coletado
        c.create_image(cw / 2, ch / 2, image=self._photo, anchor="center")

    def _render_schematic(self) -> None:
        c = self._canvas
        c.delete("all")
        cw, ch = max(c.winfo_width(), 50), max(c.winfo_height(), 50)
        if not self._snapshot or not self._snapshot.sheets:
            msg = ("Abra um CATDrawing no CATIA\ne clique em ↻"
                   if not (self._snapshot and self._snapshot.connected)
                   else "Nenhum CATDrawing ativo")
            c.create_text(cw / 2, ch / 2, text=msg, fill=T.MUTED,
                          font=("Segoe UI", 12), justify="center")
            return
        sheet = self._snapshot.sheets[self._sheet_index]
        scale = min((cw - 24) / sheet.width, (ch - 24) / sheet.height)
        sw, sh = sheet.width * scale, sheet.height * scale
        ox, oy = (cw - sw) / 2, (ch - sh) / 2
        c.create_rectangle(ox, oy, ox + sw, oy + sh, fill="#F4F7FA",
                           outline=T.CYAN, width=2)
        c.create_rectangle(ox + sw - 150 * scale, oy + sh - 70 * scale,
                           ox + sw, oy + sh, outline=T.BRAND, width=1)
        for v in sheet.views:
            px = ox + v.x * scale
            py = oy + (sheet.height - v.y) * scale
            half = 42 * scale
            c.create_rectangle(px - half, py - half * 0.7, px + half, py + half * 0.7,
                               outline=T.BRAND, dash=(4, 2))
            c.create_text(px, py, text=v.name, fill=T.BRAND_DARK, font=("Segoe UI", 8))

    # ------------------------------------------------------------------
    # Execucao REAL (update_template convertido do VBA), em thread
    # ------------------------------------------------------------------
    def _handle_execute(self) -> None:
        if self._running:
            return
        self._running = True
        self._execute.configure(state="disabled", text="CONVERTENDO...")
        self.set_progress(0)
        self._log_clear()
        chosen = self.selected_format
        threading.Thread(target=self._run_conversion, args=(chosen,),
                         daemon=True).start()

    def _do_conversion(self, progress_callback, status_callback, format_resolver):
        """Motor da ferramenta. Subclasses sobrescrevem para outra lógica."""
        from engine.update_template import update_template
        return update_template(
            progress_callback=progress_callback,
            status_callback=status_callback,
            format_resolver=format_resolver)

    def _run_conversion(self, chosen_format: str) -> None:
        import pythoncom
        from engine.update_template import UpdateTemplateCancelled, UpdateTemplateError

        def prog(p):
            self.after(0, self.set_progress, p)

        def say(msg, level="info"):
            self.after(0, self._log_append, msg, level)

        pythoncom.CoInitialize()  # COM precisa ser inicializado nesta thread
        try:
            fmt = self._do_conversion(prog, say, lambda: chosen_format)
            say(f"Formato aplicado: {fmt}", "ok")
        except UpdateTemplateCancelled:
            say("Operação cancelada: selecione um formato antes de converter.", "warn")
        except UpdateTemplateError as exc:
            say(f"Erro {exc.code}: {exc}", "error")
        except Exception as exc:  # noqa: BLE001 - nunca derrubar a UI
            say(f"Falha inesperada: {exc}", "error")
        finally:
            pythoncom.CoUninitialize()
            self.after(0, self._conversion_done)

    def _conversion_done(self) -> None:
        self._running = False
        self._execute.configure(state="normal", text="EXECUTAR UPDATE TEMPLATE")
        self.refresh()  # re-sincroniza o estado do CATIA após a execução

    def _log_clear(self) -> None:
        self._log.configure(state="normal")
        self._log.delete("1.0", "end")
        self._log.configure(state="disabled")

    def _log_append(self, msg: str, level: str = "info") -> None:
        self._log.configure(state="normal")
        self._log.insert("end", msg + "\n", level)
        self._log.see("end")
        self._log.configure(state="disabled")

    # ------------------------------------------------------------------
    # API publica
    # ------------------------------------------------------------------
    def set_progress(self, value: int) -> None:
        value = max(0, min(100, int(value)))
        self._progress.set(value / 100)
        self._progress_label.configure(text=f"{value}%")
