"""Reconhecimento do documento pelo nome: arquivo salvo no PC e desenho aberto pelo VPM.

Uso:  python -m unittest discover -s tests
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from engine.documento import eh_desenho, pn_do_documento  # noqa: E402

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


if __name__ == "__main__":
    unittest.main()
