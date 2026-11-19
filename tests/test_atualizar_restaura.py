"""Qualquer erro na conversao tem de devolver o CATIA com alertas, tela e interacao ligados."""
import os
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from engine import atualizar_template as at  # noqa: E402


class _App:
    def __init__(self, doc):
        self.Documents = SimpleNamespace(Count=1)
        self.ActiveDocument = doc
        self.ActiveWindow = mock.MagicMock()
        self.DisplayFileAlerts = True
        self.Interactive = True
        self.RefreshDisplay = True
        self.StatusBar = ""
        self.durante = None


class TestRestaura(unittest.TestCase):
    def _converter_com_erro(self, erro):
        doc = mock.MagicMock()
        doc.Name = "X.CATDrawing"
        doc.FullName = r"C:\X.CATDrawing"
        app = _App(doc)

        def aplicar(_self, *_a):
            app.durante = (app.DisplayFileAlerts, app.Interactive, app.RefreshDisplay)
            raise erro

        folha = mock.MagicMock()
        folha.Name = "Sheet.1"
        with mock.patch.object(at, "drawing_sheets", return_value=[folha]), \
                mock.patch.object(at, "format_from_background", return_value="A1"), \
                mock.patch.object(at, "_localizar", return_value=r"C:\t.CATDrawing"), \
                mock.patch.object(at._Conversao, "aplicar_template", aplicar):
            with self.assertRaises(type(erro)):
                at.run_update_template(SimpleNamespace(app=app), lambda *a: "A1")
        # Prova que o teste passou pelo trecho com tudo desligado.
        self.assertEqual(app.durante, (False, False, False))
        self.assertEqual((app.DisplayFileAlerts, app.Interactive, app.RefreshDisplay), (True, True, True))

    def test_erro_do_python(self):
        self._converter_com_erro(ValueError("inesperado"))

    def test_erro_conhecido(self):
        self._converter_com_erro(at.TemplateError("falhou", 1))


if __name__ == "__main__":
    unittest.main()
