"""Telas do Update Template e dos dois Splits."""
from __future__ import annotations

import os

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout

from ui_qt.font_size_page import button, label
from ui_qt.tool_page import ToolPage, abrir_pasta, preencher, tabela


class UpdateTemplatePage(ToolPage):
    TOOL = "update"
    TITULO = "Update Template"
    DESCRICAO = (
        "Troca a etiqueta no próprio desenho, folha por folha, conforme o formato de cada uma. "
        "As vistas não são tocadas. Nada é salvo: confira o desenho e salve para confirmar."
    )
    BOTAO = "ATUALIZAR TEMPLATE"
    BOTAO_DE_NOVO = "Atualizar de novo"
    ANDAMENTO = "Atualizando o template"
    PODE_PARAR = False  # parar no meio deixaria o desenho parcialmente convertido

    def _build_results(self, col: QVBoxLayout) -> None:
        self.lbl_note = label("Confira o desenho e salve para confirmar.", "detalheForte")
        self.lbl_note.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        col.addWidget(self.lbl_note)
        self.table = tabela(("FOLHA", "FORMATO"), {1: 120}, 0)
        col.addWidget(self.table, 1)
        caixa = QFrame()
        caixa.setObjectName("detalhe")
        c = QVBoxLayout(caixa)
        c.setContentsMargins(14, 8, 14, 8)
        c.addWidget(label("AVISOS", "secao"))
        self.lbl_warnings = label("", "detalheFraco")
        self.lbl_warnings.setWordWrap(True)
        self.lbl_warnings.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        c.addWidget(self.lbl_warnings)
        self._warnings_box = caixa
        col.addWidget(caixa)

    def _show_report(self, report) -> None:
        self.lbl_sub.setText(f"{os.path.basename(report.doc_full_name)}  ·  {len(report.sheets)} folhas")
        preencher(self.table, report.sheets)
        self.lbl_warnings.setText("\n".join(f"• {a}" for a in report.warnings))
        self._warnings_box.setVisible(bool(report.warnings))


class PosZonePage(ToolPage):
    TOOL = "poszone"
    TITULO = "Position and Zone"
    DESCRICAO = (
        "Acha os callouts de todas as folhas, a zona e a quantidade de cada um, e abre a tabela "
        "numa cópia da planilha de Callouts. O desenho não é alterado."
    )
    BOTAO = "MAPEAR CALLOUTS"
    BOTAO_DE_NOVO = "Mapear de novo"
    ANDAMENTO = "Lendo as folhas"
    ETIQUETA = "SÓ CONFERE"
    PODE_PARAR = False  # sem todas as folhas, as quantidades somadas ficariam erradas

    def _build_results(self, col: QVBoxLayout) -> None:
        self.table = tabela(("POSIÇÃO", "ZONA", "QTD", "ONDE"), {0: 80, 1: 170, 2: 60}, 3)
        col.addWidget(self.table, 1)
        caixa = QFrame()
        caixa.setObjectName("detalhe")
        c = QVBoxLayout(caixa)
        c.setContentsMargins(14, 8, 14, 8)
        self.lbl_counts = label("", "detalheFraco")
        self.lbl_counts.setWordWrap(True)
        self.lbl_counts.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        c.addWidget(self.lbl_counts)
        col.addWidget(caixa)

    def _show_report(self, report) -> None:
        c = report.counters
        self.lbl_sub.setText(
            f"PN {report.pn}  ·  {len(report.callouts)} callouts consolidados no Excel  ·  "
            f"{report.occurrences - c.referencias} ocorrências válidas"
        )
        self.lbl_counts.setText(
            f"Objetos válidos: {c.validos}  ·  Linhas multilinha: {c.multilinha}  ·  Referências ignoradas por REF: "
            f"{c.referencias}  ·  Quantidades por chave: {c.chaves}\n"
            f"Agrupados ou ambíguos não contabilizados: {c.grupo}  ·  Inconsistentes não contabilizados: {c.conflito}"
        )
        linhas = sorted(report.callouts, key=lambda x: float(x.number))
        preencher(self.table, [(x.number, x.zone, x.qty, f"{x.sheet} - {x.view}") for x in linhas])


class _SplitPage(ToolPage):
    ETIQUETA = "CRIA ARQUIVOS"
    COLUNA = "ARQUIVO"

    def _build_results(self, col: QVBoxLayout) -> None:
        self.table = tabela((self.COLUNA,), {}, 0)
        col.addWidget(self.table, 1)
        linha = QHBoxLayout()
        self.lbl_folder = label("", "detalheFraco")
        self.lbl_folder.setWordWrap(True)
        self.lbl_folder.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        linha.addWidget(self.lbl_folder, 1)
        self.btn_folder = button("Abrir a pasta", "secundario")
        self.btn_folder.clicked.connect(lambda: abrir_pasta(self._report.folder if self._report else ""))
        linha.addWidget(self.btn_folder)
        col.addLayout(linha)

    def _show_report(self, report) -> None:
        parou = "  ·  Parado antes do fim" if report.stopped else ""
        self.lbl_sub.setText(self._resumo(report) + parou)
        preencher(self.table, [(os.path.basename(f),) for f in report.files])
        self.lbl_folder.setText(report.folder)
        self.lbl_folder.setToolTip(report.folder)


class Split2DPage(_SplitPage):
    TOOL = "split2d"
    TITULO = "Split 2D"
    DESCRICAO = (
        "Exporta cada folha do desenho salvo para um CATDrawing próprio, numa pasta em Downloads. "
        "As vistas destravadas são travadas automaticamente."
    )
    BOTAO = "DIVIDIR POR FOLHA"
    BOTAO_DE_NOVO = "Dividir de novo"
    ANDAMENTO = "Exportando as folhas"

    def _resumo(self, report) -> str:
        travadas = f"  ·  {report.locked_views} vistas travadas" if report.locked_views else ""
        return f"{len(report.files)} folhas exportadas{travadas}"


class Split3DPage(_SplitPage):
    TOOL = "split3d"
    TITULO = "Split 3D"
    DESCRICAO = (
        "Divide os Bodies do CATPart salvo em várias peças, na subpasta SPLIT_PARTS. "
        "O PartBody vai em todas as partes."
    )
    BOTAO = "DIVIDIR A PEÇA"
    BOTAO_DE_NOVO = "Dividir de novo"
    ANDAMENTO = "Criando as partes"
    EXTENSAO = ".catpart"
    NOME_DOCUMENTO = "CATPart"

    def _resumo(self, report) -> str:
        return f"PN {report.pn}  ·  {report.bodies} Bodies  ·  {len(report.files)} arquivos"
