"""Trava contra downgrade: confere se o VBA mudou depois de ser convertido.

versoes_base.json guarda a impressao digital de cada macro usada como base. Se uma
macro ja convertida mudar, este teste falha ate a mudanca ser levada para o Python
e a impressao digital ser atualizada com:

    python tests/test_versoes_base.py --atualizar <arquivo>

Pasta do VBA: variavel E1DWGVBA ou o caminho padrao abaixo. Sem ela, o teste e pulado.
"""
import hashlib
import json
import os
import sys
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
ARQUIVO_BASE = os.path.join(AQUI, "versoes_base.json")
PASTA_VBA = os.environ.get("E1DWGVBA", r"C:\Users\renan\Documents\E1DWGVBA")


def impressao(caminho: str) -> str:
    """SHA-256 ignorando o tipo de quebra de linha."""
    with open(caminho, "rb") as f:
        return hashlib.sha256(f.read().replace(b"\r\n", b"\n")).hexdigest()


def carregar() -> dict:
    with open(ARQUIVO_BASE, encoding="utf-8") as f:
        return json.load(f)


class VersoesBase(unittest.TestCase):
    @unittest.skipUnless(os.path.isdir(PASTA_VBA), "pasta do VBA nao encontrada")
    def test_macros_convertidas_nao_mudaram(self):
        for ferramenta, dados in carregar()["ferramentas"].items():
            if dados["situacao"] != "convertida":
                continue
            for nome, esperado in dados["arquivos"].items():
                with self.subTest(arquivo=nome):
                    self.assertEqual(
                        impressao(os.path.join(PASTA_VBA, nome)), esperado,
                        f"{nome} mudou depois da conversao de {ferramenta}: leve a mudanca para o Python.",
                    )


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--atualizar":
        base = carregar()
        for nome in sys.argv[2:]:
            for dados in base["ferramentas"].values():
                if nome in dados["arquivos"]:
                    dados["arquivos"][nome] = impressao(os.path.join(PASTA_VBA, nome))
        with open(ARQUIVO_BASE, "w", encoding="utf-8", newline="\n") as f:
            json.dump(base, f, indent=2, ensure_ascii=False)
            f.write("\n")
    else:
        unittest.main()
