"""Update Template: numeracao da margem e da grade pela folha, e quais vistas de zona sao apagadas."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from engine import atualizar_template as at  # noqa: E402


class VistasDeZona(unittest.TestCase):
    def test_nomes_reais_do_template(self):
        for nome in ("ZONE", "zone", "ZONE[1]", "ZONE A0", "ZONE A0[3]", "ZONES_A0_SHT1", "ZONES_A0_SHT1[2]",
                     "ZONES_A0_SHT2", "ZONES_A1_SHT2", "ZONE 3A0", "ZONES_E3_SHT"):
            self.assertTrue(at.is_aux_view(nome), nome)

    def test_vista_do_usuario_nao_e_apagada(self):
        for nome in ("MY ZONE VIEW", "ZONE DETAIL", "ZONEX", "ZONE A9", "ZONES_A0", "ZONES_A0_SHTX", "PLAN VIEW", "1F7"):
            self.assertFalse(at.is_aux_view(nome), nome)


class Numeracao(unittest.TestCase):
    def test_dezena_da_folha(self):
        self.assertEqual([at.numero_na_folha(9, n) for n in (1, 2, 3, 5)], [9, 29, 39, 59])

    def test_rotulo_da_grade(self):
        self.assertEqual(at.zone_label("F6", 2), "F26")
        self.assertEqual(at.zone_label("e3", 5), "E53")
        self.assertEqual(at.zone_label("E005", 3), "E035")
        self.assertEqual(at.zone_label("A9", 1), "A9")

    def test_o_que_nao_e_rotulo_fica_como_esta(self):
        for texto in ("NOTA", "G6", "F", "F0", "F1234", "6", "F6A", ""):
            self.assertEqual(at.zone_label(texto, 2), "", texto)


class Margem(unittest.TestCase):
    def textos(self, colunas=4, altura=594.0):
        t = []
        for c in range(1, colunas + 1):
            t += [(str(c), 100.0 * c, 5.0), (str(c), 100.0 * c, altura - 5.0)]
        return t

    def test_acha_os_numeros_de_cima_e_de_baixo(self):
        m = at.margin_columns(self.textos(), 841.0, 594.0)
        self.assertEqual(len(m), 8)
        self.assertEqual(sorted({c for _, _, c in m}), [1, 2, 3, 4])

    def test_numero_solto_da_legenda_nao_entra(self):
        # Um "2" perto da borda de baixo, como o numero da folha: nao tem par em cima na mesma coluna.
        m = at.margin_columns(self.textos() + [("2", 780.0, 22.0), ("7", 650.0, 30.0)], 841.0, 594.0)
        self.assertEqual(len(m), 8)
        self.assertNotIn((780.0, 22.0, 2), m)

    def test_numero_no_meio_da_folha_nao_entra(self):
        m = at.margin_columns(self.textos() + [("3", 300.0, 300.0)], 841.0, 594.0)
        self.assertEqual(len(m), 8)

    def test_poucas_colunas_ou_so_um_lado_nao_valem(self):
        self.assertEqual(at.margin_columns(self.textos(2), 841.0, 594.0), [])
        so_baixo = [(str(c), 100.0 * c, 5.0) for c in range(1, 6)]
        self.assertEqual(at.margin_columns(so_baixo, 841.0, 594.0), [])
        self.assertEqual(at.margin_columns(self.textos(), 0.0, 594.0), [])


class GradesCopiadasDeUmaVez(unittest.TestCase):
    DADOS = [("ZONE", 0.0, 0.0), ("ZONES_A1_SHT1", 10.0, 20.0)]

    def test_casa_pelo_nome_mesmo_com_contador_e_fora_de_ordem(self):
        self.assertEqual(at.emparelhar(self.DADOS, ["ZONES_A1_SHT1[2]", "ZONE[3]"]), [self.DADOS[1], self.DADOS[0]])

    def test_sem_nome_igual_segue_a_ordem(self):
        self.assertEqual(at.emparelhar(self.DADOS, ["View.7", "View.8"]), self.DADOS)

    def test_dois_nomes_iguais_no_template(self):
        dados = [("ZONE", 0.0, 0.0), ("ZONE", 5.0, 5.0)]
        self.assertEqual(at.emparelhar(dados, ["ZONE[2]", "ZONE[3]"]), dados)


class TemplateGuardado(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.pasta = tempfile.mkdtemp(prefix="guardado_")
        os.environ["E1DWGTOOLS_TEMPLATES"] = os.path.join(self.pasta, "lidos.json")
        self.arquivo = os.path.join(self.pasta, "T.CATDrawing")
        with open(self.arquivo, "wb") as f:
            f.write(b"template")
        self.links = {"Text.5": at.TextLink("A | B", "|", ["PN", "REV"], 10.0, 20.0, "Text.5")}
        self.margem = [(100.0, 5.0, 1), (100.0, 589.0, 1)]

    def tearDown(self):
        os.environ.pop("E1DWGTOOLS_TEMPLATES", None)

    def test_devolve_o_que_guardou(self):
        self.assertIsNone(at.ler_template_guardado(self.arquivo))
        at.guardar_template(self.arquivo, self.links, self.margem)
        self.assertEqual(at.ler_template_guardado(self.arquivo), (self.links, self.margem))

    def test_template_alterado_e_lido_de_novo(self):
        at.guardar_template(self.arquivo, self.links, self.margem)
        with open(self.arquivo, "wb") as f:
            f.write(b"template novo, maior")
        self.assertIsNone(at.ler_template_guardado(self.arquivo))

    def test_guardado_estragado_nao_atrapalha(self):
        with open(os.environ["E1DWGTOOLS_TEMPLATES"], "w") as f:
            f.write("{isto nao e json")
        self.assertIsNone(at.ler_template_guardado(self.arquivo))
        at.guardar_template(self.arquivo, self.links, self.margem)
        self.assertEqual(at.ler_template_guardado(self.arquivo), (self.links, self.margem))

    def test_template_que_nao_existe(self):
        self.assertIsNone(at.ler_template_guardado(os.path.join(self.pasta, "nao_existe.CATDrawing")))


if __name__ == "__main__":
    unittest.main()
