"""Sequencia de aplicacao: roda as ferramentas do Design em ordem, e a Visao geral do Check.

Sem cronometro nem estimativa de tempo: so o que de fato aconteceu.
"""
from __future__ import annotations

from typing import List

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QProgressBar, QScrollArea, QStackedWidget, QVBoxLayout, QWidget,
)

from engine.documento import eh_desenho
from ui_qt import theme as T
from ui_qt.font_size_page import button, label
from ui_qt.icones import pixmap
from ui_qt.pecas import (
    Caixa, Cartao, LinhaSituacao, Resumo, Segmentos, aviso_catia_ocupado, botao, botao_grande, cabecalho, etiqueta,
    largura_livre, moldura,
)
from ui_qt.tool_page import LARGURA_LATERAL

ETAPAS = (
    ("update", "Update Template", "Troca a etiqueta no próprio desenho", "refresh"),
    ("symbol", "Symbol Shape Converter", "Converte a forma dos símbolos", "arrow"),
    ("flags", "Fix Flags", "Corrige as flag notes", "flag"),
    ("fontfix", "Font Size Fix", "Mostra o que está errado para você corrigir", "sheet"),
)
PRESET_COMPLETA, PRESET_MINHA = range(2)
PAGINA_ESCOLHA, PAGINA_RODANDO = range(2)


class _LinhaEtapa(QFrame):
    def __init__(self, ordem: int, nome: str, descricao: str, ic: str, ligada: bool = True):
        super().__init__()
        self.setObjectName("linhaLista" if ligada else "linhaListaOff")
        self.setFixedHeight(54)
        h = QHBoxLayout(self)
        h.setContentsMargins(12, 0, 12, 0)
        h.setSpacing(12)
        self.caixa = Caixa(ligada)
        self.caixa.setEnabled(ligada)
        h.addWidget(self.caixa)
        self.lbl_ordem = label(str(ordem) if ligada else "", "numeroOrdem")
        self.lbl_ordem.setFixedWidth(14)
        h.addWidget(self.lbl_ordem)
        i = QLabel()
        i.setPixmap(pixmap(ic, T.MUTED if ligada else T.DIM, 18))
        h.addWidget(i)
        textos = QVBoxLayout()
        textos.setSpacing(0)
        textos.addStretch(1)
        textos.addWidget(label(nome, "passoNome" if ligada else "passoNomeOff"))
        textos.addWidget(label(descricao, "passoSub"))
        textos.addStretch(1)
        h.addLayout(textos, 1)
        if not ligada:
            h.addWidget(label("No painel VBA", "passoSub"))


class _Passo(QWidget):
    """Uma etapa na linha do tempo da execucao."""

    def __init__(self, ordem: int, nome: str):
        super().__init__()
        self.ordem = ordem
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(12)
        self.marca = QLabel(str(ordem))
        self.marca.setFixedSize(30, 30)
        self.marca.setAlignment(Qt.AlignCenter)
        h.addWidget(self.marca, 0, Qt.AlignTop)
        self.caixa = QFrame()
        c = QVBoxLayout(self.caixa)
        c.setContentsMargins(10, 6, 10, 6)
        c.setSpacing(2)
        self.nome = label(nome, "passoNomeOff")
        self.sub = largura_livre(label("Aguardando", "passoSub"))
        self.barra = QProgressBar()
        self.barra.setTextVisible(False)
        self.barra.setFixedHeight(8)
        self.barra.hide()
        c.addWidget(self.nome)
        c.addWidget(self.sub)
        c.addWidget(self.barra)
        h.addWidget(self.caixa, 1)
        self.estado("espera", "Aguardando")

    def estado(self, estado: str, texto: str = "") -> None:
        if texto:
            self.sub.setText(texto)
        atual = estado == "rodando"
        self.caixa.setObjectName("passoAtual" if atual else "")
        self.caixa.style().unpolish(self.caixa)
        self.caixa.style().polish(self.caixa)
        self.barra.setVisible(atual)
        self.nome.setObjectName("passoNomeOff" if estado == "espera" else "passoNome")
        self.nome.style().unpolish(self.nome)
        self.nome.style().polish(self.nome)
        base = "border-radius: 15px; font-weight: 700;"
        if estado in ("feito", "erro", "pulado"):
            cor, tinta, ic = {
                "feito": (T.GREEN, T.GREEN_INK, "check"), "erro": (T.RED, T.RED_INK, "x"), "pulado": (T.CARD_2, T.MUTED, "minus"),
            }[estado]
            self.marca.setStyleSheet(f"{base} background: {cor};")
            self.marca.setPixmap(pixmap(ic, tinta, 16, 2.6))
        else:
            borda = T.CYAN if atual else T.LINE
            self.marca.setPixmap(pixmap("minus", "#00000000", 16))
            self.marca.setText(str(self.ordem))
            self.marca.setStyleSheet(f"{base} border: 2px solid {borda}; color: {T.CYAN if atual else T.DIM};")


