"""Part List do SAP: importacao e comparacao com os callouts do desenho.

Porte de vba_referencia/excel (macros ImportarDadosSAP, CompararPosicaoZona e LimparDadosSAP da
planilha _Callouts.xlsm). As regras sao as mesmas: tests/parity/rodar_paridade_part_list.py compara
com a macro de verdade. Uma diferenca, a pedido: com mais de uma zona, basta uma bater; a macro
deixava vermelho. O OK manual e novo: fica no perfil do usuario, separado por desenho.
"""
from __future__ import annotations

import getpass
import json
import os
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

ABAS_SAP = ("COMPONENT", "PSA")
PRIMEIRA_LINHA_SAP = 5
COL_PN, COL_POSICAO, COL_ZONA, COL_PROGRAMA, COL_SN_INICIAL, COL_SN_FINAL, COL_QUANTIDADE = 2, 13, 14, 15, 18, 19, 20
MAX_ARQUIVOS = 2
TOLERANCIA = 0.000001
XL_UP = -4162
ERRO_EXCEL_MIN = -2146826300  # Value2 devolve celula com erro como um inteiro nesta faixa
ERRO_EXCEL_MAX = -2146826200

TITULO_LIMPAR = "Clean SAP"
PERGUNTA_LIMPAR = "Deseja limpar os dados importados do SAP?\r\n\r\nOs dados do Drawing serão mantidos."


class PartListError(Exception):
    """Falha ao ler um arquivo do SAP."""


def _eh_erro(valor) -> bool:
    return isinstance(valor, int) and ERRO_EXCEL_MIN <= valor <= ERRO_EXCEL_MAX


def _cstr(valor) -> str:
    """CStr do VBA para o que vem de uma celula: 12.0 vira 12."""
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor)


def _trim(s: str) -> str:
    return s.strip(" ")  # Trim do VBA tira so espacos


def normalizar_posicao(valor) -> str:
    if valor is None or _eh_erro(valor):
        return ""
    texto = _cstr(valor)
    for ch in ("\xa0", "\t", "\r", "\n", " "):
        texto = texto.replace(ch, "")
    texto = texto.lstrip("'")
    if not texto:
        return ""
    if not all("0" <= c <= "9" for c in texto):
        return texto.upper()
    return texto.lstrip("0") or "0"


def normalizar_zona(valor) -> str:
    if valor is None or _eh_erro(valor):
        return ""
    texto = _trim(_cstr(valor).upper())
    for ch in ("\xa0", " ", "-", "\t"):
        texto = texto.replace(ch, "")
    return texto


def converter_quantidade(valor) -> float:
    if valor is None or _eh_erro(valor) or isinstance(valor, bool):
        return 0.0
    if isinstance(valor, (int, float)):
        return float(valor)
    texto = _trim(str(valor))
    try:
        return float(texto.replace(",", "."))
    except ValueError:
        return 0.0


def texto_exibido(valor, ler_texto: Callable[[], str]) -> str:
    """O que a celula mostra: 0012 fica 0012. Sem texto ou com ####, vale o valor."""
    if valor is None or _eh_erro(valor):
        return ""
    if isinstance(valor, str):  # o texto mostrado e o proprio valor: evita uma chamada por celula
        return _trim(valor)
    texto = _trim(ler_texto() or "")
    if not texto or "####" in texto:
        texto = _trim(_cstr(valor))
    return texto


@dataclass
class RegistroSAP:
    pn: str
    posicao: str
    zona: str
    quantidade: float
    efetividades: Dict[str, float] = field(default_factory=dict)


@dataclass
class PartList:
    arquivos: List[str]
    registros: List[RegistroSAP]
    linhas_lidas: int

    @property
    def resumo(self) -> str:
        return f"{len(self.arquivos)} arquivo(s), {self.linhas_lidas} linhas lidas, {len(self.registros)} registros"


def somar_linha(
    dados: Dict[str, RegistroSAP], ordem: List[str], pn: str, posicao: str, zona: str, quantidade, efetividade: str,
) -> bool:
    """Consolida por PN + posicao + zona. Efetividades diferentes nao somam: vale a maior delas."""
    pos_norm = normalizar_posicao(posicao)
    if not pos_norm:
        return False
    chave = f"{_trim(pn).upper()}|{pos_norm}|{normalizar_zona(zona)}"
    qtd = converter_quantidade(quantidade)
    ef = efetividade.lower()
    r = dados.get(chave)
    if r is None:
        dados[chave] = RegistroSAP(pn, posicao, zona, qtd, {ef: qtd})
        ordem.append(chave)
    else:
        r.efetividades[ef] = r.efetividades.get(ef, 0.0) + qtd
        r.quantidade = max(0.0, *r.efetividades.values())
    return True


