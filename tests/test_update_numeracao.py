"""Update Template: numeracao da margem e da grade pela folha, e quais vistas de zona sao apagadas."""
import os
import sys
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from engine import atualizar_template as at  # noqa: E402


class VistasDeZona(unittest.TestCase):
    def test_nomes_reais_do_template(self):
        for nome in ("ZONE", "zone", "ZONE[1]", "ZONE A0", "ZONE A0[3]", "ZONES_A0_SHT1", "ZONES_A0_SHT1[2]",
                     "ZONES_A0_SHT2", "ZONES_A1_SHT2", "ZONE 3A0", "ZONES_E3_SHT", "ZONE_E3_SHT1", "ZONE_E3_SHT1[2]"):
            self.assertTrue(at.is_aux_view(nome), nome)

    def test_vista_do_usuario_nao_e_apagada(self):
        for nome in ("MY ZONE VIEW", "ZONE DETAIL", "ZONEX", "ZONE A9", "ZONES_A0", "ZONES_A0_SHTX", "ZONE_E3", "ZONE_SHT1", "PLAN VIEW", "1F7"):
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


class ReservaDaFolha(unittest.TestCase):
    LEGENDA = [("SCALE", 975.0, 55.0, "Text.1"), ("XX", 975.0, 45.0, "Text.2"), ("DRAWING NUMBER", 1040.0, 55.0, "Text.3"),
               ("XXX", 1040.0, 45.0, "Text.4"), ("SHEET / OF", 1112.0, 55.0, "Text.5"), ("XX", 1114.0, 45.0, "Text.6"),
               ("A0", 1175.0, 8.0, "Text.68")]

    def test_vale_o_xx_embaixo_do_rotulo(self):
        self.assertEqual(at.escolher_reserva_folha(self.LEGENDA, 1189.0)[3], "Text.6")

    def test_outras_formas_da_reserva(self):
        for valor in ("XX", "X", "XXX", "X / XX", "1/XX", "1 / XXX", "xx"):
            textos = [("SHEET: OF", 100.0, 30.0, "a"), (valor, 100.0, 20.0, "b")]
            self.assertEqual(at.escolher_reserva_folha(textos, 1189.0)[3], "b", valor)

    def test_o_que_nao_e_reserva(self):
        for valor in ("3", "1/3", "XXXX", "XX-01", "A0", "REV", ""):
            textos = [("SHEET/OF", 100.0, 30.0, "a"), (valor, 100.0, 20.0, "b")]
            self.assertIsNone(at.escolher_reserva_folha(textos, 1189.0), valor)

    def test_com_rotulo_o_xx_de_outra_celula_nao_vale(self):
        textos = [("SHEET/OF", 1112.0, 55.0, "a"), ("XX", 975.0, 45.0, "b"), ("XX", 1112.0, 20.0, "c")]
        self.assertIsNone(at.escolher_reserva_folha(textos, 1189.0))

    def test_valor_na_mesma_linha_do_rotulo(self):
        # Template com "SHEET / OF   1/XX" numa linha so: antes ficava "1/XX" em todas as folhas.
        textos = [("SHEET / OF", 790.0, 34.0, "a"), ("1/XX", 808.0, 34.0, "b"), ("XXX", 740.0, 34.0, "c")]
        self.assertEqual(at.escolher_reserva_folha(textos, 841.0)[3], "b")
        longe = [("SHEET / OF", 790.0, 34.0, "a"), ("XX", 860.0, 34.0, "b")]
        self.assertIsNone(at.escolher_reserva_folha(longe, 1189.0))

    def test_sem_rotulo_vale_o_mais_a_direita_no_canto(self):
        textos = [("XX", 975.0, 45.0, "a"), ("XX", 1114.0, 45.0, "b"), ("XX", 1150.0, 400.0, "c"), ("XX", 300.0, 45.0, "d")]
        self.assertEqual(at.escolher_reserva_folha(textos, 1189.0)[3], "b")
        self.assertIsNone(at.escolher_reserva_folha([("XX", 300.0, 45.0, "d")], 1189.0))


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


class _Props:
    def __init__(self, **kw):
        self.Bold, self.Italic, self.Underline, self.Justification, self.FrameType = 0, 0, 0, 1, 0
        self.__dict__.update(kw)
        self.atualizado = False

    def Update(self):  # noqa: N802 - nome do COM
        self.atualizado = True


class _Texto:
    def __init__(self, vista, texto, x, y, nome="", **formato):
        self.vista, self.Text, self.x, self.y, self.Name = vista, texto, x, y, nome
        self.AnchorPosition, self.Angle, self.WrappingWidth = formato.get("ancora", 1), formato.get("angulo", 0.0), 0.0
        self.fonte, self.tamanho = formato.get("fonte", "Arial"), formato.get("tamanho", 3.5)
        self.TextProperties = _Props(**formato.get("props", {}))
        self.vinculo_template = formato.get("vinculo_template", False)
        self.variaveis = []
        self.NbLink = 1 if self.vinculo_template else 0

    def GetFontName(self, *_):  # noqa: N802
        return self.fonte

    def GetFontSize(self, *_):  # noqa: N802
        return self.tamanho

    def SetFontName(self, _a, _b, valor):  # noqa: N802
        self.fonte = valor

    def SetFontSize(self, _a, _b, valor):  # noqa: N802
        self.tamanho = valor

    def InsertVariable(self, pos, n, parametro):  # noqa: N802
        self.variaveis.append((pos, n, parametro))


