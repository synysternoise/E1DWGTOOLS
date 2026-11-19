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
    def folha(self, numero_letras=4, primeira=1):
        textos = []
        i = 0
        for k, letra in enumerate("ABCDEF"[:numero_letras]):
            i += 1
            textos.append(texto(i, letra, 8, 700 - 100 * k))
        for c in range(1, 5):
            i += 1
            textos.append(texto(i, str(primeira - 1 + c), 200 * c, 8))
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

    def test_margem_que_ja_traz_a_dezena_da_folha(self):
        # Desenho real: a folha 3 vem com 31 a 39 na margem. Nao soma a dezena de novo.
        zonas = pz.zones_from_border(self.folha(primeira=31), 3)
        self.assertEqual(pz.nearest_zone(800, 500, zonas), "C034")
        self.assertEqual(pz.nearest_zone(200, 700, pz.zones_from_border(self.folha(primeira=21), 2)), "A021")
        # Na folha 1 vale sempre o que esta escrito.
        self.assertEqual(pz.nearest_zone(200, 700, pz.zones_from_border(self.folha(primeira=11), 1)), "A011")

    def test_poucos_marcadores_nao_formam_zona(self):
        self.assertEqual(pz.zones_from_border(self.folha(1), 1), [])

    def a1(self, extras=(), escala=1.0, lados="ambos"):
        """Margem do A1 como no template: 6 colunas da direita para a esquerda e 4 linhas, nos dois lados."""
        textos = []

        def poe(s, x, y):
            textos.append(texto(len(textos) + 1, s, x / escala, y / escala))

        for k in range(1, 7):
            poe(str(k), 841 - 140 * k + 70, 5)
            if lados == "ambos":
                poe(str(k), 841 - 140 * k + 70, 589)
        for i, letra in enumerate("ABCD"):
            poe(letra, 5, 74 + 148.5 * i)
            if lados == "ambos":
                poe(letra, 836, 74 + 148.5 * i)
        for s, x, y in extras:
            poe(s, x, y)
        fundo = vista("Background View", *textos, fundo=True, indice=2, escala=escala)
        return pz.SheetRead("Sheet.1", False, 841.0, 594.0, [fundo])

    def test_margem_dos_dois_lados(self):
        zonas, fonte = pz.border_zones(self.a1(), 1)
        self.assertEqual((len(zonas), fonte), (24, pz.FONTE_MARGEM))
        self.assertEqual(pz.nearest_zone(324, 310, zonas), "C004")
        self.assertEqual(pz.nearest_zone(628, 283, zonas), "B002")

    def test_numero_da_legenda_nao_quebra_as_colunas(self):
        # Um numero solto da legenda, entre as colunas 2 e 1 da margem de baixo.
        zonas, fonte = pz.border_zones(self.a1(extras=[("7", 700, 30)]), 1)
        self.assertEqual((len(zonas), fonte), (24, pz.FONTE_MARGEM))
        self.assertEqual(pz.nearest_zone(771, 74, zonas), "A001")
        # Mesmo com a margem de um lado so, vale a de cima, que veio inteira.
        so_baixo = self.a1(extras=[("7", 700, 30)] + [(str(k), 841 - 140 * k + 70, 589) for k in range(1, 7)], lados="um")
        zonas, fonte = pz.border_zones(so_baixo, 1)
        self.assertEqual((len(zonas), fonte), (24, pz.FONTE_MARGEM_UM_LADO))
        self.assertEqual(pz.nearest_zone(771, 74, zonas), "A001")

    def test_escala_da_background_view_nao_desloca_a_margem(self):
        # O CATIA devolve 0,75 na escala da Background View, mas o texto esta em mm de papel.
        folha = self.a1()
        folha.views[0].scale = 0.75
        zonas, fonte = pz.border_zones(folha, 1)
        self.assertEqual(fonte, pz.FONTE_MARGEM_CRUA)
        self.assertEqual(pz.nearest_zone(324, 310, zonas), "C004")
        self.assertEqual(pz.nearest_zone(628, 283, zonas), "B002")
        # Quando a escala vale de verdade, a margem fecha nos dois lados ja na primeira leitura.
        self.assertEqual(pz.border_zones(self.a1(escala=0.5), 1)[1], pz.FONTE_MARGEM)

    def test_numero_coberto_pela_legenda_nao_perde_a_coluna(self):
        # A legenda cobre o "1" de baixo: a coluna 1 continua na grade, pelo "1" de cima.
        folha = self.a1()
        fundo = folha.views[0]
        fundo.texts = [t for t in fundo.texts if not (t.text == "1" and t.y < 100)]
        zonas, fonte = pz.border_zones(folha, 1)
        self.assertEqual((len(zonas), fonte), (24, pz.FONTE_MARGEM))
        self.assertEqual(pz.nearest_zone(771, 74, zonas), "A001")

    def test_numero_da_legenda_nao_toma_o_lugar_da_coluna_coberta(self):
        # O "1" de baixo esta coberto e a legenda tem outro "1" fora do lugar da coluna.
        folha = self.a1(extras=[("1", 740, 40)])
        fundo = folha.views[0]
        fundo.texts = [t for t in fundo.texts if not (t.text == "1" and t.y < 30)]
        zonas = pz.border_zones(folha, 1)[0]
        self.assertEqual(pz.nearest_zone(705, 150, zonas), "B001")
        self.assertEqual(pz.nearest_zone(695, 150, zonas), "B002")

    def test_tamanho_do_papel_errado_nao_muda_a_grade(self):
        # Papel lido com a orientacao trocada, ou sem o tamanho: a margem acha a grade do mesmo jeito.
        for largura, altura in ((594.0, 841.0), (0.0, 0.0)):
            folha = self.a1()
            folha.width, folha.height = largura, altura
            zonas, fonte = pz.border_zones(folha, 1)
            self.assertEqual((len(zonas), fonte), (24, pz.FONTE_MARGEM), (largura, altura))
            self.assertEqual(pz.nearest_zone(324, 310, zonas), "C004")

    def test_rotulo_da_legenda_nao_vira_linha(self):
        # Revisao "A" e numeros soltos na legenda, so de um lado.
        folha = self.a1(extras=[("A", 700, 20), ("B", 720, 20), ("1", 760, 40), ("2", 790, 40)])
        zonas, fonte = pz.border_zones(folha, 1)
        self.assertEqual((len(zonas), fonte), (24, pz.FONTE_MARGEM))
        self.assertEqual(pz.nearest_zone(771, 74, zonas), "A001")

    def test_texto_sem_posicao_fica_sem_zona_e_avisa(self):
        folha = self.a1()
        b = texto(1, "7", 324, 310, frame=3)
        b.pos_ok = False
        folha.views.append(vista("Front view", b, indice=3))
        a = pz.Analyzer(lambda i, v: [])
        a.process_sheet(1, folha)
        self.assertEqual([(o.number, o.zone) for o in a.occs], [("7", "N/A")])
        report = pz._relatorio("PN", "", "", a)
        self.assertIn("Sheet.1 › Front view › 7", pz.aviso_mapeamento(report))

    def test_folha_sem_grade_e_folha_repetida_avisam(self):
        a = pz.Analyzer(lambda i, v: [])
        for _ in range(2):
            a.process_sheet(1, pz.SheetRead("Sheet.1", False, 841.0, 594.0, [vista("Front view", texto(1, "7", 10, 10, frame=3))]))
        aviso = pz.aviso_mapeamento(pz._relatorio("PN", "", "", a))
        self.assertIn("Não achei a grade de zonas", aviso)
        self.assertIn("mesmo nome: Sheet.1", aviso)
        self.assertEqual(pz.aviso_mapeamento(pz._relatorio("PN", "", "", pz.Analyzer(lambda i, v: []))), "")

    def test_grade_desenhada_de_todos_os_formatos(self):
        for nome in ("ZONE A0", "ZONE A0[3]", "ZONES_A0_SHT1", "ZONES_A2_SHT13", "ZONES_3A0_SHT2", "ZONE_E3_SHT1", "ZONES_A3_SHT1[2]"):
            self.assertTrue(pz.is_aux_view(nome), nome)
        for nome in ("ZONEX", "ZONE DETAIL", "VIEW ZONE", "ZONES"[:4] + " B"):
            self.assertFalse(pz.is_aux_view(nome), nome)

    def test_conferencia_com_a_grade_desenhada(self):
        folha = self.a1()
        folha.views.append(vista("ZONES_A1_SHT1", texto(1, "C004", 351, 371, fonte=20), texto(2, "B002", 500, 222, fonte=20)))
        lidos, diferentes = pz.drawn_grid_mismatches(folha, pz.border_zones(folha, 1)[0])
        self.assertEqual((lidos, diferentes), (2, ["B002 caiu em B003"]))

    def test_vista_sem_posicao_nao_para_a_leitura(self):
        registros = [
            ["F", "Sheet.1", "0", "841", "594"],
            ["V", "3", "Front view", "0", "0", "0", "1", "0", "0"],
            ["T", "3", "1", "12", "324", "310", "3,5", "5", "1", "3", "0", "1", "0", "Text.1"],
            ["V", "4", "Top view", "0", "0", "0", "1", "0"],
        ]
        folha = pz.parse_sheet(registros)
        self.assertEqual([v.pos_ok for v in folha.views], [False, True])
        folha.views.insert(0, self.a1().views[0])
        a = pz.Analyzer(lambda i, v: [])
        a.process_sheet(1, folha)
        self.assertEqual([(o.number, o.zone) for o in a.occs], [("12", "N/A")])
        self.assertEqual(a.sem_posicao, [("Sheet.1", "Front view")])
        report = pz._relatorio("PN", "", "", a)
        self.assertIn("Sheet.1 › Front view", pz.aviso_sem_posicao(report))
        self.assertIn("POSIÇÃO NÃO INFORMADA", pz.texto_conferencia(report))

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

    def test_acha_o_template_pelo_nome_novo(self):
        with tempfile.TemporaryDirectory() as d:
            for nome in ("2E.CATDrawing", "E1_DRW_TEMPLATE_3A0_R00.CATDrawing", "E1_DRW_TEMPLATE_A0_R00.CATDrawing",
                         "E1_DRW_TEMPLATE_A1_R00.CATDrawing", "E1_DRW_TEMPLATE_E3_R00.CATDrawing", "ECN.CATDrawing",
                         "E1_DRAWING TEMPLATE_SHEET A1_CATIAV5R32_REV01.CATDrawing",
                         "E1_DRAWING TEMPLATE_SHEET A2_CATIAV5R32_REV01.CATDrawing"):
                open(os.path.join(d, nome), "w").close()
            self.assertTrue(at.find_template(d, "A0").endswith("E1_DRW_TEMPLATE_A0_R00.CATDrawing"))
            self.assertTrue(at.find_template(d, "3A0").endswith("E1_DRW_TEMPLATE_3A0_R00.CATDrawing"))
            self.assertTrue(at.find_template(d, "e3").endswith("E1_DRW_TEMPLATE_E3_R00.CATDrawing"))
            # Com os dois nomes na pasta, vale o novo. So com o antigo, vale o antigo.
            self.assertTrue(at.find_template(d, "A1").endswith("E1_DRW_TEMPLATE_A1_R00.CATDrawing"))
            self.assertTrue(at.find_template(d, "A2").endswith("A2_CATIAV5R32_REV01.CATDrawing"))
            self.assertEqual(at.find_template(d, "A3"), "")

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
