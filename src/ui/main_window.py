"""HUB de ferramentas (janela borderless), visual fiel à referência IMAGEM3.

Descobre os modulos em src/tools e gera uma pilula numerada por ferramenta.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType
from typing import List

SRC_DIR = Path(__file__).resolve().parent.parent
TOOLS_DIR = SRC_DIR / "tools"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import customtkinter as ctk  # noqa: E402

from ui import theme as T  # noqa: E402

WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 760


def discover_tools() -> List[ModuleType]:
    """Importa cada .py de src/tools (ignora os que comecam com '_')."""
    modules: List[ModuleType] = []
    for path in sorted(TOOLS_DIR.glob("*.py")):
        if path.name.startswith("_"):
            continue
        try:
            mod = importlib.import_module(f"tools.{path.stem}")
        except Exception as exc:  # um modulo quebrado nao derruba o HUB
            print(f"[HUB] Falha ao carregar {path.name}: {exc}", file=sys.stderr)
            continue
        if hasattr(mod, "TOOL_NAME") and hasattr(mod, "Tool"):
            modules.append(mod)
    modules.sort(key=lambda m: (getattr(m, "ORDER", 100), m.TOOL_NAME))
    return modules


class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        self._drag_dx = self._drag_dy = 0
        self._tools = discover_tools()
        self._nav_buttons: List[ctk.CTkButton] = []
        self._current_tool = None

        self.overrideredirect(True)
        self.configure(fg_color=T.APP_BG)
        x = (self.winfo_screenwidth() - WINDOW_WIDTH) // 2
        y = (self.winfo_screenheight() - WINDOW_HEIGHT) // 2
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}+{x}+{y}")

        self._build_header()
        # Linha de acento ciano sob o cabecalho (detalhe "arrojado").
        ctk.CTkFrame(self, height=2, corner_radius=0, fg_color=T.CYAN).pack(fill="x")

        self._content = ctk.CTkFrame(self, fg_color="transparent")
        self._content.pack(fill="both", expand=True, padx=12, pady=12)

        if self._tools:
            self.select_tool(0)
        else:
            ctk.CTkLabel(self._content, text="Nenhuma ferramenta encontrada em src/tools.",
                         text_color=T.MUTED).pack(expand=True)

    # ------------------------------------------------------------------
    # Cabecalho: logo | pilulas das ferramentas | status | X
    # ------------------------------------------------------------------
    def _build_header(self) -> None:
        bar = ctk.CTkFrame(self, height=66, corner_radius=0, fg_color=T.HEADER)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        draggable = [bar]

        logo = ctk.CTkFrame(bar, fg_color="transparent")
        logo.pack(side="left", padx=(18, 0))
        badge = ctk.CTkLabel(logo, text="E1", width=42, height=42, corner_radius=12,
                             fg_color=T.BRAND, text_color="#FFFFFF",
                             font=ctk.CTkFont(size=16, weight="bold"))
        badge.pack(side="left")
        titles = ctk.CTkFrame(logo, fg_color="transparent")
        titles.pack(side="left", padx=11)
        t1 = ctk.CTkLabel(titles, text="DWG TOOLS", text_color=T.TEXT, anchor="w",
                          font=ctk.CTkFont(size=18, weight="bold"))
        t1.pack(anchor="w")
        t2 = ctk.CTkLabel(titles, text="DESIGN ASSURANCE HUB", text_color=T.MUTED,
                          font=ctk.CTkFont(size=9, weight="bold"))
        t2.pack(anchor="w")
        draggable += [logo, badge, titles, t1, t2]

        ctk.CTkButton(bar, text="✕", width=46, height=66, corner_radius=0,
                      fg_color="transparent", hover_color=T.DANGER, text_color=T.MUTED,
                      font=ctk.CTkFont(size=15, weight="bold"),
                      command=self.close).pack(side="right")

        status = ctk.CTkFrame(bar, fg_color="transparent")
        status.pack(side="right", padx=14)
        self._conn_chip = ctk.CTkLabel(
            status, text="●  CATIA desconectado", text_color=T.MUTED, fg_color=T.CARD,
            corner_radius=13, font=ctk.CTkFont(size=11, weight="bold"), padx=12, height=28)
        self._conn_chip.pack(side="left", padx=4)
        self._doc_chip = ctk.CTkLabel(
            status, text="—", text_color=T.MUTED, fg_color=T.CARD, corner_radius=13,
            font=ctk.CTkFont(size=11, weight="bold"), padx=12, height=28)
        self._doc_chip.pack(side="left", padx=4)
        draggable.append(status)

        # Pilulas numeradas (uma por modulo de src/tools), centralizadas.
        nav = ctk.CTkFrame(bar, fg_color=T.PANEL, corner_radius=22, border_width=1,
                           border_color=T.BORDER, height=46)
        nav.place(relx=0.5, rely=0.5, anchor="center")
        inner = ctk.CTkFrame(nav, fg_color="transparent")
        inner.pack(padx=6, pady=6)
        for i, mod in enumerate(self._tools):
            btn = ctk.CTkButton(
                inner, text=f"{i + 1}   {mod.TOOL_NAME}", height=34, corner_radius=17,
                fg_color="transparent", hover_color=T.CARD, text_color=T.MUTED,
                border_width=0, font=ctk.CTkFont(size=12, weight="bold"),
                command=lambda idx=i: self.select_tool(idx))
            btn.pack(side="left", padx=3)
            self._nav_buttons.append(btn)

        for w in draggable:
            w.bind("<ButtonPress-1>", self._start_drag)
            w.bind("<B1-Motion>", self._do_drag)

    def set_status(self, snapshot) -> None:
        """Chamado pelas ferramentas (polling) para refletir o estado do CATIA."""
        connected = bool(getattr(snapshot, "connected", False))
        has_drawing = bool(getattr(snapshot, "has_drawing", False))
        self._conn_chip.configure(
            text="●  CATIA ativo" if connected else "●  CATIA desconectado",
            text_color=T.GREEN if connected else T.DANGER)
        if has_drawing:
            self._doc_chip.configure(text=snapshot.name, text_color=T.TEXT)
        else:
            self._doc_chip.configure(
                text=getattr(snapshot, "message", "") or "sem desenho", text_color=T.MUTED)

    def select_tool(self, index: int) -> None:
        """Limpa o frame de conteudo e carrega a UI da ferramenta escolhida."""
        for w in self._content.winfo_children():
            w.destroy()
        self._current_tool = self._tools[index].Tool(self._content, hub=self)
        self._current_tool.pack(fill="both", expand=True)
        for i, btn in enumerate(self._nav_buttons):
            on = i == index
            btn.configure(fg_color=T.BRAND if on else "transparent",
                          text_color="#FFFFFF" if on else T.MUTED,
                          border_width=1 if on else 0, border_color=T.CYAN)

    # ------------------------------------------------------------------
    def _start_drag(self, e) -> None:
        self._drag_dx = e.x_root - self.winfo_x()
        self._drag_dy = e.y_root - self.winfo_y()

    def _do_drag(self, e) -> None:
        self.geometry(f"+{e.x_root - self._drag_dx}+{e.y_root - self._drag_dy}")

    def close(self) -> None:
        self.destroy()


if __name__ == "__main__":
    MainWindow().mainloop()