class _Textos:
    def __init__(self, vista):
        self.vista, self.itens = vista, []

    @property
    def Count(self):  # noqa: N802
        return len(self.itens)

    def Item(self, i):  # noqa: N802
        return self.itens[i - 1]

    def Add(self, texto, x, y):  # noqa: N802
        t = _Texto(self.vista, texto, x, y)
        self.itens.append(t)
        return t


class _Vista:
    def __init__(self):
        self.Texts = _Textos(self)


class _Sel:
    def __init__(self):
        self.itens = []
        self.VisProperties = self

    def Clear(self):  # noqa: N802
        self.itens = []

    def Add(self, o):  # noqa: N802
        self.itens.append(o)

    def Delete(self):  # noqa: N802
        for o in self.itens:
            o.vista.Texts.itens.remove(o)
        self.itens = []

    def GetRealColor(self, *_):  # noqa: N802
        return (0, 0, 0, 0)

    def SetRealColor(self, *_):  # noqa: N802
        pass


class TextoSemVinculoDoTemplate(unittest.TestCase):
    """Colado do template, o texto fica ligado aos parametros dele (Edit > Links). Tem de ser recriado."""

    def colado(self, texto="XX", nome="Text.219"):
        v = _Vista()
        t = _Texto(v, texto, 1114.0, 45.0, nome, ancora=5, angulo=0.0, fonte="Arial", tamanho=5.0,
                   props={"Bold": 1}, vinculo_template=True)
        v.Texts.itens.append(t)
        return v, t

    def test_recriado_igual_e_sem_vinculo(self):
        v, velho = self.colado()
        novo = at.recriar_texto(_Sel(), v, velho, "2")
        self.assertEqual(v.Texts.itens, [novo])  # o colado, com o vinculo do template, saiu
        self.assertFalse(novo.vinculo_template)
        self.assertEqual((novo.Text, novo.x, novo.y, novo.Name), ("2", 1114.0, 45.0, "Text.219"))
        self.assertEqual((novo.AnchorPosition, novo.fonte, novo.tamanho, novo.TextProperties.Bold), (5, "Arial", 5.0, 1))
        self.assertTrue(novo.TextProperties.atualizado)

    def test_vinculo_refeito_com_o_parametro_do_desenho(self):
        v, velho = self.colado("XXX", "Text.159")
        conv = at._Conversao.__new__(at._Conversao)
        conv.report = SimpleNamespace(warnings=[])
        conv._registro = []
        parametro = object()
        conv._parametro = lambda _cache, _nome: parametro
        link = at.TextLink("XXX", "XXX", ["Drawing_No"], 1114.0, 45.0, "Text.159")
        conv._refazer_vinculos(_Sel(), at._IndiceTextos(v), {"Text.159": link}, "", {}, "Sheet.1")
        [novo] = v.Texts.itens
        self.assertIsNot(novo, velho)
        self.assertEqual(novo.variaveis, [(1, 1, parametro)])
        self.assertEqual(conv.report.warnings, [])





