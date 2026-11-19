"""Telas do Update Template, do Symbol Shape e dos dois Splits."""
from __future__ import annotations

import os
from typing import Dict, List

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QButtonGroup, QGridLayout, QHBoxLayout, QSpinBox,
    QVBoxLayout, QWidget,
)

from engine import atualizar_template as at
from engine import splits as sp
from engine import symbol_shape as ss
from ui_qt import theme as T
from ui_qt.font_size_page import button, label
from ui_qt.pecas import (
    LinhaSituacao, Resumo, botao, botao_grande, cabecalho, etiqueta, largura_livre, moldura,
)
from ui_qt.tool_page import ToolPage, abrir_pasta, preencher, tabela

LIMITE_ENVIO_MB = 200


def _mb(valor: float) -> str:
    return f"{valor:.0f} MB" if valor >= 10 else f"{valor:.1f} MB".replace(".", ",")


# ---------------------------------------------------------------------
# Update Template
# ---------------------------------------------------------------------
class UpdateTemplatePage(ToolPage):
    TOOL = "update"
    TITULO = "Update Template"
    DESCRICAO = "Troca a etiqueta no próprio desenho. As vistas não são tocadas."
    BOTAO = "CONFIRMAR E ATUALIZAR"
    BOTAO_DE_NOVO = "Atualizar de novo"
    ANDAMENTO = "Atualizando o template"
    ICONE = "refresh"
    PODE_PARAR = False  # parar no meio deixaria o desenho parcialmente convertido
    TEM_PREVIA = True

    formats_changed = Signal(object)

    def __init__(self):
        self._escolhidos: Dict[str, str] = {}
        self._folhas: List[list] = []
        super().__init__()

    def _build_ready(self, col: QVBoxLayout) -> None:
        topo, sub = cabecalho(self.TITULO, etiqueta(self.ETIQUETA))
        sub.setText(self.DESCRICAO)
        col.addLayout(topo)
        col.addWidget(label("TAMANHO DETECTADO", "secao"))
        self.lbl_detectado = largura_livre(label("", "porcento"))
        col.addWidget(self.lbl_detectado)
        self.lbl_detalhe_tamanho = largura_livre(label("", "sub"))
        col.addWidget(self.lbl_detalhe_tamanho)
        self.linha_template = LinhaSituacao()
        col.addWidget(self.linha_template)

        # Os tamanhos so aparecem se a pessoa pedir para escolher.
        self.painel_manual = QWidget()
        manual = QVBoxLayout(self.painel_manual)
        manual.setContentsMargins(0, 6, 0, 0)
        manual.setSpacing(8)
        manual.addWidget(label("Escolha o tamanho", "subtitulo2"))
        grade = QGridLayout()
        grade.setSpacing(6)
        self._grupo_formatos = QButtonGroup(self)
        for i, formato in enumerate(at.FORMATOS):
            b = button(formato, "formato")
            b.setCheckable(True)
            self._grupo_formatos.addButton(b)
            grade.addWidget(b, i // 3, i % 3)
        self._grupo_formatos.buttonClicked.connect(self._on_formato)
        manual.addLayout(grade)
        manual.addWidget(largura_livre(label("Vale para as folhas selecionadas. Para mudar só uma, clique nela antes.", "sub")))
        self.tabela_folhas = tabela(("FOLHA", "FORMATO"), {1: 110}, 0)
        self.tabela_folhas.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tabela_folhas.selectionModel().selectionChanged.connect(self._marcar_formato)
        manual.addWidget(self.tabela_folhas, 1)
        col.addWidget(self.painel_manual, 1)
        self.painel_manual.hide()

        self._espaco = QWidget()
        col.addWidget(self._espaco, 1)
        self.btn_manual = botao("ESCOLHER MANUALMENTE", "secundario")
        self.btn_manual.clicked.connect(self._alternar_manual)
        col.addWidget(self.btn_manual)

    def _show_preview(self, previa) -> None:
        self._escolhidos = {}
        self.formats_changed.emit({})
        self._folhas = [[nome, formato] for nome, formato in previa.sheets]
        self._atualizar_previa(previa)
        self.tabela_folhas.selectAll()
        self._marcar_formato()
        self._mostrar_manual(bool(self._folhas) and not self._folhas[0][1])

    def _atualizar_previa(self, previa=None) -> None:
        previa = previa or self._previa
        contagem: Dict[str, int] = {}
        for _, formato in self._folhas:
            if formato:
                contagem[formato] = contagem.get(formato, 0) + 1
        sem = sum(1 for _, f in self._folhas if not f)
        self.lbl_detectado.setText(" e ".join(contagem) or "Não detectado")
        partes = [f"{previa.doc_name}"] if len(contagem) < 2 else [f"{f}: {n} folha(s)" for f, n in contagem.items()]
        if len(contagem) < 2:
            partes.append(f"{len(self._folhas)} folha(s)")
        if sem and contagem:
            partes.append(f"{sem} sem formato: usa o da primeira")
        if self._escolhidos:
            partes.append("escolhido manualmente")
        self.lbl_detalhe_tamanho.setText("  ·  ".join(partes))
        # Com o tamanho escolhido a mao, quem confere o template e a propria conversao.
        problema = ""
        if not previa.pasta_ok:
            problema = "Pasta dos templates inacessível"
        elif previa.faltando and not self._escolhidos:
            problema = f"Template não encontrado: {', '.join(previa.faltando)}"
        self.linha_template.definir("erro", problema)
        self.linha_template.setVisible(bool(problema))
        preencher(self.tabela_folhas, [(n, f or "Sem formato") for n, f in self._folhas])

    def _mostrar_manual(self, mostrar: bool) -> None:
        self.painel_manual.setVisible(mostrar)
        self._espaco.setVisible(not mostrar)
        self.btn_manual.setText("USAR O TAMANHO DETECTADO" if mostrar else "ESCOLHER MANUALMENTE")

    def _alternar_manual(self) -> None:
        if self.painel_manual.isVisible():
            self._show_preview(self._previa)  # descarta o que foi escolhido
            self._mostrar_manual(False)
        else:
            self._mostrar_manual(True)

    def _linhas_selecionadas(self) -> List[int]:
        return sorted(i.row() for i in self.tabela_folhas.selectionModel().selectedRows() if i.row() < len(self._folhas))

    def _marcar_formato(self, *_args) -> None:
        """O botao marcado mostra o tamanho das folhas selecionadas, se for um so."""
        tamanhos = {self._folhas[i][1] for i in self._linhas_selecionadas()}
        self._grupo_formatos.setExclusive(False)
        for b in self._grupo_formatos.buttons():
            b.setChecked(tamanhos == {b.text()})
        self._grupo_formatos.setExclusive(True)

    def _on_formato(self, botao_formato) -> None:
        linhas = self._linhas_selecionadas()
        if not linhas:
            self.tabela_folhas.selectAll()
            linhas = self._linhas_selecionadas()
        for linha in linhas:
            self._folhas[linha][1] = botao_formato.text()
            self._escolhidos[self._folhas[linha][0]] = botao_formato.text()
        self.formats_changed.emit(dict(self._escolhidos))
        self._atualizar_previa()
        self._marcar_formato()

    def _build_results(self, col: QVBoxLayout) -> None:
        self.lbl_note = largura_livre(label("Confira o desenho e salve para confirmar.", "detalheForte"))
        col.addWidget(self.lbl_note)
        self.table = tabela(("FOLHA", "FORMATO"), {1: 120}, 0)
        col.addWidget(self.table, 1)
        caixa = moldura("detalhe")
        c = QVBoxLayout(caixa)
        c.setContentsMargins(14, 8, 14, 8)
        c.addWidget(label("AVISOS", "secao"))
        self.lbl_warnings = largura_livre(label("", "detalheFraco"))
        c.addWidget(self.lbl_warnings)
        self._warnings_box = caixa
        col.addWidget(caixa)

    def _show_report(self, report) -> None:
        self.lbl_sub.setText(f"{os.path.basename(report.doc_full_name)}  ·  {len(report.sheets)} folhas")
        preencher(self.table, report.sheets)
        self.lbl_warnings.setText("\n".join(f"• {a}" for a in report.warnings))
        self._warnings_box.setVisible(bool(report.warnings))


# ---------------------------------------------------------------------
# Symbol Shape Converter
# ---------------------------------------------------------------------
class SymbolShapePage(ToolPage):
    TOOL = "symbol"
    TITULO = "Symbol Shape Converter"
    DESCRICAO = (
        "Troca a ponta dos leaders dos textos pelo símbolo cheio: círculo transparente, círculo vazado e onda "
        "viram círculo cheio, e seta vazada vira seta cheia."
    )
    BOTAO = "CONVERTER OS SÍMBOLOS"
    BOTAO_DE_NOVO = "Converter de novo"
    ANDAMENTO = "Convertendo os símbolos"
    ICONE = "arrow"
    PODE_PARAR = False

    def _build_results(self, col: QVBoxLayout) -> None:
        self.lbl_note = largura_livre(label("", "detalheForte"))
        col.addWidget(self.lbl_note)
        self.table = tabela(("FOLHA", "CÍRCULOS", "SETAS"), {1: 110, 2: 110}, 0)
        col.addWidget(self.table, 1)

    def _build_side(self, col: QVBoxLayout) -> bool:
        col.addWidget(label("Resumo", "titulo"))
        self.resumo = Resumo(("Convertidos", "Círculos", "Setas", "Leaders lidos"))
        col.addWidget(self.resumo)
        col.addStretch(1)
        return True

    def _show_report(self, report) -> None:
        self.lbl_sub.setText(f"{report.doc_name}  ·  {len(report.sheets)} folhas")
        nota = "Confira o desenho e salve para confirmar." if report.convertidos else "O desenho não foi alterado."
        self.lbl_note.setText(f"{report.mensagem} {nota}")
        preencher(self.table, [(nome, c, s) for nome, c, s, _lidos in report.sheets])
        self.resumo.definir("Convertidos", report.convertidos, T.GREEN if report.convertidos else "")
        self.resumo.definir("Círculos", report.circulos)
        self.resumo.definir("Setas", report.setas)
        self.resumo.definir("Leaders lidos", report.leaders)


# ---------------------------------------------------------------------
# Splits
# ---------------------------------------------------------------------
class _SplitPage(ToolPage):
    ETIQUETA = "CRIA ARQUIVOS"
    TIPO_ETIQUETA = "cria"
    TEM_PREVIA = True

    def _cartao_arquivo(self, col: QVBoxLayout) -> None:
        caixa = moldura("kv")
        c = QHBoxLayout(caixa)
        c.setContentsMargins(14, 10, 14, 10)
        self.lbl_arquivo = largura_livre(label("", "detalheForte"))
        self.lbl_tamanho = label("", "titulo")
        c.addWidget(self.lbl_arquivo, 1)
        c.addWidget(self.lbl_tamanho)
        col.addWidget(caixa)

    def _build_results(self, col: QVBoxLayout) -> None:
        self.table = tabela(("ARQUIVO", "TAMANHO", "ENVIO"), {1: 90, 2: 150}, 0)
        col.addWidget(self.table, 1)

    def _build_side(self, col: QVBoxLayout) -> bool:
        col.addWidget(label("Resumo", "titulo"))
        self.resumo = Resumo(("Arquivos", "Maior arquivo", f"Acima de {LIMITE_ENVIO_MB} MB"))
        col.addWidget(self.resumo)
        col.addWidget(label("Pasta", "subtitulo2"))
        self.lbl_folder = largura_livre(label("", "detalheFraco"))
        col.addWidget(self.lbl_folder)
        col.addStretch(1)
        self.btn_folder = botao_grande("ABRIR A PASTA", "open")
        self.btn_folder.clicked.connect(lambda: abrir_pasta(self._report.folder if self._report else ""))
        col.addWidget(self.btn_folder)
        return True

    def _show_report(self, report) -> None:
        parou = "  ·  Parado antes do fim" if report.stopped else ""
        self.lbl_sub.setText(self._resumo(report) + parou)
        tamanhos = [sp._tamanho_mb(f) for f in report.files]
        preencher(self.table, [
            (os.path.basename(f), _mb(t), "Cabe no envio" if t <= LIMITE_ENVIO_MB else f"Acima de {LIMITE_ENVIO_MB} MB")
            for f, t in zip(report.files, tamanhos)
        ])
        self.resumo.definir("Arquivos", len(report.files))
        self.resumo.definir("Maior arquivo", _mb(max(tamanhos)) if tamanhos else "-")
        acima = sum(t > LIMITE_ENVIO_MB for t in tamanhos)
        self.resumo.definir(f"Acima de {LIMITE_ENVIO_MB} MB", acima, T.AMBER if acima else "")
        self.lbl_folder.setText(report.folder)
        self.lbl_folder.setToolTip(report.folder)


class Split2DPage(_SplitPage):
    TOOL = "split2d"
    TITULO = "Split 2D"
    DESCRICAO = "Exporta cada folha do desenho salvo para um CATDrawing próprio, numa pasta em Downloads."
    BOTAO = "DIVIDIR POR FOLHA"
    BOTAO_DE_NOVO = "Dividir de novo"
    ANDAMENTO = "Exportando as folhas"
    ICONE = "scissors"
    ICONE_BOTAO = "scissors"

    def _build_ready(self, col: QVBoxLayout) -> None:
        topo, sub = cabecalho(self.TITULO, etiqueta(self.ETIQUETA, self.TIPO_ETIQUETA))
        sub.setText(self.DESCRICAO)
        col.addLayout(topo)
        self._cartao_arquivo(col)
        col.addWidget(label("Folhas que viram arquivos", "subtitulo2"))
        self.tabela_previa = tabela(("FOLHA", "ARQUIVO"), {0: 220}, 1)
        col.addWidget(self.tabela_previa, 1)
        col.addWidget(largura_livre(label(
            "As vistas destravadas são travadas automaticamente. Só o que está salvo no arquivo vai para as folhas exportadas.",
            "notaTexto")))

    def _show_preview(self, previa) -> None:
        self.lbl_arquivo.setText(previa.doc_name)
        self.lbl_tamanho.setText(_mb(previa.size_mb))
        preencher(self.tabela_previa, [(f, sp.clean_file_name(f) + ".CATDrawing") for f in previa.sheets])

    def _resumo(self, report) -> str:
        travadas = f"  ·  {report.locked_views} vistas travadas" if report.locked_views else ""
        return f"{len(report.files)} folhas exportadas{travadas}"


class Split3DPage(_SplitPage):
    TOOL = "split3d"
    TITULO = "Split 3D"
    DESCRICAO = "Divide os Bodies do CATPart salvo em várias peças, na subpasta SPLIT_PARTS. O PartBody vai em todas."
    BOTAO = "DIVIDIR A PEÇA"
    BOTAO_DE_NOVO = "Dividir de novo"
    ANDAMENTO = "Criando as partes"
    EXTENSAO = ".catpart"
    NOME_DOCUMENTO = "CATPart"
    ICONE = "saw"
    ICONE_BOTAO = "saw"

    def _build_ready(self, col: QVBoxLayout) -> None:
        topo, sub = cabecalho(self.TITULO, etiqueta(self.ETIQUETA, self.TIPO_ETIQUETA))
        sub.setText(self.DESCRICAO)
        col.addLayout(topo)
        self._cartao_arquivo(col)
        linha = QHBoxLayout()
        linha.addWidget(label("Partes previstas", "subtitulo2"))
        linha.addStretch(1)
        linha.addWidget(label("Dividir em", "kvNome"))
        self.spin = QSpinBox()
        self.spin.setRange(2, 2)
        self.spin.setValue(2)
        self.spin.setFixedWidth(70)
        self.spin.valueChanged.connect(self._plano)
        linha.addWidget(self.spin)
        col.addLayout(linha)
        self.tabela_previa = tabela(("PARTE", "ARQUIVO", "BODIES"), {0: 70, 1: 260}, 2)
        col.addWidget(self.tabela_previa, 1)

    def _show_preview(self, previa) -> None:
        self.lbl_arquivo.setText(f"{previa.doc_name}  ·  PN {previa.pn}")
        self.lbl_tamanho.setText(_mb(previa.size_mb))
        total = len(previa.bodies)
        self.spin.setRange(2, max(2, total))
        self.spin.setEnabled(total >= 2)
        self._plano()

    def _plano(self) -> None:
        previa = self._previa
        if previa is None:
            return
        corpos = previa.bodies
        if not corpos:
            preencher(self.tabela_previa, [])
            self.btn_run.setEnabled(False)
            self.btn_run.setText("NENHUM BODY PARA DIVIDIR")
            return
        self.btn_run.setEnabled(True)
        partes = min(self.spin.value(), len(corpos))
        base = previa.doc_name[: previa.doc_name.rfind(".")]
        preencher(self.tabela_previa, [
            (n, f"{base}_P{n:02d}.CATPart", ", ".join(corpos[a - 1:b]))
            for n, (a, b) in enumerate(sp.split_ranges(len(corpos), partes), 1)
        ])
        self.btn_run.setText(self._texto_botao())

    def _texto_botao(self) -> str:
        return f"PARTIR EM {self.spin.value()} ARQUIVOS"

    def _perguntar(self, pergunta: str, titulo: str, sugestao: str) -> str:
        return str(self.spin.value())  # o numero de partes ja esta na tela

    def _resumo(self, report) -> str:
        return f"PN {report.pn}  ·  {report.bodies} Bodies  ·  {len(report.files)} arquivos"
