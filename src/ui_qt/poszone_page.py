"""Position and Zone: a tabela da planilha de Callouts, dentro do HUB.

Percorre cada balao no CATIA, como no Fix Flags, compara com o Part List do SAP e deixa marcar OK o
que o programa nao soube confirmar. A tela do Design tambem move o balao para a zona certa.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QBoxLayout, QButtonGroup, QComboBox, QFileDialog, QHBoxLayout, QHeaderView, QMessageBox, QScrollArea, QTableWidgetItem, QVBoxLayout, QWidget,
)

from engine import part_list as pl
from engine import pos_zone as pz
from ui_qt import theme as T
from ui_qt.font_size_page import PAPEL_OK, MarkDelegate, button, label
from ui_qt.pecas import Cartao, LinhaSituacao, Resumo, botao, botao_grande, largura_livre, moldura
from ui_qt.tool_page import LARGURA_LATERAL, ToolPage, tabela

CALLOUT, SO_PART_LIST, NAO_CONTADO = "callout", "sap", "pendencia"
OK, ERRO, NEUTRO, MANUAL = "ok", "erro", "neutro", "manual"
FILTRO_REVISAR, FILTRO_OK, FILTRO_SAP, FILTRO_PENDENCIAS, FILTRO_TODOS = range(5)
COLUNAS = ("", "POS", "ZONA", "QTD", "VISTA ORIGEM", "PL ZONA", "PL QTD", "PN")
COL_MARCA, COL_POS, COL_ZONA, COL_QTD, COL_VISTA, COL_PL_ZONA, COL_PL_QTD, COL_PN = range(8)
NAO_ENCONTRADO = "Callout não encontrado: foi apagado ou o desenho foi fechado."
FILTRO_ARQUIVOS = "Arquivos Excel (*.xlsx *.xlsm *.xls)"


def _numero(q: float) -> str:
    return str(int(q)) if float(q).is_integer() else str(q)


def _ordem(numero: str):
    return (0, float(numero), "") if numero.isdigit() else (1, 0.0, numero.lower())


@dataclass
class Linha:
    tipo: str
    numero: str
    chave: str
    assinatura_desenho: str
    assinatura_sap: Optional[str] = None
    callout: Optional[pz.Callout] = None
    pendencia: Optional[pz.Pending] = None
    occs: List[pz.Occurrence] = field(default_factory=list)
    sap: List[pl.RegistroSAP] = field(default_factory=list)
    zonas_sap: List[str] = field(default_factory=list)
    qtd_sap: Optional[float] = None
    # None: ainda sem Part List para comparar.
    posicao_ok: Optional[bool] = None
    zona_ok: Optional[bool] = None
    qtd_ok: Optional[bool] = None
    zona_sap_ok: Optional[bool] = None
    qtd_sap_ok: Optional[bool] = None
    manual: Optional[dict] = None

    @property
    def estado(self) -> str:
        if self.manual:
            return MANUAL
        if self.tipo != CALLOUT:
            return ERRO
        if self.posicao_ok is None:
            return NEUTRO
        return OK if self.posicao_ok and self.zona_ok and self.qtd_ok else ERRO

    @property
    def marca(self):
        return {OK: True, ERRO: False, NEUTRO: None, MANUAL: MANUAL}[self.estado]


def montar_linhas(report: pz.PosZoneReport, parte: Optional[pl.PartList], oks: pl.OkManual) -> List[Linha]:
    """Uma linha por posicao: o desenho e o Part List lado a lado, e o que ficou de fora da conta."""
    comp = pl.comparar(report.callouts, parte.registros) if parte else None
    registros = {}
    resultados = {}
    if parte:
        for r, res in zip(parte.registros, comp.sap):
            p = pl.normalizar_posicao(r.posicao)
            registros.setdefault(p, []).append(r)
            resultados.setdefault(p, []).append(res)
    ocorrencias = {}
    for o in report.occs:
        if not o.is_reference:
            ocorrencias.setdefault(pl.normalizar_posicao(o.number), []).append(o)

    def assinatura_sap(p: str) -> Optional[str]:
        return f"{';'.join(comp.zonas_sap.get(p, []))}|{comp.qtd_sap.get(p, 0.0)}" if parte else None

    linhas: List[Linha] = []
    for c in sorted(report.callouts, key=lambda x: _ordem(x.number)):
        p = pl.normalizar_posicao(c.number)
        li = Linha(CALLOUT, c.number, f"C|{p}", f"{pl.normalizar_zona(c.zone)}|{c.qty}", assinatura_sap(p), callout=c, occs=ocorrencias.get(p, []))
        if parte:
            res = comp.desenho[p]
            li.posicao_ok, li.zona_ok, li.qtd_ok = res.posicao, res.zona, res.quantidade
            li.sap = registros.get(p, [])
            li.zonas_sap = comp.zonas_sap.get(p, [])
            li.qtd_sap = comp.qtd_sap.get(p)
            if li.sap:
                li.zona_sap_ok = all(x.zona for x in resultados[p])
                li.qtd_sap_ok = all(x.quantidade for x in resultados[p])
        linhas.append(li)
    if parte:
        faltam = sorted(comp.faltam_no_desenho(parte.registros), key=_ordem)
        for p in faltam:
            li = Linha(
                SO_PART_LIST, p, f"C|{p}", "", assinatura_sap(p), sap=registros[p], zonas_sap=comp.zonas_sap.get(p, []),
                qtd_sap=comp.qtd_sap.get(p), zona_sap_ok=False, qtd_sap_ok=False,
            )
            linhas.append(li)
    for d in report.pendencias:
        chave = f"P|{d.sheet_name}|{d.view_name}|{d.item_index}|{d.number}"
        linhas.append(Linha(NAO_CONTADO, d.number, chave, d.motivo, pendencia=d))
    for li in linhas:
        li.manual = oks.vale(li.chave, li.assinatura_desenho, li.assinatura_sap)
    return linhas


def texto_situacao(li: Linha) -> str:
    if li.manual:
        return f"OK manual, por {li.manual.get('quem', '?')} no {li.manual.get('origem', '?')}"
    if li.tipo == NAO_CONTADO:
        return f"{li.pendencia.motivo}, não contabilizado"
    if li.tipo == SO_PART_LIST:
        return "Está no Part List e não tem balão no desenho"
    if li.posicao_ok is None:
        return "Carregue o Part List para comparar"
    if not li.posicao_ok:
        return "Não está no Part List"
    if not li.zona_ok:
        return f"Zona diferente: desenho {li.callout.zone or 'sem zona'}, Part List {', '.join(li.zonas_sap)}"
    if not li.qtd_ok:
        return f"Quantidade diferente: desenho {li.callout.qty}, Part List {_numero(li.qtd_sap)}"
    return "Posição, zona e quantidade batem com o Part List"


class PosZonePage(ToolPage):
    TOOL = "poszone"
    TITULO = "Position and Zone"
    DESCRICAO = (
        "Acha os callouts de todas as folhas, a zona e a quantidade de cada um, e compara com o Part List do SAP. "
        "Percorra balão por balão no CATIA e marque OK o que você conferiu. O desenho não é alterado."
    )
    BOTAO = "MAPEAR CALLOUTS"
    BOTAO_DE_NOVO = "Mapear de novo"
    ANDAMENTO = "Lendo as folhas"
    ETIQUETA = "SÓ CONFERE"
    TIPO_ETIQUETA = "confere"
    ICONE = "box"
    PODE_PARAR = False  # sem todas as folhas, as quantidades somadas ficariam erradas
    PODE_MOVER = False
    ORIGEM = "Check"
    TEXTO_TROCA = "CORRIGIR NO DESIGN"
    ICONE_TROCA = "pencil"

    go_requested = Signal(object, object, int)
    latest_nav = Signal(int)
    partlist_requested = Signal(list)
    partlist_clear_requested = Signal()
    excel_requested = Signal(str, object)
    mover_requested = Signal(object, object, str)
    desfazer_requested = Signal(object, object)
    alterado = Signal()  # a tabela mudou: a outra tela e os contadores precisam acompanhar
    trocar_requested = Signal()

    def __init__(self):
        self._part: Optional[pl.PartList] = None
        self._oks: Optional[pl.OkManual] = None
        self._todas: List[Linha] = []
        self._rows: List[Linha] = []
        self._atual = -1
        self._occ = 0
        self._occ_pedida = 0
        self._pedido = 0
        self._desfazer: List[pz.Movimento] = []
        self._lendo_part_list = False
        self._movendo = False
        self._compacto = False
        super().__init__()

    # ------------------------------------------------------------------
    # Montagem
    # ------------------------------------------------------------------
    def _build_results(self, col: QVBoxLayout) -> None:
        self._cartoes = QWidget()
        cartoes = QHBoxLayout(self._cartoes)
        cartoes.setContentsMargins(0, 0, 0, 0)
        cartoes.setSpacing(8)
        self.card_ok = Cartao("batem", "verde")
        self.card_revisar = Cartao("para revisar", "vermelho")
        self.card_manual = Cartao("OK manual")
        self.card_fora = Cartao("não contados", "ambar")
        for c in (self.card_ok, self.card_revisar, self.card_manual, self.card_fora):
            cartoes.addWidget(c, 1)
        col.addWidget(self._cartoes)

        filtros = QHBoxLayout()
        filtros.setSpacing(6)
        self._grupo = QButtonGroup(self)
        self.btn_revisar = button("", "filtro")
        self.btn_oks = button("", "filtro")
        self.btn_sap = button("", "filtro")
        self.btn_pendencias = button("", "filtro")
        self.btn_todos = button("", "filtro")
        for i, b in enumerate((self.btn_revisar, self.btn_oks, self.btn_sap, self.btn_pendencias, self.btn_todos)):
            b.setCheckable(True)
            self._grupo.addButton(b, i)
            filtros.addWidget(b)
        filtros.addStretch(1)
        self._grupo.idClicked.connect(lambda _: self._preencher())
        col.addLayout(filtros)

        self.table = tabela(COLUNAS, {COL_MARCA: 36, COL_POS: 50, COL_ZONA: 84, COL_QTD: 40, COL_PL_ZONA: 76, COL_PL_QTD: 48, COL_PN: 92}, COL_VISTA)
        self.table.setWordWrap(False)
        self.table.setTextElideMode(Qt.ElideRight)
        self.table.setItemDelegateForColumn(COL_MARCA, MarkDelegate(self.table))
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
        self.btn_prev.clicked.connect(lambda: self._mover_seta(-1))
        self.btn_next.clicked.connect(lambda: self._mover_seta(1))
        nav.addWidget(self.btn_prev, 2)
        nav.addWidget(self.lbl_pos, 1)
        nav.addWidget(self.btn_next, 2)
        col.addLayout(nav)

    def _build_side(self, col: QVBoxLayout) -> bool:
        col.setContentsMargins(0, 0, 0, 0)
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QScrollArea.NoFrame)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        area.setStyleSheet("QScrollArea, QScrollArea > QWidget, QScrollArea > QWidget > QWidget { background: transparent; }")
        area.viewport().setAutoFillBackground(False)
        dentro = QWidget()
        dentro.setAutoFillBackground(False)
        lado = QVBoxLayout(dentro)
        lado.setContentsMargins(14, 14, 14, 14)
        lado.setSpacing(8)
        area.setWidget(dentro)
        col.addWidget(area)

        topo = QHBoxLayout()
        topo.addWidget(label("CALLOUT ATUAL", "secao"))
        topo.addStretch(1)
        self.lbl_ocorrencia = label("", "secao")
        topo.addWidget(self.lbl_ocorrencia)
        lado.addLayout(topo)
        self.lbl_numero = label("", "titulo")
        lado.addWidget(self.lbl_numero)
        self.lbl_lugar = largura_livre(label("", "detalheFraco"))
        lado.addWidget(self.lbl_lugar)
        self.valores = Resumo(("Zona no desenho", "Qtd no desenho", "Zona no Part List", "Qtd no Part List", "PN"))
        lado.addWidget(self.valores)

        if self.PODE_MOVER:
            lado.addWidget(label("MOVER PARA A ZONA", "secao"))
            self.combo_zona = QComboBox()
            self.combo_zona.currentTextChanged.connect(lambda _: self._atualizar_botao_mover())
            lado.addWidget(self.combo_zona)
            self.lbl_junto = largura_livre(label("", "detalheFraco"))
            lado.addWidget(self.lbl_junto)
            self.btn_mover = botao_grande("MOVER O BALÃO", "arrow")
            self.btn_mover.clicked.connect(self._on_mover)
            lado.addWidget(self.btn_mover)
            self.btn_desfazer = botao("DESFAZER", "secundario", "refresh")
            self.btn_desfazer.clicked.connect(self._on_desfazer)
            lado.addWidget(self.btn_desfazer)

        self.btn_ok = botao("DEIXAR COMO ESTÁ (OK)", "secundario", "check")
        self.btn_ok.clicked.connect(self._on_marcar)
        lado.addWidget(self.btn_ok)

        lado.addSpacing(4)
        lado.addWidget(label("PART LIST DO SAP", "secao"))
        self.linha_pl = LinhaSituacao()
        lado.addWidget(self.linha_pl)
        botoes = QHBoxLayout()
        botoes.setSpacing(6)
        self.btn_carregar = botao("CARREGAR", "secundario", "file")
        self.btn_carregar.clicked.connect(self._on_carregar)
        self.btn_limpar = botao("LIMPAR", "secundario", "x")
        self.btn_limpar.clicked.connect(self._on_limpar)
        botoes.addWidget(self.btn_carregar, 1)
        botoes.addWidget(self.btn_limpar, 1)
        lado.addLayout(botoes)

        self.btn_troca = botao(self.TEXTO_TROCA, "secundario", self.ICONE_TROCA)
        self.btn_troca.clicked.connect(self.trocar_requested)
        lado.addWidget(self.btn_troca)
        self.btn_excel = botao("ABRIR NO EXCEL", "secundario", "open")
        self.btn_excel.clicked.connect(self._on_excel)
        lado.addWidget(self.btn_excel)

        lado.addSpacing(4)
        lado.addWidget(label("RESUMO", "secao"))
        self.resumo = Resumo((
            "Objetos válidos", "Linhas multilinha", "Ignoradas por REF", "Quantidades por chave", "Callouts",
            "Grupo ou ambíguo", "Inconsistentes", "Linhas do Part List", "Registros do Part List",
        ))
        lado.addWidget(self.resumo)
        lado.addStretch(1)
        return True

    # ------------------------------------------------------------------
    # Resultado
    # ------------------------------------------------------------------
    def _show_report(self, report) -> None:
        novo_desenho = self._oks is None or self._oks.pn != report.pn.upper()
        if novo_desenho:
            self._part = None  # o Part List de outro desenho nao pode ser comparado com este
        self._oks = pl.OkManual(report.pn)
        self._desfazer = []
        self._recalcular()
        revisar = [li for li in self._todas if li.estado == ERRO]
        (self.btn_revisar if revisar else self.btn_todos).setChecked(True)
        self._preencher()

    def _recalcular(self) -> None:
        report = self._report
        self._todas = montar_linhas(report, self._part, self._oks)
        c = report.counters
        n = {OK: 0, ERRO: 0, NEUTRO: 0, MANUAL: 0}
        for li in self._todas:
            n[li.estado] += 1
        so_sap = sum(1 for li in self._todas if li.tipo == SO_PART_LIST)
        fora = sum(1 for li in self._todas if li.tipo == NAO_CONTADO)
        self.lbl_sub.setText(f"PN {report.pn}  ·  {report.occurrences - c.referencias} ocorrências válidas  ·  {len(report.callouts)} callouts")
        self.card_ok.valor(n[OK])
        self.card_revisar.valor(n[ERRO])
        self.card_manual.valor(n[MANUAL])
        self.card_fora.valor(fora)
        self.btn_revisar.setText(f"Para revisar ({n[ERRO]})")
        self.btn_oks.setText(f"OK ({n[OK] + n[MANUAL]})")
        self.btn_sap.setText(f"Só no Part List ({so_sap})")
        self.btn_pendencias.setText(f"Não contados ({fora})")
        self.btn_todos.setText(f"Todos ({len(self._todas)})")
        for nome, valor in (
            ("Objetos válidos", c.validos), ("Linhas multilinha", c.multilinha), ("Ignoradas por REF", c.referencias),
            ("Quantidades por chave", c.chaves), ("Callouts", len(report.callouts)), ("Grupo ou ambíguo", c.grupo), ("Inconsistentes", c.conflito),
            ("Linhas do Part List", self._part.linhas_lidas if self._part else "-"),
            ("Registros do Part List", len(self._part.registros) if self._part else "-"),
        ):
            self.resumo.definir(nome, valor)
        self._mostrar_part_list()
        report.abertas = n[ERRO]

    def _mostrar_part_list(self) -> None:
        self.btn_carregar.setEnabled(not self._lendo_part_list)
        self.btn_limpar.setEnabled(self._part is not None and not self._lendo_part_list)
        if self._lendo_part_list:
            self.linha_pl.definir("neutro", "Lendo o Part List")
        elif self._part:
            self.linha_pl.definir("ok", f"{len(self._part.arquivos)} arquivo(s) comparado(s)")
            self.linha_pl.setToolTip("\n".join(self._part.arquivos))
        else:
            self.linha_pl.definir("neutro", "Nenhum carregado")
            self.linha_pl.setToolTip("")

    def _filtradas(self) -> List[Linha]:
        filtro = self._grupo.checkedId()
        if filtro == FILTRO_REVISAR:
            return [li for li in self._todas if li.estado == ERRO]
        if filtro == FILTRO_OK:
            return [li for li in self._todas if li.estado in (OK, MANUAL)]
        if filtro == FILTRO_SAP:
            return [li for li in self._todas if li.tipo == SO_PART_LIST]
        if filtro == FILTRO_PENDENCIAS:
            return [li for li in self._todas if li.tipo == NAO_CONTADO]
        return list(self._todas)

    def _celula(self, texto, ok: Optional[bool], negrito: bool = False) -> QTableWidgetItem:
        cel = QTableWidgetItem(str(texto))
        cel.setToolTip(str(texto))
        if ok is not None:
            cel.setForeground(QBrush(QColor(T.GREEN if ok else T.RED)))
        if negrito:
            f = cel.font()
            f.setBold(True)
            cel.setFont(f)
        return cel

    def _preencher(self, chave: str = "", occ: int = 0, linha_antiga: int = 0) -> None:
        self._rows = self._filtradas()
        self._atual = -1
        self.table.blockSignals(True)
        self.table.selectionModel().blockSignals(True)
        self.table.clearContents()
        self.table.setRowCount(len(self._rows))
        for n, li in enumerate(self._rows):
            marca = QTableWidgetItem()
            marca.setData(PAPEL_OK, li.marca)
            self.table.setItem(n, COL_MARCA, marca)
            c = li.callout
            d = li.pendencia
            vista = f"{c.sheet} - {c.view}" if c else (f"{d.sheet_name} - {d.view_name}" if d else "")
            pn = "; ".join(dict.fromkeys(r.pn for r in li.sap))
            self.table.setItem(n, COL_POS, self._celula(li.numero, li.posicao_ok, True))
            self.table.setItem(n, COL_ZONA, self._celula(c.zone if c else "", li.zona_ok))
            self.table.setItem(n, COL_QTD, self._celula(c.qty if c else "", li.qtd_ok))
            self.table.setItem(n, COL_VISTA, self._celula(vista, None))
            self.table.setItem(n, COL_PL_ZONA, self._celula("; ".join(r.zona for r in li.sap), li.zona_sap_ok))
            self.table.setItem(n, COL_PL_QTD, self._celula(_numero(li.qtd_sap) if li.qtd_sap is not None else "", li.qtd_sap_ok))
            self.table.setItem(n, COL_PN, self._celula(pn, None))
        self.table.selectionModel().blockSignals(False)
        self.table.blockSignals(False)
        self._colunas_visiveis()
        tem = bool(self._rows)
        self.btn_prev.setEnabled(tem)
        self.btn_next.setEnabled(tem)
        if not tem:
            self.lbl_pos.setText("")
            self.lbl_nav_state.setText("")
            self.lbl_detail.setText("Nada nesta lista")
            self.lbl_where.setText("")
            self._lado_vazio()
            return
        alvo = next((i for i, li in enumerate(self._rows) if li.chave == chave), None) if chave else 0
        if alvo is None:
            alvo, occ = min(linha_antiga, len(self._rows) - 1), 0
        self._occ_pedida = occ
        self.table.setCurrentCell(alvo, COL_POS)

    def _colunas_visiveis(self) -> None:
        """Sem Part List, as colunas dele so tirariam espaco da vista."""
        tem_part_list = self._part is not None
        for coluna in (COL_PL_ZONA, COL_PL_QTD):
            self.table.setColumnHidden(coluna, not tem_part_list)
        self.table.setColumnHidden(COL_PN, not tem_part_list or self._compacto)
        self.table.setColumnHidden(COL_VISTA, self._compacto)
        # Sem a vista, a zona fica com o espaco que sobra.
        cab = self.table.horizontalHeader()
        cab.setSectionResizeMode(COL_ZONA, QHeaderView.Stretch if self._compacto else QHeaderView.Fixed)

    # ------------------------------------------------------------------
    # Navegacao: a seta passa por todos os baloes de cada posicao
    # ------------------------------------------------------------------
    def _on_linha(self, atual, _anterior) -> None:
        if atual.isValid():
            self._ir(atual.row(), self._occ_pedida)
            self._occ_pedida = 0

    def _ir(self, linha: int, occ: int = 0) -> None:
        self._atual = linha
        li = self._rows[linha]
        self._occ = max(0, min(occ, len(li.occs) - 1)) if li.occs else 0
        total = len(li.occs)
        self.lbl_pos.setText(f"{linha + 1} de {len(self._rows)}")
        self.lbl_detail.setText(f"Callout {li.numero}  |  {texto_situacao(li)}")
        item = None
        if li.occs:
            o = li.occs[self._occ]
            item = o
            tipo = "balão" if o.source == pz.SOURCE_BALLOON else "sublinhado"
            zona = f" › zona {o.zone}" if o.source == pz.SOURCE_BALLOON else ""
            self.lbl_where.setText(f"{o.sheet} › {o.view} › {tipo} {self._occ + 1} de {total}{zona}")
        elif li.pendencia:
            p = li.pendencia
            item = p
            self.lbl_where.setText(f"{p.sheet_name} › {p.view_name} › callout {p.number}")
        else:
            self.lbl_where.setText("Sem balão no desenho")
        self._mostrar_lado(li)
        if item is None:
            self._estado("", T.MUTED)
            return
        # As duas telas leem o mesmo resultado: so a que esta aberta mexe no CATIA.
        if not self.isVisible():
            self._estado("", T.MUTED)
            return
        self._estado("Indo até o callout", T.AMBER)
        self._pedido += 1
        self.latest_nav.emit(self._pedido)
        self.go_requested.emit(self._report, item, self._pedido)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._report is not None and 0 <= self._atual < len(self._rows):
            self._ir(self._atual, self._occ)

    def on_nav_done(self, pedido: int, ok: bool) -> None:
        if pedido != self._pedido:
            return
        if ok:
            self._estado("Selecionado no CATIA", T.GREEN)
        else:
            self._estado("", T.RED)
            self.lbl_detail.setText(NAO_ENCONTRADO)

    def _estado(self, texto: str, cor: str) -> None:
        self.lbl_nav_state.setText(f"●  {texto}" if texto else "")
        self.lbl_nav_state.setStyleSheet(f"color: {cor};")

    def _mover_seta(self, passo: int) -> None:
        if not self._rows:
            return
        li = self._rows[self._atual] if self._atual >= 0 else None
        if li and li.occs and 0 <= self._occ + passo < len(li.occs):
            self._ir(self._atual, self._occ + passo)
            return
        linha = (self._atual + passo) % len(self._rows)
        destino = self._rows[linha]
        occ = len(destino.occs) - 1 if passo < 0 and destino.occs else 0
        if linha == self._atual:
            self._ir(linha, occ)
        else:
            self._occ_pedida = occ
            self.table.setCurrentCell(linha, COL_POS)

    # ------------------------------------------------------------------
    # Painel do callout atual
    # ------------------------------------------------------------------
    def _lado_vazio(self) -> None:
        self.lbl_numero.setText("")
        self.lbl_lugar.setText("")
        self.lbl_ocorrencia.setText("")
        for nome in self.valores.valores:
            self.valores.definir(nome, "-")
        self.btn_ok.setEnabled(False)
        if self.PODE_MOVER:
            self.combo_zona.clear()
            self.lbl_junto.setText("")
            self._atualizar_botao_mover()

    def _mostrar_lado(self, li: Linha) -> None:
        self.lbl_numero.setText(li.numero)
        self.lbl_lugar.setText(texto_situacao(li))
        self.lbl_ocorrencia.setText(f"{self._occ + 1} de {len(li.occs)}" if li.occs else "")
        c = li.callout
        self.valores.definir("Zona no desenho", (c.zone or "sem zona") if c else "-", self._cor(li.zona_ok))
        self.valores.definir("Qtd no desenho", c.qty if c else "-", self._cor(li.qtd_ok))
        self.valores.definir("Zona no Part List", "; ".join(r.zona for r in li.sap) or "-", self._cor(li.zona_sap_ok))
        self.valores.definir("Qtd no Part List", _numero(li.qtd_sap) if li.qtd_sap is not None else "-", self._cor(li.qtd_sap_ok))
        self.valores.definir("PN", "; ".join(dict.fromkeys(r.pn for r in li.sap)) or "-")
        self.btn_ok.setEnabled(True)
        self.btn_ok.setText("TIRAR O OK" if li.manual else "DEIXAR COMO ESTÁ (OK)")
        if self.PODE_MOVER:
            self._mostrar_mover(li)

    @staticmethod
    def _cor(ok: Optional[bool]) -> str:
        return "" if ok is None else (T.GREEN if ok else T.RED)

    def _occ_atual(self) -> Optional[pz.Occurrence]:
        if 0 <= self._atual < len(self._rows):
            li = self._rows[self._atual]
            if li.occs:
                return li.occs[self._occ]
        return None

    def _mostrar_mover(self, li: Linha) -> None:
        o = self._occ_atual()
        self.combo_zona.blockSignals(True)
        self.combo_zona.clear()
        junto = ""
        if o is not None and o.source == pz.SOURCE_BALLOON:
            zonas = pz.zonas_da_folha(self._report, o.sheet)
            self.combo_zona.addItems(zonas)
            alvo = o.zone
            pedidas = li.zonas_sap
            if pedidas and pl.normalizar_zona(o.zone) not in pedidas:
                alvo = next((z for z in pedidas if z in zonas), "")
                if not alvo:
                    junto = f"O Part List pede {', '.join(pedidas)}, que não é desta folha. "
                    alvo = o.zone
            if alvo in zonas:
                self.combo_zona.setCurrentText(alvo)
            colados = pz.colados_do_balao(self._report, o)
            if colados:
                junto += "Anda junto: " + ", ".join(colados)
            if not zonas:
                junto = "Esta folha não tem zonas mapeadas."
        elif o is not None:
            junto = "Só o balão define a zona: este número é sublinhado."
        self.combo_zona.blockSignals(False)
        self.lbl_junto.setText(junto)
        self._atualizar_botao_mover()

    def _atualizar_botao_mover(self) -> None:
        if not self.PODE_MOVER:
            return
        o = self._occ_atual()
        destino = self.combo_zona.currentText()
        self.btn_mover.setEnabled(
            not self._movendo and o is not None and o.source == pz.SOURCE_BALLOON and bool(destino) and destino != o.zone
        )
        self.btn_mover.setText(f"MOVER PARA {destino}" if self.btn_mover.isEnabled() else "MOVER O BALÃO")
        self.btn_desfazer.setEnabled(not self._movendo and bool(self._desfazer))

    # ------------------------------------------------------------------
    # Acoes
    # ------------------------------------------------------------------
    def _chave_atual(self) -> str:
        return self._rows[self._atual].chave if 0 <= self._atual < len(self._rows) else ""

    def atualizar_tabela(self) -> None:
        """A tabela mudou por fora: Part List, OK ou balao movido na outra tela."""
        if self._report is None or self._oks is None:
            return
        chave, occ, linha = self._chave_atual(), self._occ, self._atual
        self._oks = pl.OkManual(self._report.pn)
        self._recalcular()
        self._preencher(chave, occ, max(linha, 0))

    def _on_marcar(self) -> None:
        if not 0 <= self._atual < len(self._rows):
            return
        li = self._rows[self._atual]
        if li.manual:
            self._oks.tirar(li.chave)
        else:
            self._oks.marcar(li.chave, li.assinatura_desenho, li.assinatura_sap, self.ORIGEM)
        self.atualizar_tabela()
        self.alterado.emit()

    def _on_carregar(self) -> None:
        caminhos, _ = QFileDialog.getOpenFileNames(self, "Selecione um ou dois arquivos extraídos do SAP", "", FILTRO_ARQUIVOS)
        if not caminhos:
            return
        if len(caminhos) > pl.MAX_ARQUIVOS:
            QMessageBox.warning(
                self, "Muitos arquivos selecionados",
                f"Selecione no máximo dois arquivos de Part List.\n\nQuantidade selecionada: {len(caminhos)}",
            )
            return
        self.partlist_requested.emit([c.replace("/", "\\") for c in caminhos])

    def _on_limpar(self) -> None:
        caixa = QMessageBox(self)
        caixa.setIcon(QMessageBox.Question)
        caixa.setWindowTitle(pl.TITULO_LIMPAR)
        caixa.setText(pl.PERGUNTA_LIMPAR.replace("\r\n", "\n"))
        sim = caixa.addButton("Sim", QMessageBox.YesRole)
        nao = caixa.addButton("Não", QMessageBox.NoRole)
        caixa.setDefaultButton(nao)
        caixa.setEscapeButton(nao)
        caixa.exec()
        if caixa.clickedButton() is sim:
            self.partlist_clear_requested.emit()

    def lendo_part_list(self, lendo: bool) -> None:
        self._lendo_part_list = lendo
        self._mostrar_part_list()

    def definir_part_list(self, parte: Optional[pl.PartList]) -> None:
        self._part = parte
        self._lendo_part_list = False
        self._mostrar_part_list()
        self.atualizar_tabela()

    def _on_excel(self) -> None:
        if self._report is not None:
            self.excel_requested.emit(self.TOOL, self._report)

    def _on_mover(self) -> None:
        o = self._occ_atual()
        destino = self.combo_zona.currentText()
        if o is None or not destino:
            return
        self._movendo = True
        self._atualizar_botao_mover()
        self._estado(f"Movendo para {destino}", T.AMBER)
        self.mover_requested.emit(self._report, o, destino)

    def _on_desfazer(self) -> None:
        if self._desfazer:
            self._movendo = True
            self._atualizar_botao_mover()
            self._estado("Desfazendo", T.AMBER)
            self.desfazer_requested.emit(self._report, self._desfazer.pop())

    def on_movido(self, mov, erro: str) -> None:
        self._movendo = False
        if erro:
            self._atualizar_botao_mover()
            self._estado("", T.RED)
            self.on_warn(erro, "Mover o balão")
            return
        self._desfazer.append(mov)
        self._apos_mudar_zona()

    def on_desfeito(self, mov, erro: str) -> None:
        self._movendo = False
        if erro:
            self._desfazer.append(mov)
            self._atualizar_botao_mover()
            self._estado("", T.RED)
            self.on_warn(erro, "Desfazer")
            return
        self._apos_mudar_zona()

    def _apos_mudar_zona(self) -> None:
        self.atualizar_tabela()
        self.alterado.emit()

    # ------------------------------------------------------------------
    # Modo compacto: o painel vai para baixo da lista
    # ------------------------------------------------------------------
    def set_compact(self, compact: bool) -> None:
        self._compacto = compact
        self._tag.setVisible(not compact)
        self._cartoes.setVisible(not compact)
        # A tabela ja mostra os valores: sobram os botoes, sem precisar rolar.
        self.valores.setVisible(not compact)
        self.resumo.setVisible(not compact)
        self._fora_resultado.setDirection(QBoxLayout.TopToBottom if compact else QBoxLayout.LeftToRight)
        if compact:
            self._lateral.setMinimumWidth(0)
            self._lateral.setMaximumWidth(16777215)
            self._lateral.setMaximumHeight(300)
        else:
            self._lateral.setFixedWidth(LARGURA_LATERAL)
            self._lateral.setMaximumHeight(16777215)
        self._colunas_visiveis()
        for b in (self.btn_oks, self.btn_sap):
            b.setVisible(not compact)


class PosZoneFixPage(PosZonePage):
    """Mesma tabela do Check. Aqui o balao pode ser movido para a zona certa."""

    TOOL = "poszonefix"
    TITULO = "Pos and Zone Fix"
    DESCRICAO = (
        "Compara os callouts com o Part List do SAP e percorre balão por balão no CATIA. Quando a zona está errada, "
        "move o balão para a zona certa, com a flag e a quantidade coladas nele. Altera o desenho: salve uma cópia antes."
    )
    ETIQUETA = "ALTERA O DESENHO"
    TIPO_ETIQUETA = "altera"
    PODE_MOVER = True
    ORIGEM = "Design"
    TEXTO_TROCA = "CONFERIR NO CHECK"
    ICONE_TROCA = "shield"
