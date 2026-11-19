"""Reconhecimento do documento pelo nome: arquivo salvo no PC e desenho aberto pelo VPM.

Uso:  python -m unittest discover -s tests
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from engine.documento import eh_desenho, pn_do_documento, tipo_documento  # noqa: E402

VPM = "171-60466-803      1       1  --- CATDRAWING     1 ---"


class Documento(unittest.TestCase):
    def test_arquivo_salvo(self):
        self.assertTrue(eh_desenho("171-60895-401.CATDrawing"))
        self.assertEqual(pn_do_documento("171-60895-401.CATDrawing"), "171-60895-401")

    def test_aberto_pelo_vpm(self):
        self.assertTrue(eh_desenho(VPM))
        self.assertEqual(pn_do_documento(VPM), "171-60466-803")
        for nome in ("171-60466-803 1 1 --- CATDRAWING 1 ---", "171-60466-803\t1\t1\t--- CATDRAWING\t1 ---"):
            self.assertTrue(eh_desenho(nome), nome)
            self.assertEqual(pn_do_documento(nome), "171-60466-803")

    def test_arquivo_somente_leitura(self):
        self.assertTrue(eh_desenho("171-50964-401.CATDrawing (ReadOnly)"))

    def test_outros_documentos(self):
        for nome in ("", "Peca.CATPart", "Conjunto.CATProduct", "171-60466-803      1       1  --- CATPART     1 ---"):
            self.assertFalse(eh_desenho(nome), nome)

    def test_pn_sem_extensao_fica_como_esta(self):
        self.assertEqual(pn_do_documento("Drawing1"), "Drawing1")


class _Info:
    def __init__(self, tipo):
        self.tipo = tipo

    def GetDocumentation(self, _):  # noqa: N802 - nome do COM
        return (self.tipo, "", 0, "")


class _Ole:
    def __init__(self, tipo):
        self.tipo = tipo

    def GetTypeInfo(self):  # noqa: N802 - nome do COM
        return _Info(self.tipo)


class _Doc:
    """Documento do CATIA de mentira: o tipo vem do COM e o nome pode ser qualquer um."""

    def __init__(self, tipo, nome):
        self._oleobj_ = _Ole(tipo)
        self.Name = nome


class PeloTipo(unittest.TestCase):
    def test_desenho_com_qualquer_nome(self):
        for nome in (VPM, "171-60466-803 SPD A", "Drawing1", "", "171-60466-803.CATPart"):
            self.assertTrue(eh_desenho(_Doc("DrawingDocument", nome)), nome)

    def test_peca_com_nome_de_desenho_nao_e_desenho(self):
        self.assertFalse(eh_desenho(_Doc("PartDocument", "171-60466-803.CATDrawing")))

    def test_sem_tipo_vale_o_que_o_documento_tem(self):
        class SoFolhas:
            Name = "qualquer"
            Sheets = object()
        self.assertEqual(tipo_documento(SoFolhas()), "DrawingDocument")
        self.assertTrue(eh_desenho(SoFolhas()))

    def test_pn_de_nome_desconhecido_e_o_primeiro_bloco(self):
        self.assertEqual(pn_do_documento("171-60466-803   A   SPD"), "171-60466-803")
        self.assertEqual(pn_do_documento("171-60466-803.CATDrawing (ReadOnly)"), "171-60466-803")


if __name__ == "__main__":
    unittest.main()