class SequenciaPage(QWidget):
    run_requested = Signal(list)
    stop_requested = Signal()
    conferir_requested = Signal()
    revisar_fontes_requested = Signal()
    formato_preview = Signal(str)

    def __init__(self):
        super().__init__()
        self._connected = False
        self._has_drawing = False
        self._documento = ""
        self._passos: List[_Passo] = []
        self._ids: List[str] = []
        self._terminou = False
        h = QVBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        self._stack = QStackedWidget()
        h.addWidget(self._stack)
        self._stack.addWidget(self._build_escolha())
        self._stack.addWidget(self._build_rodando())
        self._atualizar()

    # ------------------------------------------------------------------
    # Escolha das etapas
    # ------------------------------------------------------------------
    def _build_escolha(self) -> QWidget:
        w = QWidget()
        fora = QHBoxLayout(w)
        fora.setContentsMargins(0, 0, 0, 0)
        fora.setSpacing(12)
        centro = moldura()
        col = QVBoxLayout(centro)
        col.setContentsMargins(18, 14, 18, 14)
        col.setSpacing(10)
        topo, sub = cabecalho("Sequência de aplicação", etiqueta("ALTERA O DESENHO"))
        sub.setText("Marque o que quer aplicar. O número mostra a ordem.")
        col.addLayout(topo)
        self.presets = Segmentos(("Completa", "Minha seleção"))
        self.presets.grupo.idClicked.connect(self._on_preset)
        col.addWidget(self.presets)
        self.linhas = {}
        ordem = 0
        for chave, nome, descricao, ic in ETAPAS:
            ordem += 1
            self.linhas[chave] = _LinhaEtapa(ordem, nome, descricao, ic)
            col.addWidget(self.linhas[chave])
        for linha in self.linhas.values():
            linha.caixa.clicked.connect(self._on_marcar)
        col.addStretch(1)
        fora.addWidget(centro, 1)
        self._centro_escolha = centro

        lado = moldura()
        lado.setFixedWidth(LARGURA_LATERAL)
        c = QVBoxLayout(lado)
        c.setContentsMargins(14, 14, 14, 14)
        c.setSpacing(8)
        self.lbl_preset = label("Sequência completa", "titulo")
        c.addWidget(self.lbl_preset)
        self.lbl_pronta = largura_livre(label("", "sub"))
        c.addWidget(self.lbl_pronta)
        self.linha_catia = LinhaSituacao()
        self.linha_doc = LinhaSituacao()
        c.addWidget(self.linha_catia)
        c.addWidget(self.linha_doc)
        self.resumo = Resumo(("Etapas marcadas",))
        c.addWidget(self.resumo)
        c.addStretch(1)
        self.btn_executar = botao_grande("EXECUTAR")
        self.btn_executar.clicked.connect(self._executar)
        c.addWidget(self.btn_executar)
        fora.addWidget(lado)
        return w

    def set_catia_state(self, connected: bool, document: str, desenho: bool = False) -> None:
        self._connected = connected
        self._documento = document
        self._has_drawing = desenho or eh_desenho(document)
        self._atualizar()

    def _marcadas(self) -> List[str]:
        return [chave for chave, _n, _d, _i in ETAPAS if self.linhas[chave].caixa.isChecked()]

    def _on_preset(self, preset: int) -> None:
        if preset == PRESET_COMPLETA:
            for chave in self.linhas:
                self.linhas[chave].caixa.setChecked(True)
        self._atualizar()

    def _on_marcar(self) -> None:
        self.presets.botoes[PRESET_MINHA].setChecked(True)
        self._atualizar()

    def _atualizar(self) -> None:
        marcadas = self._marcadas()
        n = 0
        for chave, _nome, _d, _i in ETAPAS:
            if self.linhas[chave].caixa.isChecked():
                n += 1
                self.linhas[chave].lbl_ordem.setText(str(n))
            else:
                self.linhas[chave].lbl_ordem.setText("")
        self.lbl_preset.setText(("Sequência completa", "Minha seleção")[self.presets.grupo.checkedId()])
        self.linha_catia.definir("ok" if self._connected else "erro", "CATIA ativo" if self._connected else "CATIA fechado")
        if self._has_drawing:
            self.linha_doc.definir("ok", f"{self._documento} detectado")
        else:
            self.linha_doc.definir("neutro" if not self._connected else "erro", "Nenhum desenho ativo")
        pronto = self._connected and self._has_drawing and bool(marcadas)
        self.lbl_pronta.setText("Pronta para rodar neste desenho." if pronto else "Abra um desenho e marque ao menos uma etapa.")
        self.resumo.definir("Etapas marcadas", len(marcadas))
        self.btn_executar.setText(f"EXECUTAR {len(marcadas)} ETAPA{'S' if len(marcadas) != 1 else ''}")
        self.btn_executar.setEnabled(pronto)

    def _executar(self) -> None:
        self.run_requested.emit(self._marcadas())

    # ------------------------------------------------------------------
    # Execucao
    # ------------------------------------------------------------------
    def _build_rodando(self) -> QWidget:
        w = QWidget()
        fora = QHBoxLayout(w)
        fora.setContentsMargins(0, 0, 0, 0)
        fora.setSpacing(12)
        centro = moldura()
        col = QVBoxLayout(centro)
        col.setContentsMargins(18, 14, 18, 14)
        col.setSpacing(10)
        self.lbl_run_titulo = label("Executando a sequência", "titulo")
        col.addWidget(self.lbl_run_titulo)
        self.lbl_run_doc = largura_livre(label("", "sub"))
        col.addWidget(self.lbl_run_doc)
        self._col_passos = QVBoxLayout()
        self._col_passos.setSpacing(12)
        col.addLayout(self._col_passos)
        col.addStretch(1)
        fora.addWidget(centro, 1)
        self._centro_rodando = centro

        lado = moldura()
        lado.setFixedWidth(LARGURA_LATERAL + 60)
        c = QVBoxLayout(lado)
        c.setContentsMargins(14, 14, 14, 14)
        c.setSpacing(10)
        self.lbl_estado = label("CATIA trabalhando", "subtitulo2")
        c.addWidget(self.lbl_estado)
        self.lbl_porcento = label("0%", "porcento")
        c.addWidget(self.lbl_porcento)
        self.barra_total = QProgressBar()
        self.barra_total.setTextVisible(False)
        self.barra_total.setFixedHeight(10)
        c.addWidget(self.barra_total)
        self.aviso = aviso_catia_ocupado()
        c.addWidget(self.aviso)
        c.addWidget(label("O que está acontecendo", "subtitulo2"))
        caixa_log = moldura("detalhe")
        cl = QVBoxLayout(caixa_log)
        cl.setContentsMargins(12, 10, 12, 10)
        self.lbl_log = largura_livre(label("", "log"))
        self.lbl_log.setAlignment(Qt.AlignBottom | Qt.AlignLeft)
        cl.addWidget(self.lbl_log, 1)
        c.addWidget(caixa_log, 1)
        self.btn_parar = botao("PARAR DEPOIS DESTA ETAPA", "perigo", "stop", T.RED)
        self.btn_parar.clicked.connect(self._parar)
        c.addWidget(self.btn_parar)
        self.btn_fontes = botao_grande("REVISAR AS FONTES", "sheet")
        self.btn_fontes.clicked.connect(self.revisar_fontes_requested)
        c.addWidget(self.btn_fontes)
        self.btn_conferir = botao_grande("CONFERIR NO CHECK", "shield")
        self.btn_conferir.clicked.connect(self.conferir_requested)
        self.btn_voltar = botao("VOLTAR À SEQUÊNCIA", "secundario", "left")
        self.btn_voltar.clicked.connect(lambda: self._stack.setCurrentIndex(PAGINA_ESCOLHA))
        c.addWidget(self.btn_conferir)
        c.addWidget(self.btn_voltar)
        fora.addWidget(lado)
        self._lado_rodando = lado
        return w

    def on_started(self, ids: list) -> None:
        self._ids = list(ids)
        self._terminou = False
        while self._col_passos.count():
            item = self._col_passos.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        nomes = {c: n for c, n, _d, _i in ETAPAS}
        self._passos = [_Passo(i, nomes[c]) for i, c in enumerate(ids, 1)]
        for p in self._passos:
            self._col_passos.addWidget(p)
        self._log = []
        self.lbl_log.setText("")
        self.lbl_run_titulo.setText("Executando a sequência")
        self.lbl_run_doc.setText(self._documento)
        self.lbl_estado.setText("CATIA trabalhando")
        self.lbl_porcento.setText("0%")
        self.barra_total.setRange(0, 100)
        self.barra_total.setValue(0)
        self.aviso.show()
        self.btn_parar.show()
        self.btn_parar.setEnabled(True)
        self.btn_parar.setText("PARAR DEPOIS DESTA ETAPA")
        self.btn_conferir.hide()
        self.btn_fontes.hide()
        self.btn_voltar.hide()
        self._stack.setCurrentIndex(PAGINA_RODANDO)

    def _parar(self) -> None:
        self.btn_parar.setEnabled(False)
        self.btn_parar.setText("PARANDO DEPOIS DESTA ETAPA")
        self.stop_requested.emit()

    def on_step(self, indice: int, estado: str, texto: str) -> None:
        if 0 <= indice < len(self._passos):
            self._passos[indice].estado(estado, texto)
        if texto:
            self._log.append(texto)
            self.lbl_log.setText("\n".join(self._log[-14:]))

    def on_progress(self, indice: int, atual: int, total: int) -> None:
        if not (0 <= indice < len(self._passos)) or total <= 0:
            return
        self._passos[indice].barra.setRange(0, total)
        self._passos[indice].barra.setValue(atual)
        geral = (indice + atual / total) / len(self._passos)
        self.barra_total.setValue(int(geral * 100))
        self.lbl_porcento.setText(f"{int(geral * 100)}%")

    def on_finished(self, resultado: str, mensagem: str) -> None:
        """resultado: concluida, parada ou erro."""
        self._terminou = True
        self.aviso.hide()
        self.btn_parar.hide()
        self.btn_voltar.show()
        revisar = resultado != "erro" and "fontfix" in self._ids
        self.btn_fontes.setVisible(revisar)
        self.btn_conferir.setVisible(resultado != "erro" and not revisar)
        titulo, estado = {
            "concluida": ("Sequência concluída", "Pode voltar a usar o CATIA"),
            "parada": ("Sequência parada", "Pode voltar a usar o CATIA"),
            "erro": ("A sequência parou por um erro", "Confira o desenho antes de continuar"),
        }[resultado]
        self.lbl_run_titulo.setText(titulo)
        self.lbl_estado.setText(estado)
        if resultado == "concluida":
            self.barra_total.setValue(100)
            self.lbl_porcento.setText("100%")
        if mensagem:
            self._log.append(mensagem.replace("\r\n", "\n"))
            self.lbl_log.setText("\n".join(self._log[-14:]))

    def set_compact(self, compact: bool) -> None:
        # Na janela estreita ficam o resumo e o botao; as etapas continuam como estavam marcadas.
        self._centro_escolha.setVisible(not compact)
        self._centro_rodando.setVisible(not compact)


