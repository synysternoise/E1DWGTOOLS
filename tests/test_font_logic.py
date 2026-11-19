"""Regras do Font Size Check que nao dependem do CATIA.

Uso:  python -m unittest discover -s tests
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from engine import font_check as fc  # noqa: E402
from engine.catia_bridge import CAMPO, REGISTRO, CatiaError, parse_number, parse_response  # noqa: E402


class Formato(unittest.TestCase):
    def test_padroes_de_todos_os_formatos(self):
        self.assertEqual(fc.get_standard_sizes("A4"), (0.07, 0.125))
        self.assertEqual(fc.get_standard_sizes("A3"), (0.17, 0.25))
        self.assertEqual(fc.get_standard_sizes("A1"), (0.17, 0.25))
        self.assertEqual(fc.get_standard_sizes("A2"), (0.108, 0.193))
        for f in ("A0", "E3", "E0", "3A0"):
            self.assertEqual(fc.get_standard_sizes(f), (0.197, 0.277))
        self.assertIsNone(fc.get_standard_sizes("B1"))

    def test_normaliza_como_o_vba(self):
        self.assertEqual(fc.normalize_sheet_format(" a1 "), "A1")
        self.assertEqual(fc.normalize_sheet_format("A4\r\n"), "A4")
        self.assertEqual(fc.normalize_sheet_format("\tE0"), "E0")
        self.assertEqual(fc.normalize_sheet_format("E3\xa0"), "E3")

    def test_text68_vem_primeiro(self):
        textos = [["68", "A2"], ["T", "A0"], ["T", "A2"]]
        self.assertEqual(fc.format_from_background(textos), "A2")

    def test_text68_invalido_procura_nos_demais(self):
        textos = [["68", "SIZE"], ["T", "SIZE A1"], ["T", "A0"]]
        self.assertEqual(fc.format_from_background(textos), "A0")

    def test_sem_formato(self):
        self.assertEqual(fc.format_from_background([["T", "SIZE A1"]]), "")

    def test_pedido_de_formato_repete_ate_valido(self):
        respostas = iter(["z9", " a2 "])
        avisos = []
        r = fc._ask_sheet_format(lambda *a: next(respostas), lambda m, t: avisos.append(m))
        self.assertEqual(r, "A2")
        self.assertEqual(avisos, ["Formato 'Z9' não reconhecido."])

    def test_pedido_de_formato_cancelado(self):
        self.assertEqual(fc._ask_sheet_format(lambda *a: None, None), "")


class Tamanho(unittest.TestCase):
    def test_tolerancia(self):
        padroes = (0.17, 0.25)
        self.assertTrue(fc.is_standard(0.17, padroes))
        self.assertTrue(fc.is_standard(0.25, padroes))
        self.assertTrue(fc.is_standard(0.1705, padroes))
        self.assertFalse(fc.is_standard(0.18, padroes))

    def test_mostra_tres_casas(self):
        self.assertEqual(fc.format_inch(0.17, ","), '0,170"')
        self.assertEqual(fc.format_inch(0.1705, ","), '0,171"')
        self.assertEqual(fc.format_inch(0.1705, "."), '0.171"')
        self.assertEqual(fc.format_inch(0.0, ","), '0,000"')

    def test_padrao_sem_zeros_a_mais(self):
        self.assertEqual(fc.format_number(0.17, ","), "0,17")
        self.assertEqual(fc.format_number(0.125, ","), "0,125")


class Texto(unittest.TestCase):
    def test_quebras_de_linha(self):
        self.assertEqual(fc.clean_item_text("a\r\nb\nc", False), "a / b / c")

    def test_limite_de_60(self):
        self.assertEqual(fc.clean_item_text("x" * 60, False), "x" * 60)
        self.assertEqual(fc.clean_item_text("y" * 61, False), "y" * 57 + "...")

    def test_prefixo_de_cota(self):
        self.assertEqual(fc.clean_item_text("10", True), "Cota 10")


class Resumo(unittest.TestCase):
    def setUp(self):
        self.r = fc.FontReport("c:\\x.CATDrawing", "123", ["A1", "A0"], ['Padrões A1: 0,17" e 0,25"'], 3, 2, 1)

    def test_resumo(self):
        self.assertEqual(self.r.resumo, "PN 123   |   Formato A1, A0\r\n1 fora do padrão de 3 itens analisados")

    def test_mensagem(self):
        self.assertIn('Formato: A1, A0\r\nPadrões A1: 0,17" e 0,25"\r\n\r\nItens analisados: 3', self.r.mensagem)
        self.assertTrue(self.r.mensagem.endswith("Corretos: 2\r\nIncorretos: 1"))


class Protocolo(unittest.TestCase):
    def test_registros(self):
        raw = "OK" + REGISTRO + CAMPO.join(["a", "b"]) + REGISTRO + "c"
        self.assertEqual(parse_response(raw), [["a", "b"], ["c"]])

    def test_texto_com_quebra_de_linha_nao_separa(self):
        raw = "OK" + REGISTRO + "linha 1\nlinha 2\tcom tab"
        self.assertEqual(parse_response(raw), [["linha 1\nlinha 2\tcom tab"]])

    def test_erro_vira_excecao(self):
        with self.assertRaises(CatiaError) as c:
            parse_response("ERR" + CAMPO + "1001" + CAMPO + "Sem documento")
        self.assertEqual(str(c.exception), "Sem documento")
        self.assertEqual(c.exception.number, 1001)

    def test_resposta_vazia_e_invalida(self):
        for raw in (None, "", "qualquer coisa"):
            with self.assertRaises(CatiaError):
                parse_response(raw)

    def test_numero_com_virgula(self):
        self.assertEqual(parse_number("4,318"), 4.318)
        self.assertEqual(parse_number("4.318"), 4.318)
        self.assertEqual(parse_number("2,5E-03"), 0.0025)


if __name__ == "__main__":
    unittest.main()
