"""Check de Flags (so confere) e Font Size Fix (corrige, item por item ou todos)."""
from __future__ import annotations

from typing import Dict, List

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QBoxLayout, QButtonGroup, QFileDialog, QFrame, QHBoxLayout, QTableWidgetItem, QVBoxLayout, QWidget

from engine import compare_dwg as cd
from engine import fix_flags as ff
from engine import font_check as fc
from engine import template_check as tc
from ui_qt import theme as T
from ui_qt.fix_flags_page import mostrar
from ui_qt.font_size_page import PAPEL_OK, MarkDelegate, button, label
from ui_qt.pecas import Cartao, LinhaSituacao, Resumo, botao, botao_grande, icone_grande, largura_livre, moldura
from ui_qt.tool_page import LARGURA_LATERAL, ToolPage, tabela

PENDENTE, CORRIGIDO, COMO_ESTAVA, FALHOU, SO_NO_CATIA = "Pendente", "Corrigido", "Como estava", "Falhou", "Cota: corrija no CATIA"


class FlagCheckPage(ToolPage):
    """Mesmas regras do Fix Flags, sem gravar nada no desenho."""

    TOOL = "flagcheck"
    TITULO = "Check de Flags"
    DESCRICAO = "Confere se as flag notes estão no padrão, como NL0006. O desenho não é alterado."
    BOTAO = "CONFERIR AS FLAGS"
    BOTAO_DE_NOVO = "Conferir de novo"
    ANDAMENTO = "Conferindo as flags"
    ETIQUETA = "SÓ CONFERE"
    TIPO_ETIQUETA = "confere"
    ICONE = "flag"

    go_requested = Signal(object, object, int)
    latest_nav = Signal(int)
    corrigir_requested = Signal()

    def __init__(self):
        self._rows: List = []
        self._atual = -1
        self._pedido = 0
        super().__init__()

    def _build_results(self, col: QVBoxLayout) -> None:
        cartoes = QHBoxLayout()
        cartoes.setSpacing(8)
        self.card_erradas = Cartao("para corrigir", "vermelho")
        self.card_certas = Cartao("corretas", "verde")
        self.card_lidas = Cartao("flags lidas")
        for c in (self.card_erradas, self.card_certas, self.card_lidas):
            cartoes.addWidget(c, 1)
        col.addLayout(cartoes)
        filtros = QHBoxLayout()
        filtros.setSpacing(6)
        self._grupo = QButtonGroup(self)
        self.btn_erradas = button("", "filtro")
        self.btn_certas = button("", "filtro")
        self.btn_todas = button("", "filtro")
        for i, b in enumerate((self.btn_erradas, self.btn_certas, self.btn_todas)):
            b.setCheckable(True)
            self._grupo.addButton(b, i)
            filtros.addWidget(b)
        filtros.addStretch(1)
        self._grupo.idClicked.connect(lambda _: self._preencher())
        col.addLayout(filtros)
        self.table = tabela(("", "FOLHA", "VISTA", "TEXTO", "DEVERIA SER", "TIPO"), {0: 40, 1: 90, 3: 90, 4: 90, 5: 120}, 2)
        self.table.setItemDelegateForColumn(0, MarkDelegate(self.table))
        self.table.selectionModel().currentRowChanged.connect(self._on_linha)
        col.addWidget(self.table, 1)
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
        col.addLayout(nav)

    def _build_side(self, col: QVBoxLayout) -> bool:
        col.addWidget(label("Resumo", "titulo"))
        self.resumo = Resumo(("Textos analisados", "Flags lidas", "No objeto inteiro", "Pelo Text Editor", "Fixas com cadeado", "Corretas", "Para corrigir", "Ignorados", "Erros"))
        col.addWidget(self.resumo)
        col.addStretch(1)
        self.btn_corrigir = botao_grande("CORRIGIR NO FIX FLAGS", "flag")
        self.btn_corrigir.clicked.connect(self.corrigir_requested)
        col.addWidget(self.btn_corrigir)
        return True

    def _show_report(self, report) -> None:
        parou = "  ·  Parado antes do fim" if report.stopped else ""
        self.lbl_sub.setText(f"{report.textos} textos analisados  ·  {report.flags} flags{parou}")
        self.card_erradas.valor(report.erradas)
        self.card_certas.valor(report.certas)
        self.card_lidas.valor(report.flags)
        for nome, valor, cor in (
            ("Textos analisados", report.textos, ""), ("Flags lidas", report.flags, ""), ("No objeto inteiro", report.objeto, ""),
            ("Pelo Text Editor", report.text_editor, ""), ("Fixas com cadeado", report.cadeado, ""),
            ("Corretas", report.certas, T.GREEN if report.certas else ""), ("Para corrigir", report.erradas, T.RED if report.erradas else ""),
            ("Ignorados", report.ignoradas, ""), ("Erros", report.erros, T.RED if report.erros else ""),
        ):
            self.resumo.definir(nome, valor, cor)
        self.btn_erradas.setText(f"Para corrigir ({report.erradas})")
        self.btn_certas.setText(f"Corretas ({report.certas})")
        self.btn_todas.setText(f"Todas ({len(report.items)})")
        self.btn_corrigir.setEnabled(report.erradas > 0)
        (self.btn_erradas if report.erradas else self.btn_todas).setChecked(True)
        self._preencher()

    def _preencher(self) -> None:
        filtro = self._grupo.checkedId()
        itens = self._report.items
        self._rows = [i for i in itens if (filtro == 2 or (i.ok if filtro == 1 else not i.ok))]
        self._atual = -1
        self.table.blockSignals(True)
        self.table.selectionModel().blockSignals(True)
        self.table.clearContents()
        self.table.setRowCount(len(self._rows))
        for n, it in enumerate(self._rows):
            marca = QTableWidgetItem()
            marca.setData(PAPEL_OK, it.ok)
            self.table.setItem(n, 0, marca)
            for coluna, texto in ((1, it.sheet_name), (2, it.view_name), (3, mostrar(it.before)), (4, "" if it.ok else it.after), (5, it.tipo)):
                cel = QTableWidgetItem(texto)
                cel.setToolTip(texto)
                self.table.setItem(n, coluna, cel)
        self.table.selectionModel().blockSignals(False)
        self.table.blockSignals(False)
        if self._rows:
            self.table.setCurrentCell(0, 2)
        else:
            self.lbl_pos.setText("")
            self.lbl_nav_state.setText("")
            self.lbl_detail.setText("Nenhuma flag nesta lista")
            self.lbl_where.setText("")
        self.btn_prev.setEnabled(bool(self._rows))
        self.btn_next.setEnabled(bool(self._rows))

    def _on_linha(self, atual, _a) -> None:
        if atual.isValid():
            self._ir(atual.row())

    def _ir(self, linha: int) -> None:
        self._atual = linha
        it = self._rows[linha]
        self.lbl_pos.setText(f"{linha + 1} de {len(self._rows)}")
        self.lbl_detail.setText("Correta" if it.ok else f"{mostrar(it.before)}  ›  deveria ser {it.after}")
        self.lbl_where.setText(f"{it.sheet_name} › {it.view_name} › {it.tipo}")
        self._estado("Indo até a flag", T.AMBER)
        self._pedido += 1
        self.latest_nav.emit(self._pedido)
        self.go_requested.emit(self._report, it, self._pedido)

    def on_nav_done(self, pedido: int, ok: bool) -> None:
        if pedido != self._pedido:
            return
        if ok:
            self._estado("Selecionada no CATIA", T.GREEN)
        else:
            self._estado("", T.RED)
            self.lbl_detail.setText("Flag não encontrada: foi apagada ou o desenho foi fechado.")

    def _estado(self, texto: str, cor: str) -> None:
        self.lbl_nav_state.setText(f"●  {texto}" if texto else "")
        self.lbl_nav_state.setStyleSheet(f"color: {cor};")

    def _mover(self, passo: int) -> None:
        if self._rows:
            linha = (self._atual + passo) % len(self._rows)
            if linha == self._atual:
                self._ir(linha)
            else:
                self.table.setCurrentCell(linha, 2)


