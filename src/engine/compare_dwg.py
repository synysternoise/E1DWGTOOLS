"""Compare DWG: programa externo, que o HUB so abre. O caminho fica guardado neste computador."""
from __future__ import annotations

import json
import os
from typing import Optional

CHAVE = "compare_dwg"
# Onde o Compare DWG fica na rede. Vale enquanto a pessoa nao escolher outro caminho.
PADRAO = "\\\\Sjkfs17\\mezcal\\Shared\\MACRO\\DWGCOMPARE\\DWGCompare\\DWGCompare.exe"


def padrao() -> str:
    teste = os.environ.get("E1DWGTOOLS_COMPARE_PADRAO")
    return PADRAO if teste is None else teste


def salvo() -> str:
    """O caminho que a pessoa escolheu neste computador, ou ""."""
    return str(_ler().get(CHAVE, ""))


def arquivo_config() -> str:
    """Fica no perfil do usuario, e nao na pasta do HUB, para sobreviver a uma atualizacao."""
    teste = os.environ.get("E1DWGTOOLS_CONFIG")
    if teste:
        return teste
    return os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "E1DWGTools", "config.json")


def _ler() -> dict:
    try:
        with open(arquivo_config(), encoding="utf-8") as f:
            dados = json.load(f)
        return dados if isinstance(dados, dict) else {}
    except (OSError, ValueError):
        return {}


def get_path() -> str:
    """O caminho escolhido neste computador. Sem escolha, o da rede."""
    return salvo() or padrao()


def set_path(caminho: str) -> None:
    dados = _ler()
    dados[CHAVE] = caminho
    destino = arquivo_config()
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    with open(destino, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=2, ensure_ascii=False)


def problema(caminho: str) -> Optional[str]:
    """O que impede de abrir, ou None se estiver tudo certo."""
    if not caminho:
        return "Caminho do Compare DWG ainda não adicionado."
    if not os.path.isfile(caminho):
        return f"Programa não encontrado:\n{caminho}\n\nEle pode ter mudado de lugar. Escolha o caminho de novo."
    return None


def abrir(caminho: str) -> None:
    """Abre o programa, na pasta dele, sem esperar. OSError se o Windows nao conseguir."""
    erro = problema(caminho)
    if erro:
        raise OSError(erro)
    os.startfile(caminho, cwd=os.path.dirname(caminho))  # noqa: S606
