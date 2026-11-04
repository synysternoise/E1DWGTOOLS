"""Regras do Position and Zone, do Update Template e dos Splits que nao dependem do CATIA.

Uso:  python -m unittest discover -s tests
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from engine import atualizar_template as at  # noqa: E402
from engine import pos_zone as pz  # noqa: E402
from engine import splits as sp  # noqa: E402


def texto(indice, s, x=0.0, y=0.0, frame=0, inner=0, sub=False, fonte=3.5, ancora=5):
    return pz.TextRead(indice, s, x, y, fonte, ancora, True, frame, sub, inner != 0 or frame == 0, inner)


def vista(nome="V", *textos, fundo=False, x=0.0, y=0.0, escala=1.0, angulo=0.0, indice=3):
    return pz.ViewRead(indice, nome, fundo, x, y, escala, angulo, list(textos))


def analisar(*vistas, linhas=None, folha="Sheet.1"):
    a = pz.Analyzer(lambda f, v: linhas or [])
    a.process_sheet(1, pz.SheetRead(folha, False, 0.0, 0.0, list(vistas)))
    return a


class PalavrasChave(unittest.TestCase):
    def test_ref_precisa_ser_palavra_isolada(self):
        for s in ("REF", "ref", "4 PL REF", "(REF)", "REF."):
            self.assertTrue(pz.has_ref(s), s)
        for s in ("REFERENCE", "PREFERRED", "PREF"):
            self.assertFalse(pz.has_ref(s), s)

    def test_quantidade(self):
        casos = {"4 PL": 4, "4PL": 4, "4 PLCS": 4, "4 PLACES": 4, "(4) PL": 4, "4X PL": 4, "2 REQD": 2, "2 REQ'D": 2,
                 "2 REQUIRED": 2, "REQD 2": 2, "REQ'D: 2": 2, "REQUIRED 2": 2, "ITEM 12, 4 PL": 4,
                 "4 PLATE": 0, "APPLY 4": 0, "SPLICE": 0, "NOTA": 0, "2147483648 PL": 0}
        for s, q in casos.items():
            self.assertEqual(pz.extract_quantity(s), q, s)

    def test_linhas_e_numeros(self):
        self.assertEqual(pz.non_empty_lines("12\r\n\r\n  4 PL\t\n"), ["12", "4 PL"])
        self.assertEqual(pz.normalize_callout("007"), "7")
        self.assertEqual(pz.normalize_callout("0"), "0")
        self.assertFalse(pz.only_digits("12a"))
        self.assertFalse(pz.only_digits(""))

    def test_vista_auxiliar_nao_pega_vista_do_usuario(self):
        for nome in ("ZONE", "zone", "ZONE[1]", "ZONES_A1_SHT2"):
            self.assertTrue(pz.is_aux_view(nome), nome)
        self.assertFalse(pz.is_aux_view("MY ZONE VIEW"))

    def test_lista_sem_repetir(self):
        self.assertEqual(pz.add_unique("A; B", "b"), "A; B")
        self.assertEqual(pz.add_unique("A", "B"), "A; B")
        self.assertEqual(pz.add_unique("", "B"), "B")
        self.assertEqual(pz.add_unique("A", " "), "A")


class Zonas(unittest.TestCase):
    def folha(self, numero_letras=4):
        textos = []
        i = 0
        for k, letra in enumerate("ABCDEF"[:numero_letras]):
            i += 1
            textos.append(texto(i, letra, 8, 700 - 100 * k))
        for c in range(1, 5):
            i += 1
            textos.append(texto(i, str(c), 200 * c, 8))
        return pz.SheetRead("S", False, 1000.0, 800.0, [vista("Background View", *textos, fundo=True, indice=2)])

    def test_zonas_pela_margem(self):
        zonas = pz.zones_from_border(self.folha(), 1)
        self.assertEqual(len(zonas), 16)
        self.assertEqual(pz.nearest_zone(200, 700, zonas), "A001")
        self.assertEqual(pz.nearest_zone(800, 400, zonas), "D004")

    def test_folha_entra_na_dezena_da_coluna(self):
        self.assertEqual(pz.zone_column(9, 1), 9)
        self.assertEqual(pz.zone_column(9, 2), 29)
        self.assertEqual(pz.zone_column(9, 3), 39)
        self.assertEqual(pz.nearest_zone(200, 700, pz.zones_from_border(self.folha(), 2)), "A021")

    def test_poucos_marcadores_nao_formam_zona(self):
        self.assertEqual(pz.zones_from_border(self.folha(1), 1), [])

    def test_zona_pela_vista_auxiliar(self):
        aux = vista("ZONE[1]", texto(1, "A001", 10, 10), texto(2, "b2", 90, 10), texto(3, "NOTA", 5, 5))
        zonas = pz.zones_from_aux_view(pz.SheetRead("S", False, 0, 0, [aux]))
        self.assertEqual([z.name for z in zonas], ["A001", "B002"])

    def test_sem_zona(self):
        self.assertEqual(pz.nearest_zone(1, 1, []), "N/A")

    def test_vista_com_escala_e_angulo(self):
        v = vista("V", x=100, y=50, escala=0.5, angulo=0.0)
        self.assertEqual(v.to_sheet(10, 20), (105.0, 60.0))


class Classificacao(unittest.TestCase):
    def test_frames(self):
        self.assertEqual(pz.classify(texto(1, "12", frame=3), "12"), pz.STATUS_ACCEPTED)
        self.assertEqual(pz.classify(texto(1, "12", frame=53), "12"), pz.STATUS_ACCEPTED)
        self.assertEqual(pz.classify(texto(1, "1234", frame=3), "1234"), pz.STATUS_ACCEPTED)
        self.assertEqual(pz.classify(texto(1, "12345", frame=3), "12345"), pz.STATUS_IGNORE)
        self.assertEqual(pz.classify(texto(1, "12", inner=3), "12"), pz.STATUS_ACCEPTED)
        self.assertEqual(pz.classify(texto(1, "2345", inner=3), "2345"), pz.STATUS_PENDING_GROUP)
        self.assertEqual(pz.classify(texto(1, "12", frame=1, inner=3), "12"), pz.STATUS_PENDING_CONFLICT)
        self.assertEqual(pz.classify(texto(1, "12"), "12"), pz.STATUS_IGNORE)


class Quantidades(unittest.TestCase):
    def qtd(self, a):
        return {o.number: o.qty for o in a.occs}

    def test_balao_sem_nada_vale_um(self):
        self.assertEqual(self.qtd(analisar(vista("V", texto(1, "12", frame=3)))), {"12": 1})

    def test_quantidade_no_proprio_texto(self):
        self.assertEqual(self.qtd(analisar(vista("V", texto(1, "15\n4 PL", frame=3)))), {"15": 4})

    def test_quantidade_ao_lado_vai_para_a_mesma_linha(self):
        a = analisar(vista("V", texto(1, "21", 0, 0, frame=3), texto(2, "22", 0, -30, frame=3), texto(3, "2 PL", 25, 0)))
        self.assertEqual(self.qtd(a), {"21": 2, "22": 1})

    def test_aglomerado_vale_para_todos(self):
        a = analisar(vista("V", texto(1, "31", 0, 0, frame=3), texto(2, "32", 0, -12, frame=3), texto(3, "2 PL", 0, -38)))
        self.assertEqual(self.qtd(a), {"31": 2, "32": 2})

    def test_aglomerado_multiplica_a_individual(self):
        a = analisar(vista("V", texto(1, "34", 0, 0, frame=3), texto(2, "35", 0, -12, frame=3),
                           texto(3, "3 PL", 25, -12), texto(4, "2 PL", 0, -26)))
        self.assertEqual(self.qtd(a), {"34": 2, "35": 6})

    def test_chave_vale_para_todos(self):
        a = analisar(
            vista("V", texto(1, "38", 0, 0, frame=3), texto(2, "39", 0, -14, frame=3), texto(3, "40", 0, -28, frame=3),
                  texto(4, "2 REQD", 20, -14)),
            linhas=[(8, 4, 8, -32)],
        )
        self.assertEqual(self.qtd(a), {"38": 2, "39": 2, "40": 2})
        self.assertEqual(a.c.chaves, 1)

    def test_chave_com_um_callout_so_nao_vale(self):
        a = analisar(vista("V", texto(1, "43", 0, 0, frame=3), texto(2, "4 REQD", 20, 0)), linhas=[(8, 4, 8, -4)])
        self.assertEqual(a.c.chaves, 0)
        self.assertEqual(self.qtd(a), {"43": 4})

    def test_ref_descarta_a_quantidade(self):
        a = analisar(vista("V", texto(1, "61", 0, 0, sub=True), texto(2, "REF", 15, 0)))
        self.assertTrue(a.occs[0].is_reference)
        self.assertEqual(a.c.referencias, 1)
        self.assertEqual(pz.consolidate(a.occs), [])

    def test_consolida_a_mesma_posicao(self):
        v1 = vista("A", texto(1, "12", 0, 0, frame=3))
        v2 = vista("B", texto(1, "012", 0, 0, frame=3), texto(2, "5 PL", 25, 0))
        c = pz.consolidate(analisar(v1, v2).occs)
        self.assertEqual(len(c), 1)
        self.assertEqual((c[0].number, c[0].qty, c[0].view), ("12", 6, "A; B"))

    def test_fundo_e_zona_nao_tem_callout(self):
        a = analisar(vista("Background View", texto(1, "12", frame=3), fundo=True), vista("ZONE", texto(1, "13", frame=3)))
        self.assertEqual(a.occs, [])


class Planilha(unittest.TestCase):
    def test_nome_do_arquivo(self):
        self.assertEqual(pz.clean_file_name(' a:b*c '), "a_b_c")
        self.assertEqual(pz.clean_file_name("  "), "Drawing")

    def test_caminho_livre(self):
        with tempfile.TemporaryDirectory() as d:
            pasta = d + "\\"
            self.assertEqual(pz.output_path(pasta, "PN", "X"), pasta + "PN_Callouts_X.xlsm")
            open(pasta + "PN_Callouts_X.xlsm", "w").close()
            self.assertEqual(pz.output_path(pasta, "PN", "X"), pasta + "PN_Callouts_X_001.xlsm")


class Template(unittest.TestCase):
    def test_formato(self):
        for s, esperado in ((" a1 ", "A1"), ("A0\r\n", "A0"), ("\tE3", "E3"), ("3a0\xa0", "3A0")):
            self.assertEqual(at.normalize_format(s), esperado)
            self.assertTrue(at.is_valid_format(s))
        for s in ("A4", "E0", "SIZE A1", ""):
            self.assertFalse(at.is_valid_format(s), s)

    def test_acha_o_template(self):
        with tempfile.TemporaryDirectory() as d:
            for nome in ("E1_DRAWING TEMPLATE_SHEET A1_CATIAV5R32_REV.CATDrawing", "e1_drawing template_sheet a2_catiav5r32.catdrawing",
                         "E1_DRAWING TEMPLATE_SHEET A3_CATIAV5R20.CATDrawing", "E1_DRAWING TEMPLATE_SHEET A0_CATIAV5R32.pdf"):
                open(os.path.join(d, nome), "w").close()
            self.assertTrue(at.find_template(d, "A1").endswith("A1_CATIAV5R32_REV.CATDrawing"))
            self.assertTrue(at.find_template(d, "a2").endswith("a2_catiav5r32.catdrawing"))
            self.assertEqual(at.find_template(d, "A3"), "")
            self.assertEqual(at.find_template(d, "A0"), "")

    def test_vinculos_da_direita_para_a_esquerda(self):
        marcas = {"#E1P1#": "Drawing_No", "#E1P2#": "Revision"}
        v = at.build_link("#E1P1# REV #E1P2#", marcas, 1.0, 2.0, "T")
        self.assertEqual(v.template_text, "| REV |")
        self.assertEqual(v.parametros, ["Drawing_No", "Revision"])

    def test_reserva_nao_aparece_no_texto(self):
        v = at.build_link("A|B #E1P1#", {"#E1P1#": "X"}, 0, 0, "T")
        self.assertEqual(v.reserva, "~")
        self.assertEqual(v.template_text, "A|B ~")

    def test_sem_marcador_nao_e_vinculo(self):
        self.assertIsNone(at.build_link("TEXTO", {"#E1P1#": "X"}, 0, 0, "T"))

    def test_erro_avisa_quando_o_desenho_pode_estar_parcial(self):
        self.assertIn("SEM SALVAR", at.TemplateError("x", 1, modified=True).mensagem)
        self.assertNotIn("SEM SALVAR", at.TemplateError("x", 1, modified=False).mensagem)


class Splits(unittest.TestCase):
    def test_val_como_o_vba(self):
        for s, v in (("3 partes", 3.0), ("2.5", 2.5), ("abc", 0.0), ("", 0.0), ("  4", 4.0), ("1 2", 12.0), ("-2", -2.0)):
            self.assertEqual(sp.val(s), v, s)

    def test_arredonda_como_clng(self):
        self.assertEqual(sp.number_of_parts("2.5"), 2)
        self.assertEqual(sp.number_of_parts("3.5"), 4)

    def test_faixas_dao_o_que_sobra_as_primeiras(self):
        self.assertEqual(sp.split_ranges(5, 2), [(1, 3), (4, 5)])
        self.assertEqual(sp.split_ranges(5, 3), [(1, 2), (3, 4), (5, 5)])
        self.assertEqual(sp.split_ranges(5, 5), [(i, i) for i in range(1, 6)])

    def test_nome_do_arquivo(self):
        self.assertEqual(sp.clean_file_name('Folha: 2?'), "Folha_ 2_")


if __name__ == "__main__":
    unittest.main()