class TemplateCheckPage(ToolPage):
    """Numeracao, formato e escala da legenda de cada folha, sem gravar nada no desenho."""

    TOOL = "templatecheck"
    TITULO = "Check de Template"
    DESCRICAO = (
        "Confere a legenda de cada folha: numeração (primeira folha 1/total, as outras só o número), "
        "formato contra o papel e escala contra as vistas. O desenho não é alterado."
    )
    BOTAO = "CONFERIR O TEMPLATE"
    BOTAO_DE_NOVO = "Conferir de novo"
    ANDAMENTO = "Conferindo o template"
    ETIQUETA = "SÓ CONFERE"
    TIPO_ETIQUETA = "confere"
    ICONE = "file"

    go_requested = Signal(object, object, int)
    latest_nav = Signal(int)

    def __init__(self):
        self._rows: List = []
        self._atual = -1
        self._pedido = 0
        super().__init__()

    def _build_results(self, col: QVBoxLayout) -> None:
        cartoes = QHBoxLayout()
        cartoes.setSpacing(8)
        self.card_errados = Cartao("errados", "vermelho")
        self.card_conferir = Cartao("para conferir", "ambar")
        self.card_certos = Cartao("certos", "verde")
        for c in (self.card_errados, self.card_conferir, self.card_certos):
            cartoes.addWidget(c, 1)
        col.addLayout(cartoes)
        filtros = QHBoxLayout()
        filtros.setSpacing(6)
        self._grupo = QButtonGroup(self)
        self.btn_revisar = button("", "filtro")
        self.btn_certos = button("", "filtro")
        self.btn_todos = button("", "filtro")
        for i, b in enumerate((self.btn_revisar, self.btn_certos, self.btn_todos)):
            b.setCheckable(True)
            self._grupo.addButton(b, i)
            filtros.addWidget(b)
        filtros.addStretch(1)
        self._grupo.idClicked.connect(lambda _: self._preencher())
        col.addLayout(filtros)
        self.table = tabela(("", "FOLHA", "CONFERÊNCIA", "LIDO", "ESPERADO", "SITUAÇÃO"), {0: 40, 1: 110, 3: 130, 4: 130, 5: 100}, 2)
        self.table.setItemDelegateForColumn(0, MarkDelegate(self.table))
        self.table.selectionModel().currentRowChanged.connect(self._on_linha)
        col.addWidget(self.table, 1)
        detalhe = moldura("detalhe")
        d = QHBoxLayout(detalhe)
        d.setContentsMargins(14, 8, 14, 8)
        textos = QVBoxLayout()
        textos.setSpacing(0)
        self.lbl_detail = largura_livre(label("", "detalheForte"))
        self.lbl_detail.setWordWrap(True)
        self.lbl_where = largura_livre(label("", "detalheFraco"))
        self.lbl_where.setWordWrap(True)
        textos.addWidget(self.lbl_detail)
        textos.addWidget(self.lbl_where)
        d.addLayout(textos, 1)
        self.lbl_nav_state = label("", "chipEstado")
        d.addWidget(self.lbl_nav_state)
        col.addWidget(detalhe)

    def _show_report(self, report) -> None:
        parou = "  ·  Parado antes do fim" if report.stopped else ""
        self.lbl_sub.setText(f"{report.total_folhas} folhas{parou}")
        self.card_errados.valor(report.errados)
        self.card_conferir.valor(report.conferir)
        self.card_certos.valor(report.certos)
        revisar = report.errados + report.conferir
        self.btn_revisar.setText(f"Para revisar ({revisar})")
        self.btn_certos.setText(f"Certos ({report.certos})")
        self.btn_todos.setText(f"Todos ({len(report.items)})")
        (self.btn_revisar if revisar else self.btn_todos).setChecked(True)
        self._preencher()

    def _preencher(self) -> None:
        filtro = self._grupo.checkedId()
        itens = self._report.items
        self._rows = [i for i in itens if filtro == 2 or ((i.situacao == tc.CERTO) == (filtro == 1))]
        self._atual = -1
        self.table.blockSignals(True)
        self.table.selectionModel().blockSignals(True)
        self.table.clearContents()
        self.table.setRowCount(len(self._rows))
        for n, it in enumerate(self._rows):
            marca = QTableWidgetItem()
            marca.setData(PAPEL_OK, None if it.situacao == tc.CONFERIR else it.situacao == tc.CERTO)
            self.table.setItem(n, 0, marca)
            for coluna, texto in ((1, it.sheet_name), (2, it.regra), (3, it.lido or "(vazio)"), (4, it.esperado), (5, it.situacao)):
                cel = QTableWidgetItem(texto)
                cel.setToolTip(it.detalhe or texto)
                self.table.setItem(n, coluna, cel)
        self.table.selectionModel().blockSignals(False)
        self.table.blockSignals(False)
        if self._rows:
            self.table.setCurrentCell(0, 2)
        else:
            self.lbl_nav_state.setText("")
            self.lbl_detail.setText("Nenhum item nesta lista")
            self.lbl_where.setText("")

    def _on_linha(self, atual, _a) -> None:
        if atual.isValid():
            self._ir(atual.row())

    def _ir(self, linha: int) -> None:
        self._atual = linha
        it = self._rows[linha]
        lido = it.lido or "(vazio)"
        if it.situacao == tc.CERTO:
            self.lbl_detail.setText(f"{it.regra}: {lido}, certo")
        elif it.esperado:
            self.lbl_detail.setText(f"{it.regra}: {lido}  ›  esperado {it.esperado}")
        else:
            self.lbl_detail.setText(f"{it.regra}: {lido}")
        self.lbl_where.setText(it.detalhe)
        self._estado("Indo até a folha", T.AMBER)
        self._pedido += 1
        self.latest_nav.emit(self._pedido)
        self.go_requested.emit(self._report, it, self._pedido)

    def on_nav_done(self, pedido: int, ok: bool) -> None:
        if pedido != self._pedido:
            return
        if ok:
            self._estado("Folha aberta no CATIA", T.GREEN)
        else:
            self._estado("Folha não encontrada", T.RED)

    def _estado(self, texto: str, cor: str) -> None:
        self.lbl_nav_state.setText(f"●  {texto}" if texto else "")
        self.lbl_nav_state.setStyleSheet(f"color: {cor};")

    def set_compact(self, compact: bool) -> None:
        """No compacto, o que a legenda tem e o esperado continuam visiveis: sao o resultado."""
        super().set_compact(compact)
        self.table.setColumnHidden(5, compact)
        for coluna, normal, estreita in ((1, 110, 66), (3, 130, 76), (4, 130, 76)):
            self.table.setColumnWidth(coluna, estreita if compact else normal)


