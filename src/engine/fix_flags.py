"""Fix Flags: corrige as flag notes do desenho (NL006 vira NL0006).

Porte de vba_referencia/fixflags. Todo o trabalho em cada texto roda dentro do CATIA
(catia_scripts/fix_flags.catvbs), folha por folha; a sequencia e as mensagens ficam aqui.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional

from engine import font_check as fc
from engine.catia_bridge import CatiaBridge, CatiaError

SCRIPT = "fix_flags.catvbs"
TITULO_AVISO = "E1DT - Fix de Flag Notes"
TITULO_CONFIRMA = "E1DT - Confirmar Fix de Flag Notes"
TITULO_RESULTADO = "E1DT - Resultado do Fix"
TITULO_ERRO = "E1DT - Erro no Fix"

SEM_DOCUMENTO = "Não existe nenhum documento aberto no CATIA."
NAO_E_DESENHO = "O documento ativo não é um CATDrawing.\r\n\r\nAbra o desenho 2D e execute novamente."
CONFIRMACAO = (
    "Esta feature irá corrigir as Flag Notes.\r\n\r\n"
    "Exemplo: NL006 será alterado para NL0006.\r\n\r\n"
    "Tipos reconhecidos:\r\n"
    "- Right Flag;\r\n"
    "- Left Flag;\r\n"
    "- Both Flag;\r\n"
    "- Flags fixas com cadeado;\r\n"
    "- Flags aplicadas pelo Text Editor.\r\n\r\n"
    "O tipo exato da Flag será preservado.\r\n"
    "Flags já corretas não são alteradas.\r\n"
    "Nenhum espaço será adicionado ao texto.\r\n\r\n"
    "Salve uma cópia do desenho antes do teste.\r\n\r\n"
    "Deseja continuar?"
)

CORRIGIDA, JA_CORRETA, RESTAURADA, NAO_RESTAURADA, ERRO, PARA_CORRIGIR = "C", "J", "R", "N", "E", "P"
NOME_RESULTADO = {
    CORRIGIDA: "Corrigida",
    JA_CORRETA: "Já correta",
    RESTAURADA: "Falhou, texto restaurado",
    NAO_RESTAURADA: "Falhou, não restaurada",
    ERRO: "Erro",
    PARA_CORRIGIR: "Para corrigir",
}
NOME_FRAME = {
    7: "Right Flag",
    8: "Left Flag",
    9: "Both Flag",
    57: "Right Flag fixa",
    58: "Left Flag fixa",
    59: "Both Flag fixa",
}
ORIGEM_OBJETO, ORIGEM_TEXT_EDITOR = 1, 2

CONTADORES = (
    "textos", "flags", "objeto", "text_editor", "cadeado",
    "corrigidas", "ja_corretas", "ignoradas", "falhas", "restauradas", "erros",
)


@dataclass
class FlagItem:
    """Flag reconhecida e o que aconteceu com ela."""

    sheet_name: str
    view_index: int
    view_name: str
    item_index: int
    item_name: str
    before: str
    after: str
    frame: int
    origin: int
    result: str
    order: int = 0

    is_dim = False  # o navegador do Font Check tambem aceita cotas

    @property
    def ok(self) -> bool:
        return self.result in (CORRIGIDA, JA_CORRETA)

    @property
    def tipo(self) -> str:
        nome = NOME_FRAME.get(self.frame, str(self.frame))
        return nome + (" (Text Editor)" if self.origin == ORIGEM_TEXT_EDITOR else "")


@dataclass
class FixReport:
    doc_full_name: str
    textos: int = 0
    flags: int = 0
    objeto: int = 0
    text_editor: int = 0
    cadeado: int = 0
    corrigidas: int = 0
    ja_corretas: int = 0
    ignoradas: int = 0
    falhas: int = 0
    restauradas: int = 0
    erros: int = 0
    items: List[FlagItem] = field(default_factory=list)
    stopped: bool = False

    def somar(self, valores: List[str]) -> None:
        for nome, valor in zip(CONTADORES, valores):
            setattr(self, nome, getattr(self, nome) + int(valor))

    @property
    def mensagem(self) -> str:
        return (
            "Fix de Flag Notes concluído.\r\n\r\n"
            f"DrawingTexts analisados: {self.textos}\r\n"
            f"Flags reconhecidas: {self.flags}\r\n\r\n"
            f"Flags no objeto inteiro: {self.objeto}\r\n"
            f"Flags pelo Text Editor: {self.text_editor}\r\n"
            f"Flags fixas com cadeado: {self.cadeado}\r\n\r\n"
            f"Flags corrigidas: {self.corrigidas}\r\n"
            f"Flags que já estavam corretas: {self.ja_corretas}\r\n"
            f"Textos ignorados: {self.ignoradas}\r\n"
            f"Falhas de validação: {self.falhas}\r\n"
            f"Textos restaurados: {self.restauradas}\r\n"
            f"Erros: {self.erros}\r\n\r\n"
            "Execute o Check novamente para confirmar."
        )


class FixInterrompido(CatiaError):
    """Um erro parou o fix no meio. O que ja foi feito continua em report."""

    def __init__(self, descricao: str, numero: int, report: Optional[FixReport] = None):
        super().__init__(descricao, numero)
        self.report = report

    @property
    def mensagem(self) -> str:
        return f"O fix foi interrompido.\r\n\r\nErro: {self.number}\r\nDescrição: {self}"


def run_fix_flags(
    bridge: CatiaBridge,
    confirm: Callable[[str, str], bool],
    warn: Callable[[str, str], None],
    progress: Optional[Callable[[int, int], None]] = None,
    should_stop: Optional[Callable[[], bool]] = None,
) -> Optional[FixReport]:
    """Corrige as flags do desenho ativo. Retorna None se nao houver o que fazer ou se cancelar."""
    try:
        situacao = bridge.call(SCRIPT, "LerDesenho")[0]
    except CatiaError as exc:
        raise FixInterrompido(str(exc), exc.number) from exc
    if situacao[0] == "0":
        warn(SEM_DOCUMENTO, TITULO_AVISO)
        return None
    if situacao[0] == "1":
        warn(NAO_E_DESENHO, TITULO_AVISO)
        return None
    if not confirm(CONFIRMACAO, TITULO_CONFIRMA):
        return None

    doc_full_name, total_folhas = situacao[1], int(situacao[2])
    report = FixReport(doc_full_name)
    try:
        for i in range(1, total_folhas + 1):
            if should_stop and should_stop():
                report.stopped = True
                break
            _ler_folha(report, bridge.call(SCRIPT, "CorrigirFolha", doc_full_name, i))
            if progress:
                progress(i, total_folhas)
        bridge.call(SCRIPT, "Finalizar", doc_full_name, True)
    except FixInterrompido:
        _limpar_selecao(bridge, doc_full_name)
        raise
    except CatiaError as exc:
        _limpar_selecao(bridge, doc_full_name)
        raise FixInterrompido(str(exc), exc.number, report) from exc
    return report


def _limpar_selecao(bridge: CatiaBridge, doc_full_name: str) -> None:
    """Como no VBA, depois de um erro so limpa a selecao. Nao pode esconder o erro original."""
    try:
        bridge.call(SCRIPT, "Finalizar", doc_full_name, False)
    except CatiaError:
        pass


def _ler_folha(report: FixReport, registros: List[List[str]]) -> None:
    cabecalho = registros[0]
    nome_folha = cabecalho[1]
    report.somar(cabecalho[2:])
    aborto = None
    for registro in registros[1:]:
        if registro[0] == "F":
            _, i_vista, i_item, nome_item, nome_vista, antes, depois, frame, origem, resultado = registro
            report.items.append(FlagItem(
                sheet_name=nome_folha,
                view_index=int(i_vista),
                view_name=nome_vista,
                item_index=int(i_item),
                item_name=nome_item,
                before=antes,
                after=depois,
                frame=int(frame),
                origin=int(origem),
                result=resultado,
                order=len(report.items) + 1,
            ))
        elif registro[0] == "ABORT":
            aborto = registro
    if aborto:
        numero = int(aborto[1]) if aborto[1].lstrip("-").isdigit() else 0
        raise FixInterrompido(aborto[2], numero, report)


def go_to_flag(bridge: CatiaBridge, report: FixReport, item: FlagItem) -> bool:
    """Leva a tela ate a flag. Retorna False se ela ou o desenho nao existem mais."""
    return fc.go_to_item(bridge, report, item, com_seta=True)


# ---------------------------------------------------------------------
# Check de Flags: as mesmas regras, sem gravar nada no desenho.
# ---------------------------------------------------------------------
@dataclass
class FlagCheckReport:
    doc_full_name: str
    textos: int = 0
    flags: int = 0
    objeto: int = 0
    text_editor: int = 0
    cadeado: int = 0
    certas: int = 0
    erradas: int = 0
    ignoradas: int = 0
    erros: int = 0
    items: List[FlagItem] = field(default_factory=list)
    stopped: bool = False


def flags_sem_nota(items: List[FlagItem], notas) -> List[FlagItem]:
    """Flags cujo codigo nao esta na aba DWG_NOTES do Part List. Compara o codigo ja no padrao."""
    from engine.part_list import codigo_da_nota

    codigos = {codigo_da_nota(c) for c in notas}
    return [i for i in items if codigo_da_nota(i.after) not in codigos]


def notas_sem_flag(items: List[FlagItem], notas) -> List[str]:
    """Codigos da aba DWG_NOTES que nao aparecem em nenhuma flag do desenho, na ordem da aba."""
    from engine.part_list import codigo_da_nota

    no_desenho = {codigo_da_nota(i.after) for i in items}
    return [c for c in notas if codigo_da_nota(c) not in no_desenho]


def check_flags(
    bridge: CatiaBridge,
    progress: Optional[Callable[[int, int], None]] = None,
    should_stop: Optional[Callable[[], bool]] = None,
) -> Optional[FlagCheckReport]:
    """Confere as flags do desenho ativo. Em item.after fica como o texto deveria ser."""
    situacao = bridge.call(SCRIPT, "LerDesenho")[0]
    if situacao[0] != "2":
        raise CatiaError(SEM_DOCUMENTO if situacao[0] == "0" else NAO_E_DESENHO)
    cheio, total = situacao[1], int(situacao[2])
    report = FlagCheckReport(cheio)
    for i in range(1, total + 1):
        if should_stop and should_stop():
            report.stopped = True
            break
        registros = bridge.call(SCRIPT, "ConferirFolha", cheio, i)
        c = registros[0]
        nome_folha = c[1]
        for nome, valor in zip(("textos", "flags", "objeto", "text_editor", "cadeado", "certas", "erradas", "ignoradas", "erros"), c[2:]):
            setattr(report, nome, getattr(report, nome) + int(valor))
        for r in registros[1:]:
            if r[0] == "F":
                _, i_vista, i_item, nome_item, nome_vista, antes, certo, frame, origem, resultado = r
                report.items.append(FlagItem(nome_folha, int(i_vista), nome_vista, int(i_item), nome_item, antes, certo, int(frame), int(origem), resultado, len(report.items) + 1))
            elif r[0] == "ABORT":
                raise CatiaError(r[2], int(r[1]) if r[1].lstrip("-").isdigit() else 0)
        if progress:
            progress(i, total)
    return report
