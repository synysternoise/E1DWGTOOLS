"""Garante que a lista do verificar.py acompanha o codigo. Se falhar, rode: python verificar.py --manifesto"""
import os
import sys
import unittest

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, RAIZ)

import verificar  # noqa: E402


class TestManifesto(unittest.TestCase):
    def test_lista_igual_aos_arquivos(self):
        self.assertEqual(len(verificar.MANIFESTO), 25)
        for relativo, esperado in verificar.MANIFESTO.items():
            with open(os.path.join(RAIZ, *relativo.split("/")), "rb") as f:
                self.assertEqual(verificar.assinatura(f.read()), esperado, relativo)

    def test_assinatura_ignora_o_que_o_editor_muda(self):
        base = verificar.assinatura(b"a = 1\n    b = 2\n")
        self.assertEqual(verificar.assinatura(b"a = 1\r\n    b = 2\r\n"), base)
        self.assertEqual(verificar.assinatura(b"\xef\xbb\xbfa = 1  \n    b = 2"), base)
        self.assertEqual(verificar.assinatura(b"a = 1\n    b = 2\n\n\n"), base)

    def test_assinatura_acusa_mudanca_no_codigo(self):
        base = verificar.assinatura(b"a = 1\n    b = 2\n")
        self.assertNotEqual(verificar.assinatura(b"a = 1\nb = 2\n"), base)
        self.assertNotEqual(verificar.assinatura(b"a = 2\n    b = 2\n"), base)


if __name__ == "__main__":
    unittest.main()