class FontSizeFixPage(ToolPage):
    """Mostra o que esta fora do padrao para a pessoa corrigir. Muda so o tamanho."""

    TOOL = "fontfix"
    TITULO = "Font Size Fix"
    DESCRICAO = (
        "Mostra os textos fora do padrão da folha para você corrigir um por um. Muda só o tamanho. "
        "Vista travada é destravada só na troca e travada de novo. Main View, Background e ocultos ficam de fora."
    )
    BOTAO = "ANALISAR AS FONTES"
    BOTAO_DE_NOVO = "Analisar de novo"
    ANDAMENTO = "Analisando as fontes"
    ICONE = "sheet"

    go_requested = Signal(object, object, int)
    latest_nav = Signal(int)
    fix_requested = Signal(object, object)

    def __init__(self):
        self._rows: List = []
        self._atual = -1
        self._pedido = 0
        self._situacao: Dict[int, str] = {}
        self._alvo: Dict[int, float] = {}
        self._era: Dict[int, str] = {}
        self._removidos = 0
        self._sep = "."
        super().__init__()

    def _build_results(self, col: QVBoxLayout) -> None:
        self.table = tabela(("", "TEXTO / COTA", "FOLHA", "ATUAL", "PADRÃO DA FOLHA", "SITUAÇÃO"), {0: 40, 2: 84, 3: 70, 4: 150, 5: 92}, 1)
        self.table.setItemDelegateForColumn(0, MarkDelegate(self.table))
        self.table.selectionModel().currentRowChanged.connect(self._on_linha)
        col.addWidget(self.table, 1)
        col.addWidget(largura_livre(label("Muda só o tamanho. Background, vistas travadas, vistas ocultas e itens ocultos ficam de fora.", "notaTexto")))

    def _build_side(self, col: QVBoxLayout) -> bool:
        topo = QHBoxLayout()
        topo.addWidget(label("ITEM ATUAL", "secao"))
        topo.addStretch(1)
        self.lbl_pos = label("", "subtitulo2")
        topo.addWidget(self.lbl_pos)
        col.addLayout(topo)
        self.lbl_item = largura_livre(label("", "titulo"))
        col.addWidget(self.lbl_item)
        self.lbl_where = largura_livre(label("", "detalheFraco"))
        col.addWidget(self.lbl_where)
        self.lbl_nav_state = label("", "chipEstado")
        col.addWidget(self.lbl_nav_state)
        caixa = moldura("kv")
        c = QVBoxLayout(caixa)
        c.setContentsMargins(12, 8, 12, 10)
        c.setSpacing(4)
        self.lbl_atual = label("", "subtitulo2")
        c.addWidget(self.lbl_atual)
        c.addWidget(label("CORRIGIR PARA", "kvNome"))
        linha = QHBoxLayout()
        linha.setSpacing(6)
        self._grupo_alvo = QButtonGroup(self)
        self.btn_alvo = []
        for i in range(2):
            b = button("", "formato")
            b.setCheckable(True)
            self._grupo_alvo.addButton(b, i)
            linha.addWidget(b)
            self.btn_alvo.append(b)
        self._grupo_alvo.idClicked.connect(self._on_alvo)
        c.addLayout(linha)
        col.addWidget(caixa)
        self.btn_fix = botao_grande("CORRIGIR ESTE", "check")
        self.btn_fix.clicked.connect(self._corrigir_este)
        col.addWidget(self.btn_fix)
        self.btn_keep = botao("DEIXAR COMO ESTÁ", "secundario")
        self.btn_keep.clicked.connect(self._deixar)
        col.addWidget(self.btn_keep)
        nav = QHBoxLayout()
        self.btn_prev = botao("ANTERIOR", "secundario", "left")
        self.btn_next = botao("PRÓXIMO", "secundario", "right")
        self.btn_next.setLayoutDirection(Qt.RightToLeft)
        self.btn_prev.clicked.connect(lambda: self._mover(-1))
        self.btn_next.clicked.connect(lambda: self._mover(1))
        nav.addWidget(self.btn_prev)
        nav.addWidget(self.btn_next)
        col.addLayout(nav)
        col.addStretch(1)
        self.resumo = Resumo(("Corrigidos", "Como estava", "Pendentes"))
        col.addWidget(self.resumo)
        self.btn_remove = botao("REMOVER ESTE TEXTO DA LISTA", "secundario")
        self.btn_remove.setToolTip("Tira da lista um texto que não precisa ser conferido. Não altera o desenho.")
        self.btn_remove.clicked.connect(self._remover)
        col.addWidget(self.btn_remove)
        return True

    def _show_report(self, report) -> None:
        self._sep = fc.windows_decimal_separator()
        self._rows = list(report.items)
        self._situacao = {}
        self._alvo = {}
        self._era = {}
        for it in self._rows:
            self._situacao[it.order] = SO_NO_CATIA if it.is_dim else PENDENTE
            self._alvo[it.order] = fc.closest_standard(it)
        self._removidos = 0
        self._legenda()
        self._atual = -1
        self._preencher()
        if self._rows:
            self.table.setCurrentCell(0, 1)
        else:
            self.lbl_item.setText("Tudo dentro do padrão")
            self.lbl_where.setText("")
            self.lbl_pos.setText("")
            self.lbl_atual.setText("")
            self.lbl_nav_state.setText("")
            for b in self.btn_alvo:
                b.setText("")
        self._atualizar_botoes()

    def _legenda(self) -> None:
        report = self._report
        parou = "  ·  Parado antes do fim" if report.stopped else ""
        ocultos = f"  ·  {report.nota_ocultos}" if report.total_hidden else ""
        removidos = f"  ·  {self._removidos} removidos da lista" if self._removidos else ""
        self.lbl_sub.setText(
            f"{report.total_nok - self._removidos} fora do padrão de {report.total_items} itens{ocultos}{removidos}"
            f"  ·  Formato {', '.join(report.formats)}{parou}"
        )

    def _preencher(self) -> None:
        self.table.blockSignals(True)
        self.table.selectionModel().blockSignals(True)
        self.table.clearContents()
        self.table.setRowCount(len(self._rows))
        for n, it in enumerate(self._rows):
            situacao = self._situacao[it.order]
            marca = QTableWidgetItem()
            marca.setData(PAPEL_OK, situacao == CORRIGIDO)
            self.table.setItem(n, 0, marca)
            atual = it.size + (f"  (era {self._era[it.order]})" if it.order in self._era else "")
            for coluna, texto in ((1, it.text), (2, it.sheet_name), (3, atual), (4, it.standard), (5, situacao)):
                cel = QTableWidgetItem(texto)
                cel.setToolTip(texto)
                self.table.setItem(n, coluna, cel)
        self.table.selectionModel().blockSignals(False)
        self.table.blockSignals(False)
        if 0 <= self._atual < len(self._rows):
            self.table.selectRow(self._atual)

    def _atualizar_botoes(self) -> None:
        contagem = [self._situacao[i.order] for i in self._rows]
        self.resumo.definir("Corrigidos", contagem.count(CORRIGIDO), T.GREEN if CORRIGIDO in contagem else "")
        self.resumo.definir("Como estava", contagem.count(COMO_ESTAVA))
        pendentes = contagem.count(PENDENTE) + contagem.count(FALHOU)
        self.resumo.definir("Pendentes", pendentes, T.AMBER if pendentes else "")
        tem = 0 <= self._atual < len(self._rows)
        self.btn_remove.setEnabled(tem)
        pode = tem and self._situacao[self._rows[self._atual].order] in (PENDENTE, COMO_ESTAVA, FALHOU)
        self.btn_fix.setEnabled(pode)
        self.btn_keep.setEnabled(pode)
        for b in self.btn_alvo:
            b.setEnabled(pode)
        self.btn_prev.setEnabled(bool(self._rows))
        self.btn_next.setEnabled(bool(self._rows))

    def _on_linha(self, atual, _a) -> None:
        if atual.isValid():
            self._ir(atual.row())

    def _ir(self, linha: int) -> None:
        self._atual = linha
        it = self._rows[linha]
        self.lbl_pos.setText(f"{linha + 1} de {len(self._rows)}")
        self.lbl_item.setText(it.text)
        self.lbl_where.setText(f"{it.sheet_name} › {it.view_name} · {it.standard}")
        self.lbl_atual.setText(f"Atual: {it.size}")
        for b, padrao in zip(self.btn_alvo, it.padroes):
            b.setText(fc.format_inch(padrao, self._sep))
            b.setChecked(padrao == self._alvo[it.order])
        self._estado("Indo até o item", T.AMBER)
        self._pedido += 1
        self.latest_nav.emit(self._pedido)
        self.go_requested.emit(self._report, it, self._pedido)
        self._atualizar_botoes()

    def _on_alvo(self, indice: int) -> None:
        if 0 <= self._atual < len(self._rows):
            it = self._rows[self._atual]
            self._alvo[it.order] = it.padroes[indice]

    def on_nav_done(self, pedido: int, ok: bool) -> None:
        if pedido != self._pedido:
            return
        if ok:
            self._estado("Selecionado no CATIA", T.GREEN)
        else:
            self._estado("Item não encontrado", T.RED)

    def _estado(self, texto: str, cor: str) -> None:
        self.lbl_nav_state.setText(f"●  {texto}" if texto else "")
        self.lbl_nav_state.setStyleSheet(f"color: {cor};")

    def _mover(self, passo: int) -> None:
        if self._rows:
            linha = (self._atual + passo) % len(self._rows)
            if linha == self._atual:
                self._ir(linha)
            else:
                self.table.setCurrentCell(linha, 1)

    def _corrigir_este(self) -> None:
        if 0 <= self._atual < len(self._rows):
            it = self._rows[self._atual]
            self._pedir_correcao([(it, self._alvo[it.order])])

    def _remover(self) -> None:
        """Tira da lista um texto que nao precisa ser conferido. O desenho nao muda."""
        if not 0 <= self._atual < len(self._rows):
            return
        linha = self._atual
        self._rows.pop(linha)
        self._removidos += 1
        self._atual = -1
        self._preencher()
        self._legenda()
        if self._rows:
            self.table.setCurrentCell(min(linha, len(self._rows) - 1), 1)
        else:
            self.lbl_item.setText("Nada mais na lista")
            self.lbl_where.setText("")
            self.lbl_pos.setText("")
            self.lbl_atual.setText("")
            self.lbl_nav_state.setText("")
        self._atualizar_botoes()

    def _pedir_correcao(self, lista) -> None:
        for b in (self.btn_fix, self.btn_keep, self.btn_remove):
            b.setEnabled(False)
        self.fix_requested.emit(self._report, lista)

    def set_compact(self, compact: bool) -> None:
        """No compacto, o painel do item vai para baixo da lista: sem ele nao da para ver nem corrigir."""
        self._tag.setVisible(not compact)
        self._fora_resultado.setDirection(QBoxLayout.TopToBottom if compact else QBoxLayout.LeftToRight)
        if compact:
            self._lateral.setMinimumWidth(0)
            self._lateral.setMaximumWidth(16777215)
        else:
            self._lateral.setFixedWidth(LARGURA_LATERAL)
        for coluna in (0, 2, 4, 5):
            self.table.setColumnHidden(coluna, compact)

    def _deixar(self) -> None:
        if 0 <= self._atual < len(self._rows):
            self._situacao[self._rows[self._atual].order] = COMO_ESTAVA
            self._preencher()
            self._mover(1)
            self._atualizar_botoes()

    def on_fixed(self, resultados) -> None:
        """resultados: (item, polegadas novas ou None se falhou)."""
        for it, novo in resultados:
            if novo is None:
                self._situacao[it.order] = FALHOU
            else:
                self._era[it.order] = it.size
                it.size = fc.format_inch(fc.round_vba(novo), self._sep)
                self._situacao[it.order] = CORRIGIDO
        self._preencher()
        self._atualizar_botoes()
        if len(resultados) == 1 and self._rows and resultados[0][1] is not None:
            self._mover(1)


