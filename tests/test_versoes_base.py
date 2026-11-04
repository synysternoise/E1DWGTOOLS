"""Trava contra downgrade: confere se o VBA mudou depois de ser convertido.

versoes_base.json guarda a impressao digital de cada macro usada como base. Se uma
macro ja convertida mudar, este teste falha ate a mudanca ser levada para o Python
e a impressao digital ser atualizada com:

    python tests/test_versoes_base.py --atualizar <arquivo>

Cada ferramenta indica a "origem" da macro: "repositorio" e a pasta vba_referencia deste
projeto; "conserto" e o CONSERTO-E1DWGVBA (variavel E1DWGVBA ou o caminho padrao abaixo).
Sem a pasta do CONSERTO, os arquivos dela sao pulados.
"""
import hashlib
import json
import os
import sys
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
ARQUIVO_BASE = os.path.join(AQUI, "versoes_base.json")
PASTA_REPOSITORIO = os.path.join(AQUI, "..", "vba_referencia")
PASTA_CONSERTO = os.environ.get("E1DWGVBA", r"C:\Users\renan\Documents\E1DWGVBA")


def impressao(caminho: str) -> str:
    """SHA-256 ignorando o tipo de quebra de linha."""
    with open(caminho, "rb") as f:
        return hashlib.sha256(f.read().replace(b"\r\n", b"\n")).hexdigest()


def carregar() -> dict:
    with open(ARQUIVO_BASE, encoding="utf-8") as f:
        return json.load(f)


def pasta_de(dados: dict) -> str:
    return PASTA_REPOSITORIO if dados["origem"] == "repositorio" else PASTA_CONSERTO


class VersoesBase(unittest.TestCase):
    def test_macros_convertidas_nao_mudaram(self):
        for ferramenta, dados in carregar()["ferramentas"].items():
            if dados["situacao"] != "convertida":
                continue
            pasta = pasta_de(dados)
            for nome, esperado in dados["arquivos"].items():
                with self.subTest(arquivo=nome):
                    if not os.path.isdir(pasta):
                        self.skipTest("pasta do VBA nao encontrada")
                    self.assertEqual(
                        impressao(os.path.join(pasta, nome)), esperado,
                        f"{nome} mudou depois da conversao de {ferramenta}: leve a mudanca para o Python.",
                    )


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--atualizar":
        base = carregar()
        for nome in sys.argv[2:]:
            for dados in base["ferramentas"].values():
                if nome in dados["arquivos"]:
                    dados["arquivos"][nome] = impressao(os.path.join(pasta_de(dados), nome))
        with open(ARQUIVO_BASE, "w", encoding="utf-8", newline="\n") as f:
            json.dump(base, f, indent=2, ensure_ascii=False)
            f.write("\n")
    else:
        unittest.main()
