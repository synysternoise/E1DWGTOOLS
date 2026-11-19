"""Check de Flags contra a aba DWG_NOTES do Part List: leitura dos codigos e flags sem nota.

Uso:  python -m unittest discover -s tests
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from engine import fix_flags as ff  # noqa: E402
from engine import part_list as pl  # noqa: E402

# Como o UsedRange.Value2 da aba DWG_NOTES do arquivo PARTLIST_17112026_150853 (foto de 19/11/2026).
ABA = (
    (None, None),
    ("EMBRAER", None),
    (None, "Drawing - Part List Preview"),
    ("Note Code", "Description"),
    ("NI0362", "MARK AND IDENTIFY PARTS AND ASSEMBLIES ACCORDING TO NE 01-103."),
    ("NI0926", "PART BASED UPON INFORMATION OF RELEASED PART 170-47121-401."),
    ("NI0928", "THIS DRAWING IS BEING REGISTERED FOR FIRST TIME ... THE RESPONSIBILI"),
    ("NI0928", "TY TO PREVIOUS INFORMATION IS OF PARTNER CANDD."),
    ("NI0990", "TOLERANCE FOR COMPONENTS POSITIONING ON ASSEMBLY +/- 1MM AND/OR +/- 2 DEGREE(S)."),
    (" NL0001 ", "BOND DADO JOINTS ACCORDING TO NE90-007 (CDP400-00) USING ITEM 22."),
    ("nl002", "BOND ACCORDING TO NE90-009 (CDP400-02) USING ITEM 21."),
    (None, None),
)


def flag(depois, ordem):
    return ff.FlagItem("Sheet.1", 1, "Front view", ordem, f"Text.{ordem}", depois, depois, 7, 1, ff.JA_CORRETA, ordem)


class LeituraDasNotas(unittest.TestCase):
    def test_codigos_da_aba(self):
        self.assertEqual(pl.codigos_das_notas(ABA), ["NI0362", "NI0926", "NI0928", "NI0990", "NL0001", "NL0002"])

    def test_sem_cabecalho(self):
        self.assertIsNone(pl.codigos_das_notas((("Codigo", "Texto"), ("NL0001", "x"))))
        self.assertIsNone(pl.codigos_das_notas(None))

    def test_codigo_no_padrao_da_flag(self):
        self.assertEqual(pl.codigo_da_nota(" nl 006"), "NL0006")
        self.assertEqual(pl.codigo_da_nota("NL0006"), "NL0006")
        self.assertEqual(pl.codigo_da_nota(None), "")


class FlagsSemNota(unittest.TestCase):
    def test_so_aponta_flag_que_nao_esta_na_aba(self):
        notas = pl.codigos_das_notas(ABA)
        itens = [flag("NL0001", 1), flag("NL0002", 2), flag("NL0005", 3), flag("NI0928", 4)]
        self.assertEqual([i.after for i in ff.flags_sem_nota(itens, notas)], ["NL0005"])

    def test_nota_sem_flag_fica_fora_desta_lista(self):
        self.assertEqual(ff.flags_sem_nota([flag("NL0001", 1)], ["NL0001", "NL0002", "NI0362"]), [])


class NotasSemFlag(unittest.TestCase):
    def test_aponta_nota_do_part_list_que_nao_esta_no_desenho(self):
        notas = pl.codigos_das_notas(ABA)
        itens = [flag("NL0001", 1), flag("NL0001", 2), flag("NI0928", 3), flag("NL0005", 4)]
        self.assertEqual(ff.notas_sem_flag(itens, notas), ["NI0362", "NI0926", "NI0990", "NL0002"])

    def test_flag_errada_conta_pelo_codigo_certo(self):
        errada = ff.FlagItem("Sheet.1", 1, "Front view", 1, "Text.1", "NL002", "NL0002", 7, 1, ff.PARA_CORRIGIR, 1)
        self.assertEqual(ff.notas_sem_flag([errada], ["NL0002"]), [])


if __name__ == "__main__":
    unittest.main()