def _chave_ordem(r: RegistroSAP) -> Tuple[int, float, str]:
    # Como a ordenacao do Excel com xlSortTextAsNumbers: numeros primeiro, depois os textos.
    texto = _trim(r.posicao)
    try:
        return 0, float(texto.replace(",", ".")), ""
    except ValueError:
        return 1, 0.0, texto.lower()


def _ler_arquivo(xl, caminho: str, dados: Dict[str, RegistroSAP], ordem: List[str]) -> int:
    nome = os.path.basename(caminho)
    wb = xl.Workbooks.Open(Filename=caminho, UpdateLinks=False, ReadOnly=True, AddToMru=False)
    try:
        ws = None
        for aba in ABAS_SAP:
            try:
                ws = wb.Worksheets(aba)
                break
            except Exception:  # noqa: S112 - a aba nao existe, tenta a outra
                continue
        if ws is None:
            raise PartListError(f"As abas 'COMPONENT' e 'PSA' não foram encontradas em: {nome}")
        ultima = ws.Cells(ws.Rows.Count, COL_POSICAO).End(XL_UP).Row
        if ultima < PRIMEIRA_LINHA_SAP:
            raise PartListError(f"Nenhum registro foi encontrado em: {nome}")
        bloco = ws.Range(ws.Cells(PRIMEIRA_LINHA_SAP, 1), ws.Cells(ultima, COL_QUANTIDADE)).Value2
        lidas = 0
        for i, linha in enumerate(bloco):
            n = PRIMEIRA_LINHA_SAP + i

            def mostrado(coluna: int) -> str:
                return texto_exibido(linha[coluna - 1], lambda c=coluna: ws.Cells(n, c).Text)

            posicao = mostrado(COL_POSICAO)
            if not posicao:
                continue
            valor_pn = linha[COL_PN - 1]
            pn = _trim(_cstr(valor_pn)) if valor_pn is not None and not _eh_erro(valor_pn) else ""
            efetividade = "|".join((mostrado(COL_PROGRAMA), mostrado(COL_SN_INICIAL), mostrado(COL_SN_FINAL)))
            if somar_linha(dados, ordem, pn, posicao, mostrado(COL_ZONA), linha[COL_QUANTIDADE - 1], efetividade):
                lidas += 1
        return lidas
    finally:
        wb.Close(False)


def ler_part_list(caminhos: List[str]) -> PartList:
    """Le um ou dois arquivos do SAP num Excel escondido, que e fechado no fim."""
    import win32com.client

    if len(caminhos) > MAX_ARQUIVOS:
        raise PartListError(f"Selecione no máximo dois arquivos de Part List.\r\n\r\nQuantidade selecionada: {len(caminhos)}")
    dados: Dict[str, RegistroSAP] = {}
    ordem: List[str] = []
    lidas = 0
    xl = win32com.client.DispatchEx("Excel.Application")
    try:
        xl.Visible = False
        xl.DisplayAlerts = False
        xl.ScreenUpdating = False
        for caminho in caminhos:
            lidas += _ler_arquivo(xl, caminho, dados, ordem)
    finally:
        xl.Quit()
    registros = sorted((dados[c] for c in ordem), key=_chave_ordem)
    return PartList(list(caminhos), registros, lidas)


# ---------------------------------------------------------------------
# Comparacao
# ---------------------------------------------------------------------
@dataclass
class Resultado:
    posicao: bool = False
    zona: bool = False
    quantidade: bool = False


@dataclass
class Comparacao:
    desenho: Dict[str, Resultado]  # por posicao normalizada
    sap: List[Resultado]  # na ordem de part_list.registros
    qtd_sap: Dict[str, float]
    zonas_sap: Dict[str, List[str]]  # zonas normalizadas de cada posicao, sem repetir

    def faltam_no_desenho(self, registros: List[RegistroSAP]) -> List[str]:
        return list(dict.fromkeys(normalizar_posicao(r.posicao) for r in registros if normalizar_posicao(r.posicao) not in self.desenho))


