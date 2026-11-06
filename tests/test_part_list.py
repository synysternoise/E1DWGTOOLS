"""Regras do Part List e do mover balao, sem Excel e sem CATIA."""
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace as NS

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from engine import part_list as pl  # noqa: E402
from engine import pos_zone as pz  # noqa: E402


class TestNormalizar(unittest.TestCase):
    def test_posicao(self):
        for entrada, esperado in (("0012", "12"), (12.0, "12"), ("'007", "7"), (" 1 2 ", "12"), ("0", "0"), ("000", "0"), ("a1", "A1"), (None, ""), ("", "")):
            self.assertEqual(pl.normalizar_posicao(entrada), esperado, entrada)

    def test_zona(self):
        self.assertEqual(pl.normalizar_zona(" d-005 "), "D005")
        self.assertEqual(pl.normalizar_zona("D005; D006"), "D005;D006")
        self.assertEqual(pl.normalizar_zona(None), "")

    def test_celula_com_erro_conta_como_vazia(self):
        self.assertEqual(pl.normalizar_posicao(-2146826246), "")
        self.assertEqual(pl.converter_quantidade(-2146826246), 0.0)
        self.assertEqual(pl.texto_exibido(-2146826246, lambda: "#N/A"), "")

    def test_texto_exibido(self):
        self.assertEqual(pl.texto_exibido(12.0, lambda: "0012"), "0012")
        self.assertEqual(pl.texto_exibido(12.0, lambda: "####"), "12")
        self.assertEqual(pl.texto_exibido(12.0, lambda: ""), "12")
        self.assertEqual(pl.texto_exibido(" A1 ", lambda: "nao usa"), "A1")


class TestConsolidar(unittest.TestCase):
    def _somar(self, linhas):
        d, o = {}, []
        for li in linhas:
            pl.somar_linha(d, o, *li)
        return [d[c] for c in o]

    def test_mesma_efetividade_soma(self):
        r = self._somar([("P", "10", "A001", 2, "x"), ("P", "10", "A001", 3, "x")])
        self.assertEqual(r[0].quantidade, 5)

    def test_efetividades_diferentes_vale_a_maior(self):
        r = self._somar([("P", "10", "A001", 2, "0170"), ("P", "10", "A001", 3, "0190"), ("P", "10", "A001", 1, "0170")])
        self.assertEqual(r[0].quantidade, 3)

    def test_zona_diferente_fica_em_outra_linha(self):
        self.assertEqual(len(self._somar([("P", "10", "A001", 2, "x"), ("P", "010", "A002", 3, "x")])), 2)

    def test_quantidades_negativas_nao_vencem_o_zero(self):
        r = self._somar([("P", "10", "A001", -2, "x"), ("P", "10", "A001", -1, "y")])
        self.assertEqual(r[0].quantidade, 0)


def _callout(n, z, q):
    return NS(number=n, zone=z, qty=q)


