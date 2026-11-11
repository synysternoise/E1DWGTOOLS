"""Prova do layout novo: os tres modos, o cartao de resumo e o voo, com fotos. Nao precisa de desenho aberto."""
import os
import sys
import time

R = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
sys.path.insert(0, os.path.join(R, "src"))
from PySide6.QtCore import QCoreApplication, QEventLoop  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from ui_qt import hub_window as hw  # noqa: E402
from ui_qt import voo as vo  # noqa: E402

SAIDA = sys.argv[1]
os.makedirs(SAIDA, exist_ok=True)
falhas = []


def confere(nome, ok, extra=""):
    print(("[OK] " if ok else "[FALHOU] ") + nome, extra if not ok else "", flush=True)
    if not ok:
        falhas.append(nome)


def gira(segundos=0.4):
    fim = time.perf_counter() + segundos
    while time.perf_counter() < fim:
        QCoreApplication.processEvents(QEventLoop.AllEvents, 20)


def foto(w, nome):
    gira(0.3)
    w.grab().save(os.path.join(SAIDA, nome + ".png"))


app = QApplication(sys.argv)
j = hw.HubWindow()
j.show()
gira(2.5)

# ---- voo ----
confere("arco: no chão nas pontas e no alto no meio", vo.altura_no_arco(0, 26) == 0 and vo.altura_no_arco(1, 26) == 0 and vo.altura_no_arco(.5, 26) == 26)
confere("fração nunca passa de 0 a 1", vo.fracao(5, 0) == 0 and vo.fracao(12, 10) == 1 and vo.fracao(3, 10) == .3)
confere("parado: pronto para decolar", j.voo.posicao() == 0 and j.voo.estado() == "Pronto para decolar", j.voo.estado())
j._on_busy(True)
j._titulo_voo("Fix Flags")
confere("ocupado: sai do zero", j.voo.posicao() == 0 and j.voo.estado() == "CATIA trabalhando")
j._on_any_progress(6, 10)
confere("progresso 6 de 10", abs(j.voo.posicao() - .6) < 1e-9 and j.voo.estado() == "6 de 10", j.voo.estado())
confere("o cartão acompanha", abs(j.cartao.voo.posicao() - .6) < 1e-9)
foto(j, "1_ampliado_voando")
j._on_busy(False)
confere("terminou: pousou", j.voo.posicao() == 1 and j.voo.estado() == "Pousou: CATIA livre", j.voo.estado())
foto(j, "2_ampliado_pousou")
j._on_busy(True)
j._voo_seq(["update", "symbol", "flags", "fontfix"])
j._voo_seq_progresso(1, 1, 2)
confere("sequência: um voo só para as 4 etapas", abs(j.voo.posicao() - .375) < 1e-9 and j.voo.estado() == "Etapa 2 de 4", (j.voo.posicao(), j.voo.estado()))
j._on_busy(False)

# ---- canto ----
geo = j.geometry()
j.btn_compact.click()
gira(1.0)
confere("canto: 460 de largura", j.width() <= 470 and j._modo == hw.MODO_CANTO, j.width())
confere("canto: mostra a faixa de ícones e o voo", j._faixa.isVisible() and j.voo.isVisible() and not j._rail.isVisible())
j._faixa.botoes["Fix Flags"].click()
gira()
confere("faixa: troca de ferramenta", j._pages.currentWidget() is j.flags_page and j.rail_buttons["Fix Flags"].isChecked())
j._faixa.botoes_aba[1].click()
gira()
confere("faixa: troca de aba", j._rail.currentIndex() == hw.ABA_CHECK and j.pills["Check"].isChecked() and j._pages.currentWidget() is j.geral_page)
foto(j, "3_canto")
j._faixa.botoes_aba[0].click()
gira()

# ---- so icones ----
j.set_modo(hw.MODO_MINI)
gira(1.0)
confere("só ícones: barra fina", j.width() <= 70 and j._mini.isVisible() and not j._cabecalho.isVisible() and not j._corpo.isVisible(), (j.width(), j.height()))
confere("só ícones: marca a mesma ferramenta", j._mini.botoes["Fix Flags"].isChecked())
j._mini.botoes["Symbol Shape Converter"].click()
gira(0.6)
confere("clique no ícone abre o cartão", j.cartao.isVisible() and j.cartao.lbl_nome.text() == "Symbol Shape Converter", j.cartao.lbl_nome.text())
confere("o cartão fica ao lado da barra", j.cartao.frameGeometry().right() < j.frameGeometry().left() or j.cartao.frameGeometry().left() > j.frameGeometry().right())
confere("o cartão traz o resumo da tela", len(j._resumo_da_pagina()) >= 1, j._resumo_da_pagina())
foto(j, "4_so_icones_barra")
foto(j.cartao, "5_so_icones_cartao")
j._mini.botoes["Symbol Shape Converter"].click()
gira()
confere("clicar de novo fecha o cartão", not j.cartao.isVisible())
j._mini.botoes_aba[2].click()
gira()
confere("barra: troca de aba", j._rail.currentIndex() == hw.ABA_ENVIO and j._pages.currentWidget() is j.split3d_page)
j._atualizar_contagens()
j._mini.selo("Fix Flags", 3, "#fff", "#900")
confere("selo no ícone", j._mini.selos["Fix Flags"].text() == "3")
j._mini.btn_canto.click()
gira(1.0)
confere("da barra para o canto", j._modo == hw.MODO_CANTO and j._cabecalho.isVisible() and 400 < j.width() <= 470, j.width())
j.btn_mini.click()
gira(1.0)
j._mini.btn_cheio.click()
gira(1.0)
confere("da barra para o ampliado: volta ao tamanho de antes", j._modo == hw.MODO_CHEIO and j.geometry() == geo and j._rail.isVisible() and not j._faixa.isVisible(), (j.geometry(), geo))
foto(j, "6_ampliado_de_volta")
j.close()
print("RESULTADO:", "TUDO CERTO" if not falhas else f"{len(falhas)} FALHAS: {falhas}", flush=True)
sys.exit(1 if falhas else 0)