class TextoColado(unittest.TestCase):
    """Colado, o texto ganha outro nome e a posicao pode mudar na ultima casa (A0 real, 19/11/2026)."""

    def vista(self, *textos):
        v = _Vista()
        for valor, x, y, nome in textos:
            v.Texts.itens.append(_Texto(v, valor, x, y, nome))
        return v

    def test_acha_com_outro_nome_e_posicao_do_outro_lado_do_arredondamento(self):
        v = self.vista(("1/", 817.2758, 27.6222, "Text.149"), ("XX", 820.4551, 27.6222, "Text.150"))
        achado = at._IndiceTextos(v).localizar("Text.78", 820.4549, 27.6222)
        self.assertEqual(achado.Name, "Text.150")

    def test_a0_real_1_barra_e_xx_no_mesmo_ponto(self):
        # Template A0: Text.6 "1/" e Text.83 "XX" (No_of_Sheets) em (1168.32, 28.25). Colados com outro nome.
        v = self.vista(("1/", 1168.32, 28.25, "Text.149"), ("XX", 1168.32, 28.25, "Text.150"))
        achado = at._IndiceTextos(v).localizar("Text.83", 1168.32, 28.25, "XX")
        self.assertEqual(achado.Name, "Text.150")
        link = at.TextLink("|", "|", ["No_of_Sheets"], 1168.32, 28.25, "Text.83", "XX")
        self.assertEqual(at.sheet_field_prefixes(v, link), [(1168.32, 28.25)])

    def test_dois_textos_no_mesmo_lugar_vale_o_que_nao_esta_vazio(self):
        v = self.vista(("", 820.45, 27.62, "Text.151"), ("XX", 820.45, 27.62, "Text.150"))
        self.assertEqual(at._IndiceTextos(v).localizar("Text.78", 820.45, 27.62).Name, "Text.150")

    def test_copia_identica_no_mesmo_lugar_sai_junto(self):
        # A0 real: o campo era recriado, mas um "XX" igual no mesmo lugar ficava ligado ao template.
        v = self.vista(("XX", 820.45, 27.62, "Text.78"), ("XX", 820.45, 27.62, "Text.150"), ("1/", 817.28, 27.62, "Text.75"))
        conv = at._Conversao.__new__(at._Conversao)
        conv.report = SimpleNamespace(warnings=[])
        conv._registro = []
        conv._parametro = lambda _cache, _nome: object()
        link = at.TextLink("|", "|", ["No_of_Sheets"], 820.45, 27.62, "Text.78")
        conv._refazer_vinculos(_Sel(), at._IndiceTextos(v), {"Text.78": link}, "", {}, "Sheet.1")
        self.assertEqual(sorted(t.Text for t in v.Texts.itens), ["1/", "|"])
        self.assertIn("copias apagadas: 1", conv._registro[0])

    def test_longe_demais_nao_acha_e_avisa(self):
        v = self.vista(("XX", 821.0, 27.62, "Text.150"))
        self.assertIsNone(at._IndiceTextos(v).localizar("Text.78", 820.45, 27.62))
        conv = at._Conversao.__new__(at._Conversao)
        conv.report = SimpleNamespace(warnings=[])
        conv._registro = []
        link = at.TextLink("|", "|", ["No_of_Sheets"], 820.45, 27.62, "Text.78")
        conv._refazer_vinculos(_Sel(), at._IndiceTextos(v), {"Text.78": link}, "", {}, "Sheet.1")
        self.assertIn("No_of_Sheets não foi achado", conv.report.warnings[0])


class LigacaoComOTemplate(unittest.TestCase):
    """Depois de fechado, o template so continua carregado se algo do desenho aponta para ele."""

    def conversao(self, carregados, itens=(0, 0)):
        conv = at._Conversao.__new__(at._Conversao)
        conv.report = SimpleNamespace(warnings=[])
        docs = [SimpleNamespace(FullName=n) for n in carregados]
        conv.app = SimpleNamespace(Documents=SimpleNamespace(Count=len(docs), Item=lambda i: docs[i - 1]))
        conv._itens_do_template = itens
        return conv

    def test_template_descarregado_nao_avisa(self):
        conv = self.conversao([r"C:\d\171-52382-001.CATDrawing"])
        conv._registro = []
        conv.conferir_ligacao(r"\\rede\E1_DRW_TEMPLATE_A1_R00.CATDrawing")
        self.assertEqual(conv.report.warnings, [])

    def test_template_ainda_carregado_vai_so_para_o_registro(self):
        # No PC da empresa o template ficou carregado com o desenho sem links: nao e aviso na tela.
        tpl = r"\\rede\E1_DRW_TEMPLATE_A1_R00.CATDrawing"
        conv = self.conversao([r"C:\d\171-52382-001.CATDrawing", tpl.upper()], itens=(2, 1))
        conv._registro = []
        conv.conferir_ligacao(tpl)
        self.assertEqual(conv.report.warnings, [])
        self.assertIn("dittos: 2, tabelas: 1", conv._registro[0])


class MarcadorDoParametro(unittest.TestCase):
    class Parametro:
        """Como o CATIA V5R20: com unidade, o numero sozinho e lido em metros (734006 vira 7,34e+008mm)."""

        def __init__(self, unidade=None, texto=False):
            self.unidade, self.texto, self.valor = unidade, texto, "0"

        def ValuateFromString(self, s):
            u = (self.unidade or "").strip()
            if self.texto:
                self.valor = s
            elif s.isdigit():
                self.valor = s if not u else "7,34e+008"
            elif u and s.endswith(u) and s[:-len(u)].strip().isdigit():
                self.valor = s[:-len(u)].strip()
            else:
                raise at.COM_ERROR(-1, "valor recusado", None, None)

        def ValueAsString(self):
            return self.valor + (self.unidade or "") if not self.texto else self.valor

    def test_texto_inteiro_e_com_unidade(self):
        self.assertEqual(at._marcar(self.Parametro(texto=True), 3), "#E1P3#")
        self.assertEqual(at._marcar(self.Parametro(), 3), "734003")
        self.assertEqual(at._marcar(self.Parametro("mm"), 6), "734006mm")
        self.assertEqual(at._marcar(self.Parametro(" deg"), 6), "734006 deg")

    def test_marcador_com_unidade_acha_o_texto(self):
        link = at.build_link("ESP 734006mm", {"734006mm": "Thickness"}, 650.0, 50.0, "Text.9")
        self.assertEqual((link.template_text, link.parametros), ("ESP |", ["Thickness"]))