class TestComparar(unittest.TestCase):
    def test_tudo_certo(self):
        c = pl.comparar([_callout("10", "A001", 2)], [pl.RegistroSAP("P", "0010", "A-001", 2.0)])
        self.assertEqual(c.desenho["10"], pl.Resultado(True, True, True))
        self.assertEqual(c.sap[0], pl.Resultado(True, True, True))

    def test_zona_errada_nao_confere_quantidade(self):
        c = pl.comparar([_callout("10", "A002", 2)], [pl.RegistroSAP("P", "10", "A001", 2.0)])
        self.assertEqual(c.desenho["10"], pl.Resultado(True, False, False))

    def test_quantidade_errada(self):
        c = pl.comparar([_callout("10", "A001", 3)], [pl.RegistroSAP("P", "10", "A001", 2.0)])
        self.assertEqual(c.desenho["10"], pl.Resultado(True, True, False))

    def test_so_de_um_lado(self):
        c = pl.comparar([_callout("10", "A001", 3)], [pl.RegistroSAP("P", "20", "A001", 2.0)])
        self.assertEqual(c.desenho["10"], pl.Resultado())
        self.assertEqual(c.sap[0], pl.Resultado())
        self.assertEqual(c.faltam_no_desenho([pl.RegistroSAP("P", "20", "A001", 2.0)]), ["20"])

    def test_varias_zonas_no_sap_soma_a_quantidade(self):
        reg = [pl.RegistroSAP("P", "10", "A001", 2.0), pl.RegistroSAP("P", "10", "A002", 3.0)]
        c = pl.comparar([_callout("10", "A001", 5)], reg)
        self.assertEqual(c.desenho["10"], pl.Resultado(True, True, True))
        self.assertEqual(c.sap[1].zona, False)
        self.assertEqual(c.zonas_sap["10"], ["A001", "A002"])

    def test_duas_zonas_no_desenho_basta_uma_bater(self):
        for sap in ("A005", "A006"):
            c = pl.comparar([_callout("10", "A005; A006", 2)], [pl.RegistroSAP("P", "10", sap, 2.0)])
            self.assertEqual(c.desenho["10"], pl.Resultado(True, True, True), sap)
            self.assertEqual(c.sap[0], pl.Resultado(True, True, True), sap)

    def test_duas_zonas_no_desenho_nenhuma_bate(self):
        c = pl.comparar([_callout("10", "A005; A006", 2)], [pl.RegistroSAP("P", "10", "A007", 2.0)])
        self.assertEqual(c.desenho["10"], pl.Resultado(True, False, False))
        self.assertEqual(c.sap[0], pl.Resultado(True, False, False))

    def test_zona_certa_e_a_segunda_do_sap(self):
        reg = [pl.RegistroSAP("P", "10", "A001", 1.0), pl.RegistroSAP("P", "10", "A002", 1.0)]
        c = pl.comparar([_callout("10", "A002", 2)], reg)
        self.assertEqual(c.desenho["10"], pl.Resultado(True, True, True))

    def test_uma_zona_nao_bate_com_outra_que_comeca_igual(self):
        c = pl.comparar([_callout("10", "A0051", 2)], [pl.RegistroSAP("P", "10", "A005", 2.0)])
        self.assertFalse(c.desenho["10"].zona)

    def test_sublinhado_sem_balao_nao_tem_zona(self):
        c = pl.comparar([_callout("10", "", 1)], [pl.RegistroSAP("P", "10", "A005", 1.0)])
        self.assertEqual(c.desenho["10"], pl.Resultado(True, False, False))


def _occ(numero, zona, fonte, sublinhado=False, qtd=1):
    return pz.Occurrence(numero, qtd, zona, "S", "V", 0, 0, fonte, 1, underlined=sublinhado)


class TestZonaDoBalao(unittest.TestCase):
    def test_sublinhado_so_conta_a_quantidade(self):
        c = pz.consolidate([_occ("10", "A001", pz.SOURCE_UNDERLINED), _occ("10", "A005", pz.SOURCE_BALLOON)])
        self.assertEqual((c[0].zone, c[0].qty), ("A005", 2))

    def test_balao_sublinhado_nao_da_zona_se_tem_balao_sem_sublinhado(self):
        c = pz.consolidate([_occ("10", "A001", pz.SOURCE_BALLOON, True), _occ("10", "A005", pz.SOURCE_BALLOON), _occ("10", "A002", pz.SOURCE_BALLOON, True)])
        self.assertEqual((c[0].zone, c[0].qty), ("A005", 3))

    def test_so_balao_sublinhado_ainda_da_a_zona(self):
        c = pz.consolidate([_occ("10", "A001", pz.SOURCE_BALLOON, True)])
        self.assertEqual(c[0].zone, "A001")

    def test_dois_baloes_sem_sublinhado_ficam_as_duas_zonas(self):
        c = pz.consolidate([_occ("10", "A005", pz.SOURCE_BALLOON), _occ("10", "A006", pz.SOURCE_BALLOON)])
        self.assertEqual(c[0].zone, "A005; A006")

    def test_regra_de_uma_posicao_nao_vale_para_outra(self):
        c = pz.consolidate([_occ("10", "A005", pz.SOURCE_BALLOON), _occ("11", "A006", pz.SOURCE_BALLOON, True)])
        self.assertEqual([x.zone for x in c], ["A005", "A006"])


