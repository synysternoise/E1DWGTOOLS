"""Telas do Update Template, do Position and Zone e dos dois Splits."""
from __future__ import annotations

import os
from typing import Dict, List

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QButtonGroup, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QSizePolicy, QSpinBox,
    QStackedWidget, QTableWidgetItem, QVBoxLayout,
)

from engine import atualizar_template as at
from engine import splits as sp
from ui_qt import theme as T
from ui_qt.font_size_page import PAPEL_OK, MarkDelegate, button, label
from ui_qt.pecas import (
    Cartao, LinhaSituacao, Resumo, botao, botao_grande, cabecalho, etiqueta, largura_livre, moldura,
)
from ui_qt.tool_page import ToolPage, abrir_arquivo, abrir_pasta, preencher, tabela

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
    BOTAO = "EXECUTAR UPDATE TEMPLATE"
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
        corpo = QHBoxLayout()
        corpo.setSpacing(18)

        esquerda = QVBoxLayout()
        esquerda.setSpacing(8)
        self.linha_desenho = LinhaSituacao()
        self.linha_formato = LinhaSituacao()
        self.linha_template = LinhaSituacao()
        for w in (self.linha_desenho, self.linha_formato, self.linha_template):
            esquerda.addWidget(w)
        esquerda.addSpacing(6)
        esquerda.addWidget(label("Resumo da análise", "subtitulo2"))
        self.resumo_previa = Resumo(("Documento", "Folhas", "Formatos", "Templates"))
        esquerda.addWidget(self.resumo_previa)
        esquerda.addStretch(1)
        corpo.addLayout(esquerda, 1)

        direita = QVBoxLayout()
        direita.setSpacing(8)
        direita.addWidget(label("Folhas e formatos", "subtitulo2"))
        self.tabela_folhas = tabela(("FOLHA", "FORMATO"), {1: 110}, 0)
        self.tabela_folhas.selectionModel().currentRowChanged.connect(self._on_folha)
        direita.addWidget(self.tabela_folhas, 1)
        self.lbl_pergunta = largura_livre(label("", "subtitulo2"))
        direita.addWidget(self.lbl_pergunta)
        grade = QGridLayout()
        grade.setSpacing(6)
        self._grupo_formatos = QButtonGroup(self)
        for i, formato in enumerate(at.FORMATOS):
            b = button(formato, "formato")
            b.setCheckable(True)
            self._grupo_formatos.addButton(b)
            grade.addWidget(b, i // 3, i % 3)
        self._grupo_formatos.buttonClicked.connect(self._on_formato)
        direita.addLayout(grade)
        corpo.addLayout(direita, 1)
        col.addLayout(corpo, 1)

    def _show_preview(self, previa) -> None:
        self._escolhidos = {}
        self.formats_changed.emit({})
        self._folhas = [[nome, formato] for nome, formato in previa.sheets]
        self.linha_desenho.definir("ok", f"Desenho detectado: {previa.doc_name}")
        self._atualizar_previa(previa)
        self.tabela_folhas.selectRow(0)

    def _atualizar_previa(self, previa=None) -> None:
        previa = previa or self._previa
        sem = [n for n, f in self._folhas if not f]
        if sem:
            self.linha_formato.definir("aviso", f"{len(sem)} folha(s) sem formato: usa a primeira ou pergunta")
        else:
            self.linha_formato.definir("ok", "Formato lido em todas as folhas")
        if not previa.pasta_ok:
            self.linha_template.definir("erro", "Pasta dos templates inacessível")
        elif previa.faltando:
            self.linha_template.definir("erro", f"Template não encontrado: {', '.join(previa.faltando)}")
        elif previa.encontrados:
            self.linha_template.definir("ok", f"Templates {' e '.join(previa.encontrados)} encontrados")
        else:
            self.linha_template.definir("neutro", "Template: depende do formato")
        formatos = list(dict.fromkeys(f for _, f in self._folhas if f))
        self.resumo_previa.definir("Documento", previa.doc_name)
        self.resumo_previa.definir("Folhas", len(self._folhas))
        self.resumo_previa.definir("Formatos", ", ".join(formatos) or "-")
        self.resumo_previa.definir("Templates", f"{len(previa.encontrados)} de {len(previa.encontrados) + len(previa.faltando)}")
        preencher(self.tabela_folhas, [(n, f or "Sem formato") for n, f in self._folhas])

    def _on_folha(self, atual, _anterior) -> None:
        if not atual.isValid() or atual.row() >= len(self._folhas):
            return
        nome, formato = self._folhas[atual.row()]
        self.lbl_pergunta.setText(f"O formato de {nome} está correto?")
        self._grupo_formatos.setExclusive(False)
        for b in self._grupo_formatos.buttons():
            b.setChecked(b.text() == formato)
        self._grupo_formatos.setExclusive(True)

    def _on_formato(self, botao_formato) -> None:
        linha = self.tabela_folhas.currentRow()
        if linha < 0:
            return
        self._folhas[linha][1] = botao_formato.text()
        self._escolhidos[self._folhas[linha][0]] = botao_formato.text()
        self.formats_changed.emit(dict(self._escolhidos))
        self._atualizar_previa()
        self.tabela_folhas.selectRow(linha)

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
# Position and Zone
# ---------------------------------------------------------------------
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
    TIPO_ETIQUETA = "confere"
    ICONE = "box"
    PODE_PARAR = False  # sem todas as folhas, as quantidades somadas ficariam erradas

    go_requested = Signal(object, object, int)
    latest_nav = Signal(int)

    def __init__(self):
        self._pendencias = []
        self._atual = -1
        self._pedido = 0
        super().__init__()

    def _build_results(self, col: QVBoxLayout) -> None:
        cartoes = QHBoxLayout()
        cartoes.setSpacing(8)
        self.card_validos = Cartao("válidos", "verde")
        self.card_grupo = Cartao("grupo ou ambíguo", "ambar")
        self.card_conflito = Cartao("inconsistentes", "vermelho")
        for c in (self.card_validos, self.card_grupo, self.card_conflito):
            cartoes.addWidget(c, 1)
        col.addLayout(cartoes)

        filtros = QHBoxLayout()
        filtros.setSpacing(6)
        self._grupo = QButtonGroup(self)
        self.btn_pendencias = button("", "filtro")
        self.btn_todos = button("", "filtro")
        for i, b in enumerate((self.btn_pendencias, self.btn_todos)):
            b.setCheckable(True)
            self._grupo.addButton(b, i)
            filtros.addWidget(b)
        filtros.addStretch(1)
        self._grupo.idClicked.connect(self._on_filtro)
        col.addLayout(filtros)

        self._pilha = QStackedWidget()
        self.tabela_pendencias = tabela(("", "FOLHA", "VISTA", "CALLOUT", "MOTIVO"), {0: 40, 1: 110, 2: 110, 3: 90}, 4)
        self.tabela_pendencias.setItemDelegateForColumn(0, MarkDelegate(self.tabela_pendencias))
        self.tabela_pendencias.selectionModel().currentRowChanged.connect(self._on_linha)
        self.table = tabela(("POSIÇÃO", "ZONA", "QTD", "ONDE"), {0: 76, 1: 140, 2: 50}, 3)
        self._pilha.addWidget(self.tabela_pendencias)
        self._pilha.addWidget(self.table)
        col.addWidget(self._pilha, 1)

        detalhe = moldura("detalhe")
        d = QHBoxLayout(detalhe)
        d.setContentsMargins(14, 8, 14, 8)
        textos = QVBoxLayout()
        textos.setSpacing(0)
        self.lbl_detail = largura_livre(label("", "detalheForte"))
        self.lbl_where = largura_livre(label("", "detalheFraco"))
        textos.addWidget(self.lbl_detail)
        textos.addWidget(self.lbl_where)
        d.addLayout(textos, 1)
        self.lbl_nav_state = label("", "chipEstado")
        d.addWidget(self.lbl_nav_state)
        self._detalhe = detalhe
        col.addWidget(detalhe)

        nav = QHBoxLayout()
        self.btn_prev = botao("ANTERIOR", "secundario", "left")
        self.btn_next = botao("PRÓXIMO", "primario", "right", T.CYAN_INK)
        self.btn_next.setLayoutDirection(Qt.RightToLeft)
        self.lbl_pos = label("", "posicao")
        self.lbl_pos.setAlignment(Qt.AlignCenter)
        self.btn_prev.clicked.connect(lambda: self._mover(-1))
        self.btn_next.clicked.connect(lambda: self._mover(1))
        nav.addWidget(self.btn_prev, 2)
        nav.addWidget(self.lbl_pos, 1)
        nav.addWidget(self.btn_next, 2)
        self._nav = QFrame()
        self._nav.setLayout(nav)
        col.addWidget(self._nav)

    def _build_side(self, col: QVBoxLayout) -> bool:
        col.addWidget(label("Resumo", "titulo"))
        self.resumo = Resumo(("Objetos válidos", "Linhas multilinha", "Ignoradas por REF", "Quantidades por chave", "Callouts no Excel"))
        col.addWidget(self.resumo)
        col.addWidget(label("Planilha", "subtitulo2"))
        self.lbl_planilha = largura_livre(label("", "detalheFraco"))
        col.addWidget(self.lbl_planilha)
        col.addWidget(largura_livre(label(
            "Cópia temporária. Salve com outro nome para guardar. A comparação com a Part List continua no Excel.",
            "notaTexto")))
        col.addStretch(1)
        self.btn_excel = botao_grande("ABRIR NO EXCEL", "open")
        self.btn_excel.clicked.connect(lambda: abrir_arquivo(self._report.workbook_path if self._report else ""))
        col.addWidget(self.btn_excel)
        return True

    def _show_report(self, report) -> None:
        c = report.counters
        self.lbl_sub.setText(f"PN {report.pn}  ·  {report.occurrences - c.referencias} ocorrências válidas")
        self.card_validos.valor(c.validos)
        self.card_grupo.valor(c.grupo)
        self.card_conflito.valor(c.conflito)
        for nome, valor in (("Objetos válidos", c.validos), ("Linhas multilinha", c.multilinha), ("Ignoradas por REF", c.referencias),
                            ("Quantidades por chave", c.chaves), ("Callouts no Excel", len(report.callouts))):
            self.resumo.definir(nome, valor)
        self.lbl_planilha.setText(os.path.basename(report.workbook_path))
        self.lbl_planilha.setToolTip(report.workbook_path)
        self.btn_pendencias.setText(f"Pendências ({len(report.pendencias)})")
        self.btn_todos.setText(f"Todos os callouts ({len(report.callouts)})")
        linhas = sorted(report.callouts, key=lambda x: float(x.number))
        preencher(self.table, [(x.number, x.zone, x.qty, f"{x.sheet} - {x.view}") for x in linhas])
        self._pendencias = list(report.pendencias)
        self.tabela_pendencias.blockSignals(True)
        self.tabela_pendencias.selectionModel().blockSignals(True)
        preencher(self.tabela_pendencias, [("", p.sheet_name, p.view_name, p.number, p.motivo) for p in self._pendencias])
        for i in range(len(self._pendencias)):
            marca = QTableWidgetItem()
            marca.setData(PAPEL_OK, False)
            self.tabela_pendencias.setItem(i, 0, marca)
        self.tabela_pendencias.selectionModel().blockSignals(False)
        self.tabela_pendencias.blockSignals(False)
        self._atual = -1
        (self.btn_pendencias if self._pendencias else self.btn_todos).setChecked(True)
        self._on_filtro(0 if self._pendencias else 1)

    def _on_filtro(self, filtro: int) -> None:
        self._pilha.setCurrentIndex(filtro)
        pendencias = filtro == 0
        self._nav.setVisible(pendencias and bool(self._pendencias))
        self._detalhe.setVisible(pendencias)
        if pendencias:
            if self._pendencias:
                if self.tabela_pendencias.currentRow() < 0:
                    self.tabela_pendencias.selectRow(0)
                    self.tabela_pendencias.setCurrentCell(0, 3)
            else:
                self.lbl_detail.setText("Nenhuma pendência: todos os callouts foram contabilizados")
                self.lbl_where.setText("")
                self.lbl_pos.setText("")
                self.lbl_nav_state.setText("")

    def _on_linha(self, atual, _anterior) -> None:
        if atual.isValid():
            self._ir(atual.row())

    def _ir(self, linha: int) -> None:
        self._atual = linha
        p = self._pendencias[linha]
        self.lbl_pos.setText(f"{linha + 1} de {len(self._pendencias)}")
        self.lbl_detail.setText(f"{p.motivo}, não contabilizado")
        self.lbl_where.setText(f"{p.sheet_name} › {p.view_name} › callout {p.number}")
        self._estado("Indo até o callout", T.AMBER)
        self._pedido += 1
        self.latest_nav.emit(self._pedido)
        self.go_requested.emit(self._report, p, self._pedido)

    def on_nav_done(self, pedido: int, ok: bool) -> None:
        if pedido != self._pedido:
            return
        if ok:
            self._estado("Selecionado no CATIA", T.GREEN)
        else:
            self._estado("", T.RED)
            self.lbl_detail.setText("Callout não encontrado: foi apagado ou o desenho foi fechado.")

    def _estado(self, texto: str, cor: str) -> None:
        self.lbl_nav_state.setText(f"●  {texto}" if texto else "")
        self.lbl_nav_state.setStyleSheet(f"color: {cor};")

    def _mover(self, passo: int) -> None:
        if self._pendencias:
            linha = (self._atual + passo) % len(self._pendencias)
            if linha == self._atual:
                self._ir(linha)
            else:
                self.tabela_pendencias.setCurrentCell(linha, 3)


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
