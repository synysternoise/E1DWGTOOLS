"""Regras do Check de Template que nao dependem do CATIA.

Uso:  python -m unittest discover -s tests
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from engine import template_check as tc  # noqa: E402
from engine.template_check import CERTO, CONFERIR, ERRADO, TextoLido, VistaLida  # noqa: E402


def legenda(*valores):
    """Como na foto da legenda real: rotulo em cima, valor na mesma celula, numero da zona mais abaixo."""
    return [
        TextoLido("DRAWING NUMBER", 900.0, 60.0), TextoLido("171-54397-801", 900.0, 50.0),
        TextoLido("SCALE", 830.0, 60.0), TextoLido("SHEET / OF", 980.0, 60.0),
        TextoLido("REV", 780.0, 35.0), TextoLido("1", 880.0, 8.0), TextoLido("A0", 985.0, 8.0),
        *valores,
    ]


class TestNumeracao(unittest.TestCase):
    def test_primeira_folha_tem_o_total(self):
        self.assertEqual(tc.numeracao_esperada(1, 7), "1/7")
        self.assertEqual(tc.conferir_numeracao("1 / 7", 1, 7)[0], CERTO)
        self.assertEqual(tc.conferir_numeracao("1/7", 1, 7)[0], CERTO)

    def test_primeira_folha_com_total_errado(self):
        self.assertEqual(tc.conferir_numeracao("1 / 6", 1, 7)[0], ERRADO)
        self.assertEqual(tc.conferir_numeracao("1", 1, 7)[0], ERRADO)

    def test_outras_folhas_so_com_o_numero(self):
        self.assertEqual(tc.numeracao_esperada(2, 7), "2")
        self.assertEqual(tc.conferir_numeracao("2", 2, 7)[0], CERTO)
        self.assertEqual(tc.conferir_numeracao("2 / 7", 2, 7)[0], ERRADO)
        self.assertEqual(tc.conferir_numeracao("3", 2, 7)[0], ERRADO)

    def test_campo_vazio_e_erro_e_campo_nao_achado_nao_e(self):
        self.assertEqual(tc.conferir_numeracao("", 2, 7)[0], ERRADO)
        self.assertEqual(tc.conferir_numeracao(None, 2, 7)[0], CONFERIR)

    def test_folha_unica(self):
        self.assertEqual(tc.conferir_numeracao("1/1", 1, 1)[0], CERTO)


class TestCampoFolha(unittest.TestCase):
    def test_um_texto_so(self):
        self.assertEqual(tc.campo_folha(legenda(TextoLido("1 / 7", 980.0, 50.0))), "1 / 7")

    def test_prefixo_separado_do_total(self):
        self.assertEqual(tc.campo_folha(legenda(TextoLido("7", 988.0, 50.0), TextoLido("1 /", 974.0, 50.0))), "1 / 7")

    def test_nao_pega_o_numero_da_zona_nem_o_desenho(self):
        self.assertEqual(tc.campo_folha(legenda()), "")

    def test_numero_da_main_view_em_cima_do_total_aparece_nos_dois(self):
        lido = tc.campo_folha(legenda(TextoLido("7", 982.0, 50.0), TextoLido("2", 978.0, 50.0)))
        self.assertEqual(lido, "2 7")
        self.assertEqual(tc.conferir_numeracao(lido, 2, 7)[0], ERRADO)

    def test_sem_rotulo(self):
        self.assertIsNone(tc.campo_folha([TextoLido("2", 980.0, 50.0)]))

    def test_rotulo_e_valor_no_mesmo_texto(self):
        self.assertEqual(tc.campo_escala([TextoLido("SCALE 1:4", 830.0, 50.0)]), "1:4")
        self.assertEqual(tc.campo_escala([TextoLido("SCALE\n1:4", 830.0, 50.0)]), "1:4")
        self.assertEqual(tc.campo_folha([TextoLido("SHEET / OF\n1 / 7", 980.0, 50.0)]), "1 / 7")
        self.assertEqual(tc.campo_folha([TextoLido("SHEET 2", 980.0, 50.0)]), "2")


class TestCampoEscala(unittest.TestCase):
    def test_le_o_valor_da_celula(self):
        self.assertEqual(tc.campo_escala(legenda(TextoLido("1:4", 830.0, 50.0))), "1:4")

    def test_prefere_o_que_parece_escala(self):
        self.assertEqual(tc.campo_escala(legenda(TextoLido("X", 830.0, 55.0), TextoLido("1:4", 830.0, 50.0))), "1:4")

    def test_texto_que_nao_e_escala(self):
        self.assertEqual(tc.campo_escala(legenda(TextoLido("NTS", 830.0, 50.0))), "NTS")

    def test_campo_vazio_e_sem_rotulo(self):
        self.assertEqual(tc.campo_escala(legenda()), "")
        self.assertIsNone(tc.campo_escala([TextoLido("1:4", 830.0, 50.0)]))


class TestEscala(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(tc.parse_escala("1:4"), 0.25)
        self.assertEqual(tc.parse_escala(" 2 : 1 "), 2.0)
        self.assertEqual(tc.parse_escala("1:2,5"), 0.4)
        self.assertIsNone(tc.parse_escala("NTS"))
        self.assertIsNone(tc.parse_escala("0:4"))

    def test_formato(self):
        self.assertEqual(tc.formato_escala(0.25), "1:4")
        self.assertEqual(tc.formato_escala(2.0), "2:1")
        self.assertEqual(tc.formato_escala(0.4), "1:2.5")
        self.assertEqual(tc.formato_escala(1 / 3), "1:3")

    def test_vistas_que_nao_contam(self):
        for nome in ("Isometric view", "ISOMETRIC", "ISO", "SECTION A-A", "VIEW ZAC/ZAC", "PLAN VIEW", "ZONE", "ZONE A0[2]", "ZONES_A0_SHT1[2]", "ZONE[1]"):
            self.assertFalse(tc.conta_para_escala(nome), nome)

    def test_vistas_que_contam(self):
        for nome in ("2F7", "1C33", "1A42", "ZONEX", "ISOLATOR", "VIEW LOOKING FWD", "View Looking Aft", "VIEW  LOOKING INBD"):
            self.assertTrue(tc.conta_para_escala(nome), nome)

    def test_view_looking_nao_salva_isometrica_nem_section(self):
        for nome in ("ISOMETRIC VIEW LOOKING FWD", "ISO VIEW LOOKING FWD", "SECTION VIEW LOOKING FWD"):
            self.assertFalse(tc.conta_para_escala(nome), nome)

    def test_folha_so_com_view_looking_e_isometrica(self):
        vistas = [VistaLida("VIEW LOOKING FWD", 0.25), VistaLida("Isometric view", 0.1), VistaLida("ZONE A0", 1.0)]
        self.assertEqual(tc.conferir_escala("1:4", vistas)[0], CERTO)
        self.assertEqual(tc.conferir_escala("1:2", vistas)[:2], (ERRADO, "1:4"))

    def test_bate(self):
        vistas = [VistaLida("2F7", 0.25), VistaLida("Isometric view", 0.1), VistaLida("SECTION A-A", 0.5)]
        self.assertEqual(tc.conferir_escala("1:4", vistas)[0], CERTO)

    def test_um_terco_gravado_arredondado_bate(self):
        self.assertEqual(tc.conferir_escala("1:3", [VistaLida("2F7", 0.3333)])[0], CERTO)

    def test_nao_bate(self):
        self.assertEqual(tc.conferir_escala("1:4", [VistaLida("2F7", 0.5)])[:2], (ERRADO, "1:2"))

    def test_so_section_e_isometrica_diferentes_nao_acusa(self):
        vistas = [VistaLida("1F7", 0.25), VistaLida("SECTION A-A", 0.5), VistaLida("Isometric view", 0.1)]
        self.assertEqual(tc.conferir_escala("1:4", vistas)[0], CERTO)

    def test_parte_das_vistas_bate(self):
        self.assertEqual(tc.conferir_escala("1:4", [VistaLida("2F7", 0.25), VistaLida("1F7", 0.5)])[0], CONFERIR)

    def test_sem_vista_para_comparar(self):
        self.assertEqual(tc.conferir_escala("1:4", [VistaLida("PLAN VIEW", 0.5)])[0], CONFERIR)

    def test_campo_nao_achado_vazio_ou_sem_escala(self):
        vistas = [VistaLida("2F7", 0.25)]
        self.assertEqual(tc.conferir_escala(None, vistas)[0], CONFERIR)
        self.assertEqual(tc.conferir_escala("", vistas)[0], ERRADO)
        self.assertEqual(tc.conferir_escala("NTS", vistas)[0], CONFERIR)


class TestFormato(unittest.TestCase):
    def test_papel_padrao(self):
        self.assertEqual(tc.conferir_formato("A0", 2, 1189, 841)[0], CERTO)
        self.assertEqual(tc.conferir_formato("A1", 2, 1189, 841)[:2], (ERRADO, "A0"))

    def test_papel_personalizado_pela_medida(self):
        self.assertEqual(tc.conferir_formato("A1", 13, 841, 594)[0], CERTO)
        self.assertEqual(tc.conferir_formato("A1", 13, 594, 841)[0], CERTO)
        self.assertEqual(tc.conferir_formato("A0", 13, 841, 594)[:2], (ERRADO, "A1"))

    def test_3a0_e_e3_sem_medida_de_referencia(self):
        self.assertEqual(tc.conferir_formato("3A0", 13, 2523, 1189)[0], CONFERIR)
        self.assertEqual(tc.conferir_formato("E3", 13, 3354, 864)[0], CONFERIR)

    def test_3a0_em_papel_a0(self):
        self.assertEqual(tc.conferir_formato("3A0", 2, 1189, 841)[0], ERRADO)

    def test_etiqueta_nao_achada(self):
        self.assertEqual(tc.conferir_formato("", 2, 1189, 841)[0], CONFERIR)


class _Colecao:
    def __init__(self, itens):
        self.itens = itens
        self.Count = len(itens)

    def Item(self, chave):
        return self.itens[chave - 1]


class _Parametros:
    def __init__(self, valor):
        self.valor = valor

    def Item(self, _nome):
        p = type("P", (), {})()
        p.ValueAsString = lambda: self.valor
        return p


def _texto(texto, x, y, nome="Text.1"):
    t = type("T", (), {})()
    t.Text, t.x, t.y, t.Name = texto, x, y, nome
    return t


def _vista(nome, escala=1.0, textos=(), x=0.0, y=0.0):
    v = type("V", (), {})()
    v.Name, v.Scale, v.Scale2, v.x, v.y = nome, escala, escala, x, y
    v.Texts = _Colecao(list(textos))
    return v


def _folha(nome, numero, vistas=(), principal=(), escala="1:4", formato="A0", papel=2):
    fundo = [
        _texto("SCALE", 830.0, 60.0), _texto(escala, 830.0, 50.0), _texto("SHEET / OF", 980.0, 60.0),
        _texto(formato, 985.0, 8.0),
    ]
    if numero is not None:
        fundo.append(_texto(numero, 980.0, 50.0))
    f = type("F", (), {})()
    f.Name, f.IsDetail, f.PaperSize = nome, False, papel
    f.GetPaperWidth = lambda: 1189.0
    f.GetPaperHeight = lambda: 841.0
    f.Views = _Colecao([_vista("Main View", textos=principal), _vista("Background View", textos=fundo), *vistas])
    return f


def _ponte(folhas, parametro="3", nome="X.CATDrawing"):
    doc = type("D", (), {})()
    doc.Name, doc.FullName, doc.Sheets = nome, "C:\\" + nome, _Colecao(folhas)
    doc.Parameters = _Parametros(parametro)
    app = type("A", (), {})()
    app.Documents, app.ActiveDocument = _Colecao([doc]), doc
    return type("B", (), {"app": app})()


class TestConferirTemplate(unittest.TestCase):
    def _situacoes(self, relatorio):
        return {(i.sheet_name, i.regra): i.situacao for i in relatorio.items}

    def test_desenho_certo(self):
        folhas = [
            _folha("Sheet.1", "1 / 3", [_vista("2F7", 0.25)]),
            _folha("Sheet.2", "2", [_vista("1F7", 0.25)]),
            # Numero da folha na Main View, sem nada no Background.
            _folha("Sheet.3", None, [_vista("1C33", 0.25)], principal=[_texto("3", 980.0, 50.0)]),
        ]
        r = tc.conferir_template(_ponte(folhas))
        self.assertEqual((r.errados, r.conferir), (0, 0), self._situacoes(r))
        self.assertEqual(r.certos, 10)
        self.assertEqual(r.total_folhas, 3)

    def test_numero_na_main_view_com_escala_e_origem(self):
        principal = [_texto("2", (980.0 - 100.0) / 2, (50.0 - 20.0) / 2)]
        folha2 = _folha("Sheet.2", None, [_vista("1F7", 0.25)])
        folha2.Views.itens[0] = _vista("Main View", 2.0, principal, 100.0, 20.0)
        r = tc.conferir_template(_ponte([_folha("Sheet.1", "1/2", [_vista("2F7", 0.25)]), folha2], "2"))
        self.assertEqual(self._situacoes(r)[("Sheet.2", tc.NUMERACAO)], CERTO)

    def test_acusa_cada_erro(self):
        folhas = [
            _folha("Sheet.1", "1 / 5", [_vista("2F7", 0.5)], formato="A1"),
            _folha("Sheet.2", "2 / 3", [_vista("1F7", 0.25)]),
        ]
        s = self._situacoes(tc.conferir_template(_ponte(folhas, "5")))
        self.assertEqual(s[("Sheet.1", tc.TOTAL)], ERRADO)
        self.assertEqual(s[("Sheet.1", tc.NUMERACAO)], ERRADO)
        self.assertEqual(s[("Sheet.1", tc.FORMATO)], ERRADO)
        self.assertEqual(s[("Sheet.1", tc.ESCALA)], ERRADO)
        self.assertEqual(s[("Sheet.2", tc.NUMERACAO)], ERRADO)
        self.assertEqual(s[("Sheet.2", tc.FORMATO)], CERTO)
        self.assertEqual(s[("Sheet.2", tc.ESCALA)], CERTO)

    def test_para_quando_pedem(self):
        folhas = [_folha("Sheet.1", "1/2"), _folha("Sheet.2", "2")]
        r = tc.conferir_template(_ponte(folhas, "2"), should_stop=lambda: True)
        self.assertTrue(r.stopped)
        self.assertEqual([i.regra for i in r.items], [tc.TOTAL])

    def test_documento_que_nao_e_desenho(self):
        with self.assertRaises(tc.CatiaError):
            tc.conferir_template(_ponte([], nome="X.CATPart"))


if __name__ == "__main__":
    unittest.main()