class TestOkManual(unittest.TestCase):
    def setUp(self):
        self._d = tempfile.TemporaryDirectory()
        os.environ["E1DWGTOOLS_OK"] = os.path.join(self._d.name, "sub", "ok.json")

    def tearDown(self):
        del os.environ["E1DWGTOOLS_OK"]
        self._d.cleanup()

    def test_marca_e_sobrevive_a_reabrir(self):
        pl.OkManual("pn1").marcar("C|10", "A001|2", "A001|3.0", "Check")
        self.assertEqual(pl.OkManual("PN1").vale("C|10", "A001|2", "A001|3.0")["origem"], "Check")

    def test_deixa_de_valer_se_o_desenho_ou_o_sap_mudar(self):
        pl.OkManual("pn1").marcar("C|10", "A001|2", "A001|3.0", "Check")
        ok = pl.OkManual("pn1")
        self.assertIsNone(ok.vale("C|10", "A002|2", "A001|3.0"))
        self.assertIsNone(ok.vale("C|10", "A001|2", "A001|4.0"))

    def test_sem_part_list_confere_so_o_desenho(self):
        pl.OkManual("pn1").marcar("C|10", "A001|2", "A001|3.0", "Check")
        self.assertIsNotNone(pl.OkManual("pn1").vale("C|10", "A001|2", None))

    def test_um_desenho_nao_ve_o_ok_do_outro(self):
        pl.OkManual("pn1").marcar("C|10", "x", None, "Design")
        self.assertIsNone(pl.OkManual("pn2").vale("C|10", "x", None))

    def test_tirar(self):
        pl.OkManual("pn1").marcar("C|10", "x", None, "Design")
        pl.OkManual("pn1").tirar("C|10")
        self.assertIsNone(pl.OkManual("pn1").vale("C|10", "x", None))

    def test_arquivo_estragado_nao_derruba(self):
        os.makedirs(os.path.dirname(pl.arquivo_ok()))
        with open(pl.arquivo_ok(), "w") as f:
            f.write("{quebrado")
        self.assertIsNone(pl.OkManual("pn1").vale("C|10", "x", None))


def _texto(i, s, x, y, balao=False):
    return pz.TextRead(i, s, x, y, 3.5, 5, True, pz.CALLOUT_FRAME_CIRCLE if balao else 0, False, True, 0, f"T{i}")


class TestMover(unittest.TestCase):
    ZONAS = [pz.Zone("A001", 100, 100), pz.Zone("A002", 200, 100), pz.Zone("B001", 100, 200)]

    def test_ponto_cai_na_zona_e_o_mais_perto_possivel(self):
        x, y = pz.ponto_na_zona(190, 110, "A001", self.ZONAS)
        self.assertEqual(pz.nearest_zone(x, y, self.ZONAS), "A001")
        self.assertLess(x, 150)
        self.assertGreater(x, 110)  # nao vai para o centro da zona

    def test_ja_dentro_da_zona_fica_dentro(self):
        x, y = pz.ponto_na_zona(105, 105, "A001", self.ZONAS)
        self.assertEqual(pz.nearest_zone(x, y, self.ZONAS), "A001")

    def test_vista_girada_e_com_escala_volta_certo(self):
        v = pz.ViewRead(1, "V", False, 50, 60, 0.25, 0.5)
        ax, ay = v.to_sheet(10, 20)
        dx, dy = v.delta_to_view(7, -3)
        bx, by = v.to_sheet(10 + dx, 20 + dy)
        self.assertAlmostEqual(bx - ax, 7)
        self.assertAlmostEqual(by - ay, -3)

    def test_texto_colado_anda_junto_e_outro_balao_nao(self):
        balao = _texto(1, "58", 100, 100, True)
        flag = _texto(2, "NI1008", 112, 100)
        abaixo = _texto(3, "42", 100, 92)
        outro = _texto(4, "59", 100, 108, True)
        longe = _texto(5, "NOTA", 200, 200)
        comprido = _texto(6, "NOTA GERAL COMPRIDA DEMAIS AQUI", 100, 85)
        v = pz.ViewRead(1, "V", False, 0, 0, 1, 0, [balao, flag, abaixo, outro, longe, comprido])
        self.assertEqual({t.text for t in pz.textos_colados(v, balao)}, {"NI1008", "42"})


if __name__ == "__main__":
    unittest.main()