def iguais(a: float, b: float) -> bool:
    return abs(a - b) <= TOLERANCIA


def zonas_do_callout(zona) -> List[str]:
    """As zonas dos baloes de uma posicao: "A005; A006" sao duas."""
    return [normalizar_zona(z) for z in str(zona or "").split(";")]


def comparar(callouts, registros: List[RegistroSAP]) -> Comparacao:
    """callouts: objetos com number, zone e qty. A logica de CompararPosicaoZona, com uma diferenca:
    a macro comparava o texto inteiro com a primeira zona do SAP. Aqui, basta uma zona bater."""
    zona_des: Dict[str, List[str]] = {}
    qtd_des: Dict[str, float] = {}
    for c in callouts:
        p = normalizar_posicao(c.number)
        if p:
            zona_des.setdefault(p, zonas_do_callout(c.zone))
            qtd_des[p] = qtd_des.get(p, 0.0) + float(c.qty)

    qtd_sap: Dict[str, float] = {}
    zonas_sap: Dict[str, List[str]] = {}
    for r in registros:
        p = normalizar_posicao(r.posicao)
        if p:
            z = normalizar_zona(r.zona)
            if z not in zonas_sap.setdefault(p, []):
                zonas_sap[p].append(z)
            qtd_sap[p] = qtd_sap.get(p, 0.0) + r.quantidade

    desenho: Dict[str, Resultado] = {}
    for c in callouts:
        p = normalizar_posicao(c.number)
        res = Resultado()
        if p and p in zonas_sap:
            res.posicao = True
            res.zona = any(z in zonas_sap[p] for z in zonas_do_callout(c.zone))
            res.quantidade = res.zona and iguais(qtd_des[p], qtd_sap[p])
        desenho[p] = res

    sap: List[Resultado] = []
    for r in registros:
        p = normalizar_posicao(r.posicao)
        res = Resultado()
        if p and p in zona_des:
            res.posicao = True
            res.zona = normalizar_zona(r.zona) in zona_des[p]
            res.quantidade = res.zona and iguais(qtd_des[p], qtd_sap[p])
        sap.append(res)
    return Comparacao(desenho, sap, qtd_sap, zonas_sap)


# ---------------------------------------------------------------------
# OK manual: a pessoa olhou e aceitou o que o programa nao soube confirmar
# ---------------------------------------------------------------------
def arquivo_ok() -> str:
    teste = os.environ.get("E1DWGTOOLS_OK")
    if teste:
        return teste
    return os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "E1DWGTools", "poszone_ok.json")


class OkManual:
    """OKs de um desenho. Se o que foi aceito mudar, aquele OK deixa de valer."""

    def __init__(self, pn: str):
        self.pn = pn.upper()
        self._tudo = self._ler()

    @staticmethod
    def _ler() -> dict:
        try:
            with open(arquivo_ok(), encoding="utf-8") as f:
                dados = json.load(f)
            return dados if isinstance(dados, dict) else {}
        except (OSError, ValueError):
            return {}

    def _gravar(self) -> None:
        caminho = arquivo_ok()
        os.makedirs(os.path.dirname(caminho), exist_ok=True)
        temporario = caminho + ".tmp"
        with open(temporario, "w", encoding="utf-8") as f:
            json.dump(self._tudo, f, ensure_ascii=False, indent=1)
        os.replace(temporario, caminho)

    def marcar(self, chave: str, desenho: str, sap: Optional[str], origem: str) -> None:
        self._tudo = self._ler()  # o outro lado do HUB pode ter marcado outro item
        self._tudo.setdefault(self.pn, {})[chave] = {
            "desenho": desenho, "sap": sap, "quem": getpass.getuser(), "origem": origem,
        }
        self._gravar()

    def tirar(self, chave: str) -> None:
        self._tudo = self._ler()
        self._tudo.get(self.pn, {}).pop(chave, None)
        self._gravar()

    def vale(self, chave: str, desenho: str, sap: Optional[str]) -> Optional[dict]:
        """O registro do OK, se ainda vale. Sem Part List carregado, confere so o lado do desenho."""
        r = self._tudo.get(self.pn, {}).get(chave)
        if not r or r.get("desenho") != desenho:
            return None
        if sap is not None and r.get("sap") is not None and r.get("sap") != sap:
            return None
        return r
