"""Sequencia do Fix Flags que nao depende do CATIA.

Uso:  python -m unittest discover -s tests
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from engine import fix_flags as ff  # noqa: E402
from engine.catia_bridge import CatiaError  # noqa: E402

CONTADORES_1 = ["3", "2", "1", "1", "1", "1", "1", "1", "0", "0", "0"]
FLAG_C = ["F", "3", "1", "Text.1", "OBJ 7", "NL006", "NL0006", "57", "1", "C"]
FLAG_J = ["F", "3", "2", "Text.2", "OBJ 7", "AB0123", "AB0123", "8", "2", "J"]


class PonteFalsa:
    def __init__(self, situacao, folhas=(), falha_em=None):
        self.situacao = situacao
        self.folhas = list(folhas)
        self.falha_em = falha_em
        self.chamadas = []

    def call(self, script, funcao, *args):
        self.chamadas.append((funcao,) + args)
        if funcao == "LerDesenho":
            return [self.situacao]
        if funcao == "Finalizar":
            return []
        i = args[1]
        if self.falha_em == i:
            raise CatiaError("CATIA caiu", 462)
        return self.folhas[i - 1]


def rodar(ponte, confirma=True, **kw):
    avisos, perguntas = [], []

    def confirm(m, t):
        perguntas.append((m, t))
        return confirma

    rep = ff.run_fix_flags(ponte, confirm, lambda m, t: avisos.append((m, t)), **kw)
    return rep, avisos, perguntas


class Sequencia(unittest.TestCase):
    def test_sem_documento_avisa_e_nao_pergunta(self):
        ponte = PonteFalsa(["0"])
        rep, avisos, perguntas = rodar(ponte)
        self.assertIsNone(rep)
        self.assertEqual(avisos, [(ff.SEM_DOCUMENTO, ff.TITULO_AVISO)])
        self.assertEqual(perguntas, [])

    def test_nao_e_desenho_avisa_e_nao_pergunta(self):
        rep, avisos, perguntas = rodar(PonteFalsa(["1"]))
        self.assertIsNone(rep)
        self.assertEqual(avisos, [(ff.NAO_E_DESENHO, ff.TITULO_AVISO)])
        self.assertEqual(perguntas, [])

    def test_responder_nao_nao_toca_no_desenho(self):
        ponte = PonteFalsa(["2", "D.CATDrawing", "2"])
        rep, avisos, perguntas = rodar(ponte, confirma=False)
        self.assertIsNone(rep)
        self.assertEqual(perguntas, [(ff.CONFIRMACAO, ff.TITULO_CONFIRMA)])
        self.assertEqual([c[0] for c in ponte.chamadas], ["LerDesenho"])

    def test_soma_as_folhas_e_atualiza_no_fim(self):
        folha = [["N", "Sheet.1"] + CONTADORES_1, FLAG_C, FLAG_J]
        ponte = PonteFalsa(["2", "D.CATDrawing", "2"], [folha, folha])
        vistos = []
        rep, _, _ = rodar(ponte, progress=lambda a, b: vistos.append((a, b)))
        self.assertEqual((rep.textos, rep.flags, rep.corrigidas, rep.ja_corretas), (6, 4, 2, 2))
        self.assertEqual(vistos, [(1, 2), (2, 2)])
        self.assertEqual(ponte.chamadas[-1], ("Finalizar", "D.CATDrawing", True))
        self.assertEqual([i.order for i in rep.items], [1, 2, 3, 4])
        self.assertEqual(rep.items[0].tipo, "Right Flag fixa")
        self.assertEqual(rep.items[1].tipo, "Left Flag (Text Editor)")
        self.assertTrue(rep.items[0].ok)

    def test_parar_entre_folhas(self):
        folha = [["N", "Sheet.1"] + CONTADORES_1]
        ponte = PonteFalsa(["2", "D.CATDrawing", "3"], [folha, folha, folha])
        pedidos = iter([False, True])
        rep, _, _ = rodar(ponte, should_stop=lambda: next(pedidos))
        self.assertTrue(rep.stopped)
        self.assertEqual(rep.textos, 3)
        self.assertEqual(ponte.chamadas[-1], ("Finalizar", "D.CATDrawing", True))

    def test_erro_da_folha_guarda_o_que_ja_foi_feito_e_so_limpa_a_selecao(self):
        folha = [["N", "Sheet.1"] + CONTADORES_1, FLAG_C, ["ABORT", "91", "Objeto apagado"]]
        ponte = PonteFalsa(["2", "D.CATDrawing", "2"], [folha, folha])
        with self.assertRaises(ff.FixInterrompido) as c:
            rodar(ponte)
        self.assertEqual(c.exception.number, 91)
        self.assertEqual(c.exception.report.corrigidas, 1)
        self.assertEqual(len(c.exception.report.items), 1)
        self.assertEqual(ponte.chamadas[-1], ("Finalizar", "D.CATDrawing", False))
        self.assertEqual(c.exception.mensagem, "O fix foi interrompido.\r\n\r\nErro: 91\r\nDescrição: Objeto apagado")

    def test_catia_cai_no_meio(self):
        folha = [["N", "Sheet.1"] + CONTADORES_1, FLAG_C]
        ponte = PonteFalsa(["2", "D.CATDrawing", "2"], [folha, folha], falha_em=2)
        with self.assertRaises(ff.FixInterrompido) as c:
            rodar(ponte)
        self.assertEqual(c.exception.number, 462)
        self.assertEqual(c.exception.report.corrigidas, 1)

    def test_erro_ao_ler_o_desenho(self):
        class Quebrada(PonteFalsa):
            def call(self, script, funcao, *args):
                raise CatiaError("sem resposta", 5)

        with self.assertRaises(ff.FixInterrompido) as c:
            rodar(Quebrada(["0"]))
        self.assertIsNone(c.exception.report)

    def test_flag_com_problema_nao_conta_como_ok(self):
        for resultado in (ff.RESTAURADA, ff.NAO_RESTAURADA, ff.ERRO):
            registro = FLAG_C[:-1] + [resultado]
            rep = ff.FixReport("D")
            ff._ler_folha(rep, [["N", "S"] + CONTADORES_1, registro])
            self.assertFalse(rep.items[0].ok)

    def test_mensagem_final_como_no_vba(self):
        rep = ff.FixReport("D", textos=10, flags=9, objeto=8, text_editor=1, cadeado=2, corrigidas=3,
                           ja_corretas=4, ignoradas=1, falhas=1, restauradas=1, erros=0)
        self.assertEqual(
            rep.mensagem,
            "Fix de Flag Notes concluído.\r\n\r\n"
            "DrawingTexts analisados: 10\r\nFlags reconhecidas: 9\r\n\r\n"
            "Flags no objeto inteiro: 8\r\nFlags pelo Text Editor: 1\r\nFlags fixas com cadeado: 2\r\n\r\n"
            "Flags corrigidas: 3\r\nFlags que já estavam corretas: 4\r\nTextos ignorados: 1\r\n"
            "Falhas de validação: 1\r\nTextos restaurados: 1\r\nErros: 0\r\n\r\n"
            "Execute o Check novamente para confirmar.",
        )


class Script(unittest.TestCase):
    def test_script_em_ascii(self):
        caminho = os.path.join(os.path.dirname(ff.__file__), "catia_scripts", ff.SCRIPT)
        with open(caminho, "rb") as f:
            f.read().decode("ascii")


if __name__ == "__main__":
    unittest.main()