class _LinhaCheck(QFrame):
    def __init__(self, nome: str, descricao: str):
        super().__init__()
        self.setObjectName("linhaLista")
        self.setFixedHeight(64)
        h = QHBoxLayout(self)
        h.setContentsMargins(12, 0, 12, 0)
        h.setSpacing(12)
        self.caixa = Caixa(True)
        h.addWidget(self.caixa)
        self.marca = QLabel()
        self.marca.setFixedSize(30, 30)
        self.marca.setAlignment(Qt.AlignCenter)
        h.addWidget(self.marca)
        textos = QVBoxLayout()
        textos.setSpacing(0)
        textos.addStretch(1)
        textos.addWidget(label(nome, "passoNome"))
        self.sub = largura_livre(label(descricao, "passoSub"))
        textos.addWidget(self.sub)
        textos.addStretch(1)
        h.addLayout(textos, 2)
        self.lbl_resultado = largura_livre(label("Ainda não rodou", "passoSub"))
        h.addWidget(self.lbl_resultado, 2)
        self.btn_revisar = button("Revisar  ›", "ligacao")
        h.addWidget(self.btn_revisar)
        self.marcar("neutro")

    def marcar(self, estado: str) -> None:
        cor, tinta, ic = {
            "ok": (T.GREEN, T.GREEN_INK, "check"), "erro": (T.RED, T.RED_INK, "x"),
            "aviso": (T.AMBER, T.RED_INK, "alert"), "neutro": (T.CARD_2, T.MUTED, "minus"),
        }[estado]
        self.marca.setStyleSheet(f"background: {cor}; border-radius: 15px;")
        self.marca.setPixmap(pixmap(ic, tinta, 16, 2.6))