class CompareDwgPage(QWidget):
    """Abre o Compare DWG, um programa separado, que funciona mesmo com o CATIA fechado."""

    FILTRO = "Programas (*.exe *.bat *.cmd *.lnk *.py *.pyw);;Todos os arquivos (*)"

    def __init__(self):
        super().__init__()
        fora = QVBoxLayout(self)
        fora.setContentsMargins(0, 0, 0, 0)
        caixa = moldura()
        col = QVBoxLayout(caixa)
        col.setContentsMargins(22, 18, 22, 18)
        col.setSpacing(10)
        col.addStretch(1)
        linha = QHBoxLayout()
        linha.addStretch(1)
        linha.addWidget(icone_grande("monitor"))
        linha.addStretch(1)
        col.addLayout(linha)
        titulo = label("Compare DWG", "titulo")
        titulo.setAlignment(Qt.AlignCenter)
        col.addWidget(titulo)
        sub = largura_livre(label("Programa separado: abre em janela própria e funciona mesmo com o CATIA fechado.", "sub"))
        sub.setAlignment(Qt.AlignCenter)
        col.addWidget(sub)
        centro = QHBoxLayout()
        centro.addStretch(1)
        meio = QVBoxLayout()
        meio.setSpacing(8)
        self.linha_caminho = LinhaSituacao()
        self.linha_caminho.setMinimumWidth(320)
        meio.addWidget(self.linha_caminho)
        self.lbl_caminho = largura_livre(label("", "detalheFraco"))
        self.lbl_caminho.setAlignment(Qt.AlignCenter)
        meio.addWidget(self.lbl_caminho)
        self.lbl_erro = largura_livre(label("", "erro"))
        self.lbl_erro.setAlignment(Qt.AlignCenter)
        self.lbl_erro.hide()
        meio.addWidget(self.lbl_erro)
        self.btn_abrir = botao_grande("ABRIR O COMPARE DWG", "open")
        self.btn_abrir.clicked.connect(self.abrir)
        meio.addWidget(self.btn_abrir)
        self.btn_escolher = botao("TROCAR O CAMINHO", "secundario", "file")
        self.btn_escolher.clicked.connect(self.escolher)
        meio.addWidget(self.btn_escolher)
        centro.addLayout(meio, 3)
        centro.addStretch(1)
        col.addLayout(centro)
        col.addStretch(2)
        fora.addWidget(caixa)
        self._atualizar()

    def _atualizar(self) -> None:
        caminho = cd.get_path()
        erro = cd.problema(caminho)
        self.lbl_caminho.setText(caminho)
        self.lbl_caminho.setToolTip(caminho)
        if not caminho:
            self.linha_caminho.definir("neutro", "Caminho ainda não adicionado")
            self.btn_abrir.setText("ADICIONAR O CAMINHO DO COMPARE DWG")
            self.btn_escolher.hide()
        elif erro:
            self.linha_caminho.definir("erro", "Programa não encontrado nesse caminho")
            self.btn_abrir.setText("ESCOLHER O CAMINHO DE NOVO")
            self.btn_escolher.hide()
        else:
            self.linha_caminho.definir("ok", "Compare DWG encontrado")
            self.btn_abrir.setText("ABRIR O COMPARE DWG")
            self.btn_escolher.show()

    def escolher(self) -> bool:
        """Pede o programa e guarda o caminho. Devolve False se a pessoa cancelar."""
        atual = cd.get_path()
        caminho, _ = QFileDialog.getOpenFileName(self, "Escolha o programa do Compare DWG", atual, self.FILTRO)
        if not caminho:
            return False
        cd.set_path(caminho.replace("/", "\\"))
        self.lbl_erro.hide()
        self._atualizar()
        return True

    def abrir(self) -> None:
        """Abre o programa. Sem um caminho que funcione, pede o caminho e abre em seguida."""
        if cd.problema(cd.get_path()) and not self.escolher():
            return
        try:
            cd.abrir(cd.get_path())
            self.lbl_erro.hide()
        except OSError as exc:
            self.lbl_erro.setText(f"Não foi possível abrir o Compare DWG.\n{exc}")
            self.lbl_erro.show()
        self._atualizar()

    def set_compact(self, compact: bool) -> None:
        pass