class CheckGeralPage(QWidget):
    """Resultado do que ja rodou nesta sessao: nada aqui e inventado ou estimado."""

    run_requested = Signal(list)
    revisar_requested = Signal(str)
    compare_requested = Signal()

    def __init__(self):
        super().__init__()
        self._font = None
        self._pos = None
        self._flags = None
        self._template = None
        self._connected = False
        self._has_drawing = False
        h = QVBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        caixa = moldura()
        col = QVBoxLayout(caixa)
        col.setContentsMargins(18, 14, 18, 14)
        col.setSpacing(10)
        self.btn_rodar = botao_grande("RODAR OS CHECKS")
        self.btn_rodar.setFixedHeight(38)
        self.btn_rodar.clicked.connect(self._rodar)
        topo, self.lbl_sub = cabecalho("Resultado do Check", None, self.btn_rodar)
        self.lbl_sub.setText("O desenho não é alterado.")
        col.addLayout(topo)
        cartoes = QHBoxLayout()
        cartoes.setSpacing(8)
        self.card_revisar = Cartao("com itens para revisar", "vermelho")
        self.card_ok = Cartao("sem problemas", "verde")
        self.card_nao = Cartao("não rodou")
        for c in (self.card_revisar, self.card_ok, self.card_nao):
            cartoes.addWidget(c, 1)
        col.addLayout(cartoes)
        self.linha_font = _LinhaCheck("Font Size Check", "Confere o tamanho dos textos")
        self.linha_pos = _LinhaCheck("Position and Zone Check", "Callouts, zonas e quantidades")
        self.linha_flags = _LinhaCheck("Check de Flags", "Confere sem corrigir")
        self.linha_flags.btn_revisar.clicked.connect(lambda: self.revisar_requested.emit("flagcheck"))
        self.linha_template = _LinhaCheck("Check de Template", "Numeração, formato e escala de cada folha")
        self.linha_template.btn_revisar.clicked.connect(lambda: self.revisar_requested.emit("templatecheck"))
        self.linha_font.btn_revisar.clicked.connect(lambda: self.revisar_requested.emit("font"))
        self.linha_pos.btn_revisar.clicked.connect(lambda: self.revisar_requested.emit("poszone"))
        for l in (self.linha_font, self.linha_pos, self.linha_flags, self.linha_template):
            l.caixa.clicked.connect(self._atualizar)
            col.addWidget(l)
        # Programa externo: nao tem resultado para mostrar aqui, so abre.
        self.linha_compare = _LinhaCheck("Compare DWG", "Programa externo, abre em janela própria")
        self.linha_compare.caixa.hide()
        self.linha_compare.lbl_resultado.setText("Não informa resultado para o HUB")
        self.linha_compare.btn_revisar.setText("Abrir  ›")
        self.linha_compare.btn_revisar.clicked.connect(self.compare_requested)
        col.addWidget(self.linha_compare)
        col.addStretch(1)
        h.addWidget(caixa)
        self._atualizar()

    def set_catia_state(self, connected: bool, document: str, desenho: bool = False) -> None:
        self._connected = connected
        self._has_drawing = desenho or eh_desenho(document)
        self._atualizar()

    def on_font(self, report) -> None:
        if report is not None:
            self._font = report
            self._atualizar()

    def definir_part_list(self, tem: bool) -> None:
        self._tem_part_list = tem
        self._atualizar()

    def on_poszone(self, report) -> None:
        if report is not None:
            self._pos = report
            self._atualizar()

    def on_flags(self, report) -> None:
        if report is not None:
            self._flags = report
            self._atualizar()

    def on_template(self, report) -> None:
        if report is not None:
            self._template = report
            self._atualizar()

    def pendencias_flags(self) -> int:
        return self._flags.erradas if self._flags else 0

    def pendencias_template(self) -> int:
        return self._template.errados if self._template else 0

    def pendencias_font(self) -> int:
        return self._font.total_nok if self._font else 0

    def pendencias_pos(self) -> int:
        if not self._pos:
            return 0
        return len(self._pos.pendencias) if self._pos.abertas is None else self._pos.abertas

    def _marcados(self) -> list:
        saida = []
        if self.linha_font.caixa.isChecked():
            saida.append("font")
        if self.linha_pos.caixa.isChecked():
            saida.append("poszone")
        if self.linha_flags.caixa.isChecked():
            saida.append("flagcheck")
        if self.linha_template.caixa.isChecked():
            saida.append("templatecheck")
        return saida

    def _rodar(self) -> None:
        self.run_requested.emit(self._marcados())

    def _atualizar(self) -> None:
        revisar = ok = nao = 0
        if self._font is None:
            nao += 1
            self.linha_font.marcar("neutro")
            self.linha_font.lbl_resultado.setText("Ainda não rodou")
        else:
            r = self._font
            self.linha_font.sub.setText(f"{r.total_nok} fora do padrão de {r.total_items} itens")
            self.linha_font.lbl_resultado.setText(f"{r.total_ok} corretos · {r.total_nok} fora do padrão")
            if r.total_nok:
                revisar += 1
                self.linha_font.marcar("erro")
            else:
                ok += 1
                self.linha_font.marcar("ok")
        if self._pos is None:
            nao += 1
            self.linha_pos.marcar("neutro")
            self.linha_pos.lbl_resultado.setText("Ainda não rodou")
        else:
            r = self._pos
            self.linha_pos.sub.setText(f"{len(r.callouts)} callouts, {self.pendencias_pos()} para revisar")
            self.linha_pos.lbl_resultado.setText(f"{r.counters.validos} válidos · {r.counters.grupo} ambíguos · {r.counters.conflito} inconsistentes")
            if self.pendencias_pos():
                revisar += 1
                self.linha_pos.marcar("aviso")
            elif not getattr(self, "_tem_part_list", False):
                # Sem o Part List so da para dizer que os baloes foram lidos: nada foi comparado.
                revisar += 1
                self.linha_pos.marcar("aviso")
                self.linha_pos.sub.setText(f"{len(r.callouts)} callouts lidos · falta anexar o Part List")
                self.linha_pos.lbl_resultado.setText("Sem Part List: zona e quantidade não foram comparadas")
            else:
                ok += 1
                self.linha_pos.marcar("ok")
        if self._flags is None:
            nao += 1
            self.linha_flags.marcar("neutro")
            self.linha_flags.lbl_resultado.setText("Ainda não rodou")
        else:
            r = self._flags
            self.linha_flags.lbl_resultado.setText(f"{r.certas} de {r.flags} corretas")
            if r.erradas:
                revisar += 1
                self.linha_flags.marcar("erro")
            else:
                ok += 1
                self.linha_flags.marcar("ok")
        if self._template is None:
            nao += 1
            self.linha_template.marcar("neutro")
            self.linha_template.lbl_resultado.setText("Ainda não rodou")
        else:
            r = self._template
            self.linha_template.lbl_resultado.setText(f"{r.certos} certos · {r.errados} errados · {r.conferir} para conferir")
            if r.errados or r.conferir:
                revisar += 1
                self.linha_template.marcar("erro" if r.errados else "aviso")
            else:
                ok += 1
                self.linha_template.marcar("ok")
        self.card_revisar.valor(revisar)
        self.card_ok.valor(ok)
        self.card_nao.valor(nao)
        marcados = self._marcados()
        self.btn_rodar.setText(f"RODAR {len(marcados)} CHECK{'S' if len(marcados) != 1 else ''}")
        self.btn_rodar.setEnabled(bool(marcados) and self._connected and self._has_drawing)

    def set_compact(self, compact: bool) -> None:
        pass
