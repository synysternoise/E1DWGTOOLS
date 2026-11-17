"""Update Template: troca o formato (etiqueta) no proprio desenho. As vistas nao sao tocadas.

Porte de update.txt, a versao de 23/10 do CONSERTO-E1DWGVBA. Substitui engine/update_template.py,
que veio da versao de 14/10, que copiava as vistas para um documento novo.

Roda inteiro por COM, sem script dentro do CATIA: abrir, copiar e colar ficam 10 vezes mais lentos
dentro de um script, e o comando seguinte a qualquer script tambem. A legenda tem poucos textos, e
por isso o custo de COM nela e pequeno.
"""
from __future__ import annotations

import json
import os
import re
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

import pywintypes

from engine.catia_bridge import CatiaBridge, CatiaError
from engine.documento import eh_desenho

PASTA_TEMPLATES = "\\\\nfscad05.sjk.emb\\dmuv5\\smarteam\\b01\\v5\\DLNames\\START_UP\\"
FORMATOS = ("3A0", "A0", "A1", "A2", "A3", "E3")
VB_OBJECT_ERROR = -2147221504
FORMAT_TEXT_NAME = "Text.68"
SHEET_COUNT_PARAMETER = "No_of_Sheets"
WORKING_SHEET_NUMBER_TEXT = "Text.1"
CAT_PAPER_USER = 13
POSITION_TOLERANCE = 0.001
RESERVAS = ("|", "~", "^", "`")

# Uma busca seleciona o conteudo inteiro da view. Se algum tipo nao existir na versao do CATIA, a
# busca falha inteira: por isso as reservas.
BUSCAS = (
    "(Drafting.Geometry + Drafting.Text + Drafting.Area Fill + Drafting.Table + Drafting.Picture + "
    "Drafting.Dimension + Drafting.Arrow + Drafting.Axis Line + Drafting.Center Line + Drafting.Thread + "
    "Drafting.Datum Feature + Drafting.Datum Target + Drafting.Geometrical Tolerance + Drafting.Balloon),sel",
    "(Drafting.Geometry + Drafting.Text + Drafting.Area Fill + Drafting.Table + Drafting.Picture),sel",
    "(Drafting.Geometry + Drafting.Text),sel",
)

TITULO_RESULTADO = "Migração de Template"
TITULO_ERRO = "Erro"
TITULO_PEDIDO = "Definição de Formato"
FORMATO_SUGERIDO = "A0"
PERGUNTA_FORMATO = (
    "Não foi possível identificar automaticamente o tamanho da folha no Background.\r\n\r\n"
    "Digite um dos formatos abaixo:\r\n\r\n"
    "3A0\r\nA0\r\nA1\r\nA2\r\nA3\r\nE3"
)
AVISO_PARCIAL = (
    "\r\n\r\nO desenho pode ter ficado parcialmente convertido.\r\n"
    "Feche-o SEM SALVAR e abra novamente antes de repetir a conversão."
)
COM_ERROR = pywintypes.com_error


class TemplateError(CatiaError):
    """Falha na conversao. Se modified for True, o desenho pode ter ficado parcial."""

    report = None

    def __init__(self, descricao: str, numero: int, origem: str = "ConvertTemplate", modified: bool = False):
        super().__init__(descricao, numero)
        self.origem = origem
        self.modified = modified

    @property
    def mensagem(self) -> str:
        return (
            "Falha na execução.\r\n\r\n"
            f"Erro número: {self.number}\r\n"
            f"Origem: {self.origem}\r\n"
            f"Descrição: {self}"
            + (AVISO_PARCIAL if self.modified else "")
        )


@dataclass
class TemplateReport:
    doc_full_name: str
    sheets: List[Tuple[str, str]] = field(default_factory=list)  # nome da folha, formato
    warnings: List[str] = field(default_factory=list)

    @property
    def mensagem(self) -> str:
        resumo = "".join(f"{nome}: {formato}\r\n" for nome, formato in self.sheets)
        avisos = ""
        if self.warnings:
            avisos = "\r\nAvisos:\r\n" + "".join(f"- {a}\r\n" for a in self.warnings)
        return (
            "Template atualizado no próprio desenho.\r\n\r\n"
            f"{resumo}{avisos}\r\n"
            "Confira o desenho e salve para confirmar."
        )


# ---------------------------------------------------------------------
# Regras, sem CATIA
# ---------------------------------------------------------------------
def normalize_format(texto: str) -> str:
    """O conteudo precisa resultar exatamente em um formato; nao procura dentro de frases."""
    valor = texto.strip(" ").upper()
    for ch in ("\r", "\n", "\t", "\xa0"):
        valor = valor.replace(ch, "")
    return valor.strip(" ")


def is_valid_format(formato: str) -> bool:
    return normalize_format(formato) in FORMATOS


# Nome do arquivo do template, do mais novo para o mais antigo. O "_" depois do formato impede que o A0
# case com o 3A0. Em 11/11/2026 a pasta da rede passou a ter E1_DRW_TEMPLATE_A0_R00.CATDrawing.
PREFIXOS_TEMPLATE = ("E1_DRW_TEMPLATE_{formato}_", "E1_DRAWING TEMPLATE_SHEET {formato}_CATIAV5R32")


def find_template(pasta: str, formato: str) -> str:
    """Primeiro arquivo .CATDrawing da pasta que comeca com o nome do template do formato.
    O nome novo vale antes do antigo, quando os dois estao na pasta."""
    if not pasta.endswith("\\"):
        pasta += "\\"
    # Sem ordenar: os.listdir devolve na mesma ordem que o Dir$ do VBA.
    nomes = os.listdir(pasta)
    for modelo in PREFIXOS_TEMPLATE:
        prefixo = modelo.format(formato=normalize_format(formato)).lower()
        for nome in nomes:
            minusculo = nome.lower()
            if minusculo.endswith(".catdrawing") and minusculo.startswith(prefixo):
                return pasta + nome
    return ""


# Vistas de zona do template: ZONE, ZONE A0, ZONE A0[3], ZONES_A0_SHT1, ZONES_A0_SHT1[2]...
# No template do E3 o nome vem sem o S: ZONE_E3_SHT1.
RE_VISTA_ZONA = re.compile(r"^(ZONE(\s+(3A0|A0|A1|A2|A3|E3))?|ZONES?_(3A0|A0|A1|A2|A3|E3)_SHT\d*)(\[\d+\])?$")
RE_ROTULO_ZONA = re.compile(r"^([A-F])(\d{1,3})$")
# Faixa da margem onde ficam os numeros das colunas, como no Position and Zone.
MARGEM_PROPORCAO = 0.12
MARGEM_MINIMA = 15.0
MARGEM_MAXIMA = 80.0
MARGEM_MIN_COLUNAS = 3
MARGEM_PAR_X = 2.0  # o mesmo numero aparece em cima e embaixo, na mesma coluna


def is_aux_view(nome: str) -> bool:
    """Vista de zona do template. O nome precisa ser exato, para nao apagar views do usuario
    com ZONE no nome. Sem o formato no criterio, a grade antiga do A0 ficava embaixo da nova."""
    s = nome.strip(" ").upper()
    return s.startswith("ZONES_A1_SHT") or bool(RE_VISTA_ZONA.match(s))


def nome_sem_contador(nome: str) -> str:
    """O CATIA acrescenta [2], [3]... ao nome de uma view colada onde ja existe outra igual."""
    return re.sub(r"\[\d+\]$", "", nome.strip(" ")).upper()


def emparelhar(dados: list, nomes_colados: List[str]) -> list:
    """Para cada view colada, os dados (nome, x, y) da view do template de onde ela veio.

    Pelo nome; o que nao casar pelo nome segue a ordem em que foi copiado.
    """
    livres = list(dados)
    saida: list = [None] * len(nomes_colados)
    for i, colado in enumerate(nomes_colados):
        for d in livres:
            if nome_sem_contador(d[0]) == nome_sem_contador(colado):
                saida[i] = d
                livres.remove(d)
                break
    for i in range(len(saida)):
        if saida[i] is None:
            saida[i] = livres.pop(0)
    return saida


def numero_na_folha(coluna: int, numero_folha: int) -> int:
    """A folha entra na dezena, como na zona: coluna 9 e 9 na folha 1, 29 na folha 2, 39 na folha 3."""
    return coluna if numero_folha <= 1 else numero_folha * 10 + coluna


def margin_columns(textos, largura: float, altura: float) -> List[Tuple[float, float, int]]:
    """Numeros das colunas na margem. textos: (texto, x, y). Devolve (x, y, coluna).

    So vale o numero que aparece em cima e embaixo na mesma coluna: assim um numero solto da
    legenda, que tambem fica perto da borda de baixo, nunca e trocado.
    """
    if largura <= 0 or altura <= 0:
        return []
    faixa = min(max(altura * MARGEM_PROPORCAO, MARGEM_MINIMA), MARGEM_MAXIMA)
    cima, baixo = [], []
    for texto, x, y in textos:
        valor = str(texto).strip(" ")
        if not (0 < len(valor) <= 2 and is_all_digits(valor)) or int(valor) <= 0:
            continue
        if altura - faixa <= y <= altura:
            cima.append((x, y, int(valor)))
        elif 0 <= y <= faixa:
            baixo.append((x, y, int(valor)))
    achados = []
    for b in baixo:
        for c in cima:
            if c[2] == b[2] and abs(c[0] - b[0]) <= MARGEM_PAR_X:
                achados.extend(m for m in (b, c) if m not in achados)
    if len({m[2] for m in achados}) < MARGEM_MIN_COLUNAS:
        return []
    return achados


def zone_label(texto: str, numero_folha: int) -> str:
    """Rotulo da grade na folha: F6 vira F26 na folha 2, E005 vira E025. "" se nao for rotulo."""
    m = RE_ROTULO_ZONA.match(str(texto).strip(" ").upper())
    if not m or int(m.group(2)) <= 0:
        return ""
    return m.group(1) + str(numero_na_folha(int(m.group(2)), numero_folha)).zfill(len(m.group(2)))


def short_parameter_name(nome: str) -> str:
    return nome[nome.rfind("\\") + 1:]


def is_all_digits(valor: str) -> bool:
    return bool(valor) and all("0" <= c <= "9" for c in valor)


def position_key(x: float, y: float) -> Tuple[float, float]:
    return round(x, 2), round(y, 2)


@dataclass
class TextLink:
    """Um texto do template ligado a parametros. template_text tem uma reserva por parametro."""

    template_text: str
    reserva: str
    parametros: List[str]
    x: float
    y: float
    nome: str


def build_link(texto: str, marcadores: Dict[str, str], x: float, y: float, nome: str) -> Optional[TextLink]:
    """Acha os marcadores no texto lido. marcadores: valor do marcador -> nome do parametro."""
    achados = []
    for marca, parametro in marcadores.items():
        pos = texto.find(marca)
        while pos >= 0:
            achados.append((pos, len(marca), parametro))
            pos = texto.find(marca, pos + len(marca))
    if not achados:
        return None
    # Mesma ordenacao da macro: da esquerda para a direita, com troca simples.
    for i in range(len(achados) - 1):
        for j in range(i + 1, len(achados)):
            if achados[j][0] < achados[i][0]:
                achados[i], achados[j] = achados[j], achados[i]
    reserva = next((r for r in RESERVAS if r not in texto), "")
    if not reserva:
        return None
    saida, cursor, nomes = [], 0, []
    for pos, tamanho, parametro in achados:
        if pos >= cursor:
            saida.append(texto[cursor:pos] + reserva)
            nomes.append(parametro)
            cursor = pos + tamanho
    saida.append(texto[cursor:])
    return TextLink("".join(saida), reserva, nomes, x, y, nome)


def _valor(p) -> str:
    """ValueAsString e um metodo: sem chamar, a comparacao com o marcador falharia em silencio."""
    return p.ValueAsString()


def _descricao_com(exc: COM_ERROR) -> str:
    info = exc.excepinfo
    return (info[2] if info and info[2] else exc.strerror) or "erro desconhecido"


# ---------------------------------------------------------------------
# Leitura do desenho
# ---------------------------------------------------------------------
def drawing_sheets(doc) -> list:
    """Folhas de desenho, sem as detail sheets.

    Quem chama guarda estes objetos e nao volta a doc.Sheets: buscar a folha a cada comando deixa
    colar e ativar varias vezes mais lentos.
    """
    saida = []
    folhas = doc.Sheets
    for i in range(1, folhas.Count + 1):
        folha = folhas.Item(i)
        try:
            detalhe = folha.IsDetail
            if callable(detalhe):  # sem a biblioteca de tipos, o COM entrega como metodo
                detalhe = detalhe()
        except COM_ERROR:
            detalhe = False
        if not detalhe:
            saida.append(folha)
    return saida


def text_by_name(vista, nome: str):
    try:
        textos = vista.Texts
        total = textos.Count
    except COM_ERROR:
        return None
    alvo = nome.strip(" ").lower()
    for i in range(1, total + 1):
        try:
            t = textos.Item(i)
            if str(t.Name).strip(" ").lower() == alvo:
                return t
        except COM_ERROR:
            continue
    return None


def format_from_background(folha) -> str:
    """Primeiro o Text.68; depois qualquer texto cujo conteudo seja exatamente um formato."""
    try:
        fundo = folha.Views.Item(2)
    except COM_ERROR:
        return ""
    t = text_by_name(fundo, FORMAT_TEXT_NAME)
    if t is not None:
        try:
            valor = normalize_format(str(t.Text))
        except COM_ERROR:
            valor = ""
        if is_valid_format(valor):
            return valor
    try:
        textos = fundo.Texts
        total = textos.Count
    except COM_ERROR:
        return ""
    for i in range(1, total + 1):
        try:
            valor = normalize_format(str(textos.Item(i).Text))
        except COM_ERROR:
            continue
        if is_valid_format(valor):
            return valor
    return ""


# ---------------------------------------------------------------------
# Vinculos da legenda
# ---------------------------------------------------------------------
def map_text_links(parametros, fundo) -> Dict[str, TextLink]:
    """Qual texto do Background usa qual parametro.

    A API nao informa. Cada parametro do template recebe um marcador unico, cada texto e lido uma
    vez e os marcadores que aparecem indicam o parametro e a posicao. Os valores originais sao
    devolvidos e o template nunca e salvo. Chave: nome do texto, unica mesmo com nomes repetidos.
    """
    links: Dict[str, TextLink] = {}
    try:
        total = parametros.Count
    except COM_ERROR:
        return links
    originais = []
    marcadores: Dict[str, str] = {}
    for i in range(1, total + 1):
        try:
            p = parametros.Item(i)
            nome = short_parameter_name(p.Name)
            original = _valor(p)
        except COM_ERROR:
            originais.append(None)
            continue
        originais.append(original)
        marca = _marcar(p, i)
        if marca:
            marcadores[marca] = nome
    try:
        if marcadores:
            textos = fundo.Texts
            for k in range(1, textos.Count + 1):
                try:
                    t = textos.Item(k)
                    nome = str(t.Name).strip(" ")
                    link = build_link(str(t.Text), marcadores, t.x, t.y, nome)
                except COM_ERROR:
                    continue
                if link is not None:
                    chave, sufixo = nome, 1
                    while chave.lower() in (c.lower() for c in links):
                        sufixo += 1
                        chave = f"{nome}#{sufixo}"
                    links[chave] = link
    finally:
        for i, original in enumerate(originais, 1):
            if original is None:
                continue
            try:
                p = parametros.Item(i)
                if _valor(p) != original:
                    p.ValuateFromString(original)
            except COM_ERROR:
                pass
    return links


def _marcar(p, i: int) -> str:
    """Parametro de texto: "#E1P<n>#". Parametro inteiro: marcador numerico de 6 digitos."""
    for marca in (f"#E1P{i}#", str(734000 + i)):
        try:
            p.ValuateFromString(marca)
            if _valor(p) == marca:
                return marca
        except COM_ERROR:
            pass
    return ""


def link_key_for_parameter(links: Dict[str, TextLink], parametro: str) -> str:
    for chave, link in links.items():
        if any(n.lower() == parametro.lower() for n in link.parametros):
            return chave
    return ""


def sheet_field_prefixes(fundo, link: TextLink) -> List[Tuple[float, float]]:
    """Textos "1 /" separados do campo SHEET/OF, a esquerda dele na mesma linha."""
    if "/" in link.template_text.replace(link.reserva, ""):
        return []
    saida = []
    try:
        textos = fundo.Texts
        total = textos.Count
    except COM_ERROR:
        return saida
    for i in range(1, total + 1):
        try:
            t = textos.Item(i)
            valor = str(t.Text).strip(" ").replace(" ", "")
            if valor and not valor.replace("1", "").replace("/", ""):
                x, y = t.x, t.y
                if abs(y - link.y) <= 10.0 and x < link.x and link.x - x <= 40.0:
                    saida.append((x, y))
        except COM_ERROR:
            continue
    return saida


# Template sem texto ligado a No_of_Sheets: o campo SHEET/OF e um texto so com X (XX, X/XX, 1/XX).
RE_RESERVA_FOLHA = re.compile(r"^(?:[1X]{1,2}/)?X{1,3}$")
ROTULOS_FOLHA = ("SHEET/OF", "SHEETOF", "SHT/OF", "SHTOF")
CELULA_FOLHA_X = 30.0  # o valor fica embaixo do rotulo, na mesma celula
CELULA_FOLHA_Y = 25.0
LEGENDA_LARGURA = 260.0  # sem rotulo: canto de baixo, a direita
LEGENDA_ALTURA = 90.0


def _so_letras(valor: str) -> str:
    return re.sub(r"[^A-Z0-9/]", "", valor.upper())


def escolher_reserva_folha(textos, largura: float):
    """Qual texto (valor, x, y, nome) e o XX do campo SHEET/OF. Embaixo do rotulo SHEET/OF, o mais perto.
    Sem rotulo no Background, o XX mais a direita no canto da legenda. None se nao houver."""
    candidatos = [t for t in textos if RE_RESERVA_FOLHA.match(_so_letras(t[0]))]
    rotulos = [t for t in textos if _so_letras(t[0]) in ROTULOS_FOLHA]
    melhor, distancia = None, 0.0
    for r in rotulos:
        for c in candidatos:
            if abs(c[1] - r[1]) <= CELULA_FOLHA_X and 0 < r[2] - c[2] <= CELULA_FOLHA_Y:
                d = abs(c[1] - r[1]) + (r[2] - c[2])
                if melhor is None or d < distancia:
                    melhor, distancia = c, d
    if rotulos:
        return melhor
    for c in candidatos:
        if c[1] >= largura - LEGENDA_LARGURA and c[2] <= LEGENDA_ALTURA and (melhor is None or c[1] > melhor[1]):
            melhor = c
    return melhor


def sheet_field_without_link(fundo, largura: float, links: Dict[str, TextLink]) -> str:
    """Poe em links o campo SHEET/OF de um template que nao o liga a No_of_Sheets. Devolve a chave, ou ""."""
    lidos = []
    try:
        textos = fundo.Texts
        total = textos.Count
    except COM_ERROR:
        return ""
    for i in range(1, total + 1):
        try:
            t = textos.Item(i)
            valor = str(t.Text)
            if 0 < len(valor.strip(" ")) <= 12:  # rotulo e reserva sao curtos: so esses precisam da posicao
                lidos.append((valor, t.x, t.y, str(t.Name).strip(" ")))
        except COM_ERROR:
            continue
    achado = escolher_reserva_folha(lidos, largura)
    if achado is None:
        return ""
    _valor_lido, x, y, nome = achado
    # Se o XX estava ligado a um parametro de outro nome, esse vinculo sai: o campo passa a ser o da folha.
    for chave in [c for c, l in links.items() if position_key(l.x, l.y) == position_key(x, y)]:
        del links[chave]
    link = TextLink(RESERVAS[0], RESERVAS[0], [SHEET_COUNT_PARAMETER], x, y, nome)
    if not sheet_field_prefixes(fundo, link):
        link.template_text = "1/" + RESERVAS[0]
    chave, sufixo = nome, 1
    while chave.lower() in (c.lower() for c in links):
        sufixo += 1
        chave = f"{nome}#{sufixo}"
    links[chave] = link
    return chave


class _IndiceTextos:
    """Textos colados de uma vista: pelo nome, se a posicao conferir; senao, pela posicao."""

    def __init__(self, vista):
        self.vista = vista
        self._por_nome = None
        self._por_posicao = None

    def _nomes(self) -> dict:
        if self._por_nome is None:
            self._por_nome = {}
            for t in self._todos():
                try:
                    self._por_nome.setdefault(str(t.Name).strip(" ").lower(), t)
                except COM_ERROR:
                    pass
        return self._por_nome

    def posicoes(self) -> dict:
        if self._por_posicao is None:
            self._por_posicao = {}
            for t in self._todos():
                try:
                    self._por_posicao.setdefault(position_key(t.x, t.y), t)
                except COM_ERROR:
                    pass
        return self._por_posicao

    def todos(self):
        return self._todos()

    def _todos(self):
        try:
            textos = self.vista.Texts
            total = textos.Count
        except COM_ERROR:
            return
        for i in range(1, total + 1):
            try:
                yield textos.Item(i)
            except COM_ERROR:
                continue

    def esquecer(self) -> None:
        """Textos foram recriados: a proxima busca le a vista de novo."""
        self._por_nome = None
        self._por_posicao = None

    def localizar(self, nome: str, x: float, y: float):
        c = self._nomes().get(nome.lower())
        if c is not None:
            try:
                if abs(c.x - x) <= POSITION_TOLERANCE and abs(c.y - y) <= POSITION_TOLERANCE:
                    return c
            except COM_ERROR:
                pass
        return self.posicoes().get(position_key(x, y))


def has_working_sheet_number(vista_principal, campo_x: float, campo_y: float) -> bool:
    """A Main View tem o numero da folha ao lado do SHEET/OF? Coordenadas convertidas para a folha."""
    try:
        escala = vista_principal.Scale
        if escala <= 0:
            escala = 1
        textos = vista_principal.Texts
        total = textos.Count
        vx, vy = vista_principal.x, vista_principal.y
    except COM_ERROR:
        return False
    for i in range(1, total + 1):
        try:
            t = textos.Item(i)
            valor = str(t.Text).strip(" ")
            if 0 < len(valor) <= 3 and is_all_digits(valor):
                sx, sy = vx + t.x * escala, vy + t.y * escala
                if abs(sy - campo_y) <= 15.0 and abs(sx - campo_x) <= 40.0:
                    return True
        except COM_ERROR:
            continue
    return False


def _gravar_texto(t, novo: str) -> bool:
    """Troca o texto. Se ele tem largura fixa, ajusta para o numero maior nao cair para a linha de baixo."""
    try:
        largura = t.WrappingWidth
    except COM_ERROR:
        largura = -1
    t.Text = novo
    if largura > 0:
        try:
            t.WrappingWidth = 0  # o CATIA ajusta a caixa ao texto
            if largura > t.WrappingWidth:
                t.WrappingWidth = largura
        except COM_ERROR:
            pass
    return str(t.Text) == novo


def _apagar(sel, objeto) -> None:
    sel.Clear()
    sel.Add(objeto)
    sel.Delete()
    sel.Clear()


def _ler(objeto, nome: str, *args):
    try:
        valor = getattr(objeto, nome)
        return valor(*args) if args else valor
    except (COM_ERROR, AttributeError):
        return None


def _copiar_formato(sel, velho, novo) -> None:
    """Fonte, tamanho, ancora, angulo, largura, estilo e cor. O que nao der para copiar fica o padrao."""
    for atributo in ("AnchorPosition", "Angle"):
        valor = _ler(velho, atributo)
        if valor is not None:
            try:
                setattr(novo, atributo, valor)
            except COM_ERROR:
                pass
    fonte, tamanho = _ler(velho, "GetFontName", 0, 0), _ler(velho, "GetFontSize", 0, 0)
    try:
        if fonte:
            novo.SetFontName(0, 0, fonte)
        if tamanho:
            novo.SetFontSize(0, 0, tamanho)
    except COM_ERROR:
        pass
    largura = _ler(velho, "WrappingWidth")
    if largura:
        try:
            novo.WrappingWidth = largura
        except COM_ERROR:
            pass
    de, para = _ler(velho, "TextProperties"), _ler(novo, "TextProperties")
    if de is not None and para is not None:
        for atributo in ("Bold", "Italic", "Underline", "Justification", "FrameType"):
            valor = _ler(de, atributo)
            if valor is not None:
                try:
                    setattr(para, atributo, valor)
                except COM_ERROR:
                    pass
        try:
            para.Update()
        except COM_ERROR:
            pass
    try:
        sel.Clear()
        sel.Add(velho)
        cor = sel.VisProperties.GetRealColor(0, 0, 0)
        sel.Clear()
        if isinstance(cor, tuple) and len(cor) >= 4:
            sel.Add(novo)
            sel.VisProperties.SetRealColor(cor[1], cor[2], cor[3], 0)
    except COM_ERROR:
        pass
    finally:
        try:
            sel.Clear()
        except COM_ERROR:
            pass


def recriar_texto(sel, vista, velho, conteudo: str):
    """Troca o texto colado por um novo, igual e sem vinculo nenhum.

    Colado de outro documento, o texto continua ligado aos parametros daquele documento (Edit > Links
    aponta para o template), e trocar o Text nao desfaz o vinculo. A API nao isola o vinculo: o texto
    e recriado com o mesmo nome, lugar e formato, e o colado e apagado.
    """
    novo = vista.Texts.Add(conteudo, velho.x, velho.y)
    _copiar_formato(sel, velho, novo)
    nome = _ler(velho, "Name")
    _apagar(sel, velho)
    if nome:
        try:
            novo.Name = nome
        except COM_ERROR:
            pass
    return novo


# ---------------------------------------------------------------------
# Conversao
# ---------------------------------------------------------------------
class _Conversao:
    """Uma execucao: o desenho, os avisos e o estado do CATIA a devolver no fim."""

    def __init__(self, bridge: CatiaBridge, status, progress):
        self.app = bridge.app
        self.status = status
        self.progress = progress
        self.doc = None
        self.modified = False
        self.report: Optional[TemplateReport] = None
        self.feitas = 0
        self.tempos: Dict[str, float] = {}  # segundos por fase, para o arquivo de diagnostico
        self.inicio = time.perf_counter()

    @contextmanager
    def fase(self, nome: str):
        inicio = time.perf_counter()
        try:
            yield
        finally:
            self.tempos[nome] = self.tempos.get(nome, 0.0) + time.perf_counter() - inicio

    def erro(self, descricao: str, codigo: int, origem: str = "ApplyTemplateToSheets") -> TemplateError:
        return TemplateError(descricao, VB_OBJECT_ERROR + codigo, origem, self.modified)

    def avisar_status(self, texto: str) -> None:
        if self.status:
            self.status(texto)
        try:
            self.app.StatusBar = texto
        except COM_ERROR:
            pass

    def abrir_template(self, caminho: str):
        # Depois de uma conversao o CATIA mantem o template carregado, sem janela, porque o desenho
        # convertido fica ligado a ele. Esse nao atrapalha: o Open abaixo volta a usa-lo e o Close
        # so fecha a janela. Recusa apenas o que a pessoa abriu, que pode ter alteracoes: doc.Saved
        # nao serve para saber, porque e True ate depois de mudar um parametro.
        if self._tem_janela(caminho):
            raise self.erro(
                f"O template já está aberto:\r\n{caminho}\r\n\r\nFeche-o sem salvar e execute novamente.",
                1006, "OpenTemplate",
            )
        # Abre com o CATIA interativo e a tela ligada: uma janela do CATIA ou do SmarTeam ficaria
        # invisivel e travaria.
        self.app.Interactive = True
        self.app.RefreshDisplay = True
        modelo = self.app.Documents.Open(caminho)
        self.app.RefreshDisplay = False
        self.app.Interactive = False
        return modelo

    def _tem_janela(self, caminho: str) -> bool:
        janelas = self.app.Windows
        for i in range(1, janelas.Count + 1):
            try:
                if janelas.Item(i).Parent.FullName.lower() == caminho.lower():
                    return True
            except COM_ERROR:
                continue
        return False

    def selecionar_conteudo(self, sel, vista) -> int:
        buscou = False
        for busca in BUSCAS:
            try:
                sel.Clear()
                sel.Add(vista)
                sel.Search(busca)
                buscou = True
                break
            except COM_ERROR:
                continue
        if not buscou:
            sel.Clear()
            raise self.erro(f"A busca do conteúdo da view {vista.Name} falhou nesta versão do CATIA.", 1205, "SelectViewContents")
        # Os dittos (componentes 2D) nao aparecem na busca.
        try:
            componentes = vista.Components
            for i in range(1, componentes.Count + 1):
                sel.Add(componentes.Item(i))
        except COM_ERROR:
            pass
        return sel.Count

    def aplicar_template(self, caminho: str, folhas: List[dict], todas: List[dict]) -> None:
        modelo = None
        try:
            with self.fase("Abrir o template"):
                modelo = self.abrir_template(caminho)
            self.modified = True  # daqui em diante o desenho comeca a mudar
            self._aplicar(modelo, caminho, folhas, todas)
        except COM_ERROR as exc:
            raise TemplateError(_descricao_com(exc), exc.hresult, "ApplyTemplateToSheets", self.modified) from exc
        finally:
            with self.fase("Fechar o template"):
                self.fechar_template(modelo)

    def fechar_template(self, modelo) -> None:
        """Como o On Error Resume Next da macro: um passo que falha nao impede os outros."""
        passos = [self.doc.Activate] if modelo is None else [modelo.Selection.Clear, modelo.Close, self.doc.Activate]
        for passo in passos:
            try:
                passo()
            except COM_ERROR:
                pass

    def _aplicar(self, modelo, caminho: str, folhas: List[dict], todas: List[dict]) -> None:
        folha_modelo = drawing_sheets(modelo)[0]
        fundo_modelo = folha_modelo.Views.Item(2)
        sel_modelo = modelo.Selection
        sel = self.doc.Selection

        # A colagem entre documentos perde os Attribute Links: o mapa e lido antes da copia e os
        # vinculos sao refeitos depois da colagem com os parametros do proprio desenho.
        self.avisar_status("Conversão de template: lendo os vínculos da legenda...")
        # A leitura depende so do arquivo do template: fica guardada ate ele mudar. Sem ela, cada
        # parametro do template e alterado e devolvido, um por um.
        guardado = ler_template_guardado(caminho)
        with self.fase("Ler os vínculos da legenda"):
            if guardado is not None:
                links, margem_lida = guardado
            else:
                links = map_text_links(modelo.Parameters, fundo_modelo)
                margem_lida = self._ler_margem(folha_modelo, fundo_modelo)
                guardar_template(caminho, links, margem_lida)
        chave_total = link_key_for_parameter(links, SHEET_COUNT_PARAMETER)
        if not chave_total:
            # Template novo (R00): o campo e um "XX" sem vinculo. Folha 1 vira 1/<total>, as outras so o numero.
            try:
                largura_modelo = folha_modelo.GetPaperWidth()
            except COM_ERROR:
                largura_modelo = 0.0
            chave_total = sheet_field_without_link(fundo_modelo, largura_modelo, links)
        prefixos = []
        if chave_total:
            prefixos = sheet_field_prefixes(fundo_modelo, links[chave_total])
        else:
            self.report.warnings.append(
                f"Nenhum texto do template está ligado a {SHEET_COUNT_PARAMETER}: numeração das folhas não atualizada."
            )

        # Numeros das colunas na margem: lidos uma vez no template e trocados em cada folha 2 em diante.
        margem = margem_lida if any(f["posicao"] >= 2 for f in folhas) else []
        if not margem and any(f["posicao"] >= 2 for f in folhas):
            self.report.warnings.append("Numeração da margem não encontrada no template: as margens ficaram sem a dezena da folha.")

        # O template precisa estar ativo: com ele inativo o CATIA recusa selecionar os textos.
        with self.fase("Trocar de janela"):
            modelo.Activate()
        self.avisar_status("Conversão de template: copiando o formato novo...")
        with self.fase("Copiar o Background do template"):
            if self.selecionar_conteudo(sel_modelo, fundo_modelo) == 0:
                raise self.erro(f"O Background do template está vazio:\r\n{caminho}", 1200)
            textos_fundo = fundo_modelo.Texts.Count
            sel_modelo.Copy()
            sel_modelo.Clear()
            self.doc.Activate()

        papel = folha_modelo.PaperSize
        orientacao = folha_modelo.Orientation
        largura = folha_modelo.GetPaperWidth() if papel == CAT_PAPER_USER else None
        altura = folha_modelo.GetPaperHeight() if papel == CAT_PAPER_USER else None
        parametros: Dict[str, object] = {}  # cache por template: a falta de um parametro avisa uma vez

        for n, f in enumerate(folhas, 1):
            folha = f["objeto"]
            fundo = folha.Views.Item(2)
            self.avisar_status(f"Conversão de template: folha {n} de {len(folhas)} ({f['nome']})...")

            # Page Setup. 3A0 e E3 chegam como catPaperUser e precisam da largura e da altura.
            with self.fase("Ajustar o papel da folha"):
                folha.PaperSize = papel
                folha.Orientation = orientacao
                if papel == CAT_PAPER_USER:
                    folha.SetPaperWidth(largura)
                    folha.SetPaperHeight(altura)

            # Uma busca + um Delete apagam o formato antigo e um Paste cola o novo.
            with self.fase("Apagar o Background antigo"):
                if self.selecionar_conteudo(sel, fundo) > 0:
                    sel.Delete()
                sel.Clear()
            with self.fase("Colar o Background novo"):
                sel.Add(fundo)
                sel.Paste()
                sel.Clear()

            # Os textos da legenda precisam ter chegado.
            if fundo.Texts.Count < textos_fundo:
                raise self.erro(f"Não foi possível colar o Background do template na folha {f['nome']}.", 1201)

            indice = _IndiceTextos(fundo)
            posicao = f["posicao"]
            # Folha 1: SHEET/OF fica ligado e mostra 1/<total>, e o numero antigo da Main View sai.
            # Folhas 2 em diante: o campo nao e religado e recebe so o numero da folha.
            with self.fase("Refazer os vínculos da legenda"):
                if posicao == 1:
                    self._apagar_numero_antigo(sel, folha.Views.Item(1))
                self._refazer_vinculos(sel, indice, links, chave_total if posicao >= 2 else "", parametros, f["nome"])
            with self.fase("Numerar a folha e a margem"):
                if posicao >= 2 and chave_total:
                    self._numerar_folha(sel, indice, folha.Views.Item(1), links[chave_total], prefixos, posicao, f["nome"])
                if posicao >= 2:
                    self._numerar_margem(indice, margem, posicao, f["nome"])
            with self.fase("Tirar o que sobrou ligado ao template"):
                self._isolar_restantes(sel, indice, links, f["nome"])
            with self.fase("Apagar as grades antigas"):
                self._apagar_views_auxiliares(sel, folha)

            self.feitas += 1
            if self.progress:
                self.progress(self.feitas, len(todas))

        # Views auxiliares do template (ex.: zonas). Views 1 e 2 sao Main e Background.
        # Todas sao copiadas de uma vez: cada ida e volta entre as janelas do template e do desenho custa caro.
        vistas = [folha_modelo.Views.Item(iv) for iv in range(3, folha_modelo.Views.Count + 1)]
        if not vistas:
            return
        with self.fase("Trocar de janela"):
            modelo.Activate()
        sel_modelo.Clear()
        for vista in vistas:
            antes = sel_modelo.Count
            sel_modelo.Add(vista)
            if sel_modelo.Count <= antes:
                raise self.erro(f"Não foi possível selecionar a view {vista.Name} do template.", 1203)
        with self.fase("Copiar as grades do template"):
            sel_modelo.Copy()
            sel_modelo.Clear()
            self.doc.Activate()
        dados = [(str(v.Name), v.x, v.y) for v in vistas]
        for f in folhas:
            folha = f["objeto"]
            antes = folha.Views.Count
            with self.fase("Colar as grades"):
                sel.Clear()
                sel.Add(folha)
                sel.Paste()
                sel.Clear()
            # So reposiciona se todas as views foram coladas; senao uma view do desenho seria movida.
            if folha.Views.Count != antes + len(vistas):
                faltou = dados[min(max(folha.Views.Count - antes, 0), len(dados) - 1)][0]
                raise self.erro(f"Não foi possível colar a view {faltou} na folha {f['nome']}.", 1204)
            coladas = [folha.Views.Item(i) for i in range(antes + 1, antes + len(vistas) + 1)]
            for colada, (nome, x, y) in zip(coladas, emparelhar(dados, [str(c.Name) for c in coladas])):
                colada.x = x
                colada.y = y
                if f["posicao"] >= 2 and is_aux_view(nome):
                    with self.fase("Numerar as grades"):
                        self._numerar_grade(colada, f["posicao"])

    def _ler_margem(self, folha_modelo, fundo_modelo) -> List[Tuple[float, float, int]]:
        textos = []
        try:
            todos = fundo_modelo.Texts
            for i in range(1, todos.Count + 1):
                t = todos.Item(i)
                valor = str(t.Text).strip(" ")
                if 0 < len(valor) <= 2 and is_all_digits(valor):  # so esses precisam da posicao
                    textos.append((valor, t.x, t.y))
            margem = margin_columns(textos, folha_modelo.GetPaperWidth(), folha_modelo.GetPaperHeight())
        except COM_ERROR:
            margem = []
        return margem

    def _numerar_margem(self, indice: _IndiceTextos, margem, numero: int, nome: str) -> None:
        """Folhas 2 em diante: a margem mostra a dezena da folha (29, 28, 27... na folha 2)."""
        falhou = 0
        for x, y, coluna in margem:
            t = indice.posicoes().get(position_key(x, y))
            try:
                if t is None or not _gravar_texto(t, str(numero_na_folha(coluna, numero))):
                    falhou += 1
            except COM_ERROR:
                falhou += 1
        if falhou:
            self.report.warnings.append(f"Folha {numero} ({nome}): {falhou} número(s) da margem não foram atualizados.")

    def _numerar_grade(self, vista, numero: int) -> None:
        """Folhas 2 em diante: os rotulos da grade de zonas ganham a dezena da folha (F6 vira F26)."""
        try:
            travada = bool(vista.LockStatus)
            if travada:
                vista.LockStatus = False
            textos = vista.Texts
            for i in range(1, textos.Count + 1):
                t = textos.Item(i)
                novo = zone_label(str(t.Text), numero)
                if novo:
                    _gravar_texto(t, novo)
            if travada:
                vista.LockStatus = True
        except COM_ERROR:
            self.report.warnings.append(f"Folha {numero}: não foi possível numerar a grade {vista.Name}.")

    def _apagar_numero_antigo(self, sel, vista_principal) -> None:
        """So apaga se o Text.1 tiver apenas digitos, para nao apagar uma nota com esse nome."""
        try:
            t = text_by_name(vista_principal, WORKING_SHEET_NUMBER_TEXT)
            if t is not None and is_all_digits(str(t.Text).strip(" ")):
                _apagar(sel, t)
        except COM_ERROR:
            pass

    def _parametro(self, cache: dict, nome: str):
        chave = nome.lower()
        if chave not in cache:
            try:
                cache[chave] = self.doc.Parameters.Item(nome)
            except COM_ERROR:
                cache[chave] = None
                self.report.warnings.append(
                    f"Parâmetro {nome} não existe no desenho: o campo da legenda ficou com o valor do template."
                )
        return cache[chave]

    def _refazer_vinculos(self, sel, indice: _IndiceTextos, links: Dict[str, TextLink], pular: str, cache: dict, folha: str) -> None:
        """Cada reserva vira o parametro de mesmo nome do desenho, da direita para a esquerda.

        O texto colado e recriado antes: senao ele continua ligado ao parametro do template.
        """
        alvos = []
        for chave, link in links.items():
            if chave.lower() == pular.lower():
                continue
            t = indice.localizar(link.nome, link.x, link.y)
            if t is not None:
                alvos.append((link, t))
        for link, velho in alvos:
            achados = [self._parametro(cache, n) for n in link.parametros]
            try:
                t = recriar_texto(sel, indice.vista, velho, link.template_text)
            except COM_ERROR:
                self.report.warnings.append(
                    f"Folha {folha}: o texto {link.nome} continua ligado ao template (Edit > Links > Isolate)."
                )
                continue
            if any(p is None for p in achados):
                continue  # sem o parametro no desenho, fica o texto do template, sem vinculo; a macro avisa
            try:
                pos = link.template_text.rfind(link.reserva)
                k = len(achados) - 1
                while pos >= 0 and k >= 0:
                    t.InsertVariable(pos + 1, 1, achados[k])
                    k -= 1
                    if pos == 0:
                        break
                    pos = link.template_text.rfind(link.reserva, 0, pos)
            except COM_ERROR:
                continue
        indice.esquecer()

    def _isolar_restantes(self, sel, indice: _IndiceTextos, links: Dict[str, TextLink], folha: str) -> None:
        """Rede de seguranca: texto colado com vinculo que a leitura do template nao reconheceu.

        O Background acabou de vir do template: um texto com vinculo que nao e um dos refeitos aqui so
        pode estar ligado ao arquivo do template. Fica o valor que ele mostra, sem vinculo, e o aviso.
        """
        refeitos = {position_key(l.x, l.y) for l in links.values()}
        sobras = []
        for t in list(indice.todos()):
            n = _ler(t, "NbLink")
            if not n:
                continue  # sem vinculo, ou a versao do CATIA nao informa: fica como esta
            try:
                if position_key(t.x, t.y) not in refeitos:
                    sobras.append(t)
            except COM_ERROR:
                continue
        for t in sobras:
            nome = _ler(t, "Name") or "?"
            try:
                recriar_texto(sel, indice.vista, t, str(t.Text))
                self.report.warnings.append(
                    f"Folha {folha}: o texto {nome} estava ligado ao template e ficou sem vínculo. Confira se ele "
                    "deveria mostrar um parâmetro do desenho."
                )
            except COM_ERROR:
                self.report.warnings.append(f"Folha {folha}: o texto {nome} continua ligado ao template (Edit > Links > Isolate).")
        if sobras:
            indice.esquecer()

    def _numerar_folha(self, sel, indice, vista_principal, link, prefixos, numero, nome) -> None:
        """Folhas 2 em diante: o numero fica sem vinculo, para nenhum Update voltar a mostrar o total."""
        campo = indice.localizar(link.nome, link.x, link.y)
        if campo is None:
            self.report.warnings.append(f"Folha {numero} ({nome}): campo SHEET/OF não encontrado, número não atualizado.")
            return
        for x, y in prefixos:
            t = indice.posicoes().get(position_key(x, y))
            if t is not None:
                try:
                    _apagar(sel, t)
                except COM_ERROR:
                    pass
        if has_working_sheet_number(vista_principal, link.x, link.y):
            # O desenho ja tem o numero na Main View: fica so ele, e o total do Background sai.
            try:
                _apagar(sel, campo)
            except COM_ERROR:
                self.report.warnings.append(f"Folha {numero} ({nome}): não foi possível apagar o total do campo SHEET/OF.")
        else:
            try:
                # Recriado: so trocar o Text deixava o vinculo do template, e a folha mostrava "2 XX".
                campo = recriar_texto(sel, indice.vista, campo, str(numero))
                indice.esquecer()
                gravou = str(campo.Text) == str(numero)
            except COM_ERROR:
                gravou = False
            if not gravou:
                self.report.warnings.append(f"Folha {numero} ({nome}): não foi possível gravar o número da folha.")

    def _apagar_views_auxiliares(self, sel, folha) -> None:
        vistas = [folha.Views.Item(i) for i in range(3, folha.Views.Count + 1)]
        antigas = [v for v in vistas if is_aux_view(str(v.Name))]
        if not antigas:
            return
        # O CATIA nao apaga view travada, e a ZONE do template antigo vem travada.
        for v in antigas:
            try:
                v.LockStatus = False
            except COM_ERROR:
                pass
        sel.Clear()
        for v in antigas:
            try:
                sel.Add(v)
            except COM_ERROR:
                pass
        if sel.Count == 0:
            return
        # Se algum elemento impedir o Delete em lote, apaga um a um.
        try:
            sel.Delete()
        except COM_ERROR:
            for v in antigas:
                try:
                    _apagar(sel, v)
                except COM_ERROR:
                    pass
        sel.Clear()

    def finalizar(self, folhas: List[dict]) -> None:
        # O campo SHEET/OF da folha 1 fica ligado a No_of_Sheets e passa a mostrar 1/<total>.
        try:
            self.doc.Parameters.Item(SHEET_COUNT_PARAMETER).ValuateFromString(str(len(folhas)))
        except COM_ERROR:
            self.report.warnings.append(f"Parâmetro {SHEET_COUNT_PARAMETER} não encontrado ou não editável.")
        # Colar no Background deixa cada folha em edicao do Background. Da ultima para a primeira,
        # para a folha 1 terminar ativa. As views nao sao atualizadas: troca-se somente o formato.
        for f in reversed(folhas):
            try:
                f["objeto"].Activate()
                f["objeto"].Views.Item(1).Activate()
            except COM_ERROR:
                pass

    def restaurar(self, sucesso: bool) -> None:
        """Saida sempre pelo mesmo caminho. Nao pode esconder o erro original."""
        for acao in (
            lambda: setattr(self.app, "RefreshDisplay", True),
            lambda: setattr(self.app, "Interactive", True),
            lambda: setattr(self.app, "DisplayFileAlerts", True),
            lambda: self.doc.Activate(),
            lambda: self.app.ActiveWindow.ActiveViewer.Update() if sucesso else None,
            lambda: self.doc.Selection.Clear(),
            lambda: setattr(self.app, "StatusBar", ""),
        ):
            try:
                acao()
            except COM_ERROR:
                pass


@dataclass
class TemplatePreview:
    """O que a conversao faria, sem alterar nada no desenho."""

    doc_name: str
    sheets: List[Tuple[str, str]]  # nome da folha, formato lido ("" se nao achou)
    faltando: List[str]  # formatos sem template na pasta
    encontrados: List[str]
    pasta_ok: bool = True


def preview_update(bridge: CatiaBridge, pasta: str = PASTA_TEMPLATES) -> Optional[TemplatePreview]:
    """Le as folhas e procura os templates. Devolve None se nao houver desenho ativo."""
    app = bridge.app
    try:
        if app.Documents.Count == 0:
            return None
        doc = app.ActiveDocument
        if not eh_desenho(doc):
            return None
        folhas = [(str(f.Name), format_from_background(f)) for f in drawing_sheets(doc)]
        nome = str(doc.Name)
    except COM_ERROR:
        return None
    previa = TemplatePreview(nome, folhas, [], [])
    for formato in dict.fromkeys(f for _, f in folhas if f):
        try:
            (previa.encontrados if find_template(pasta, formato) else previa.faltando).append(formato)
        except OSError:
            previa.pasta_ok = False
            previa.faltando.append(formato)
    return previa


def run_update_template(
    bridge: CatiaBridge,
    ask_format: Callable[[str, str, str], Optional[str]],
    status: Optional[Callable[[str], None]] = None,
    progress: Optional[Callable[[int, int], None]] = None,
    pasta: str = PASTA_TEMPLATES,
    formatos: Optional[Dict[str, str]] = None,
) -> Optional[TemplateReport]:
    """Atualiza o template do desenho ativo. Retorna None se o usuario cancelar o pedido de formato.

    formatos: folha -> formato, para as folhas em que o usuario corrigiu o formato na tela.
    """
    c = _Conversao(bridge, status, progress)
    app = bridge.app
    try:
        if app.Documents.Count == 0:
            raise TemplateError("Nenhum documento aberto.", VB_OBJECT_ERROR + 1001)
        doc = app.ActiveDocument
        if not eh_desenho(doc):
            raise TemplateError("O documento ativo não é um CATDrawing.", VB_OBJECT_ERROR + 1002)
        c.doc = doc
        folhas_doc = drawing_sheets(doc)
        if not folhas_doc:
            raise TemplateError("O documento não possui folhas de desenho.", VB_OBJECT_ERROR + 1003)
        doc_cheio = doc.FullName
        lidas = []
        for f in folhas_doc:
            nome = str(f.Name)
            lidas.append((f, nome, (formatos or {}).get(nome) or format_from_background(f)))
    except COM_ERROR as exc:
        raise TemplateError(_descricao_com(exc), exc.hresult) from exc
    except TemplateError:
        for acao in (lambda: setattr(app, "Interactive", True), lambda: setattr(app, "DisplayFileAlerts", True)):
            try:
                acao()
            except COM_ERROR:
                pass
        raise

    try:
        padrao = lidas[0][2]
        if not is_valid_format(padrao):
            padrao = normalize_format(ask_format(PERGUNTA_FORMATO, TITULO_PEDIDO, FORMATO_SUGERIDO) or "")
            if not padrao:
                c.restaurar(True)
                return None
            if not is_valid_format(padrao):
                raise TemplateError(
                    f"Formato inválido: {padrao}\r\n\r\nUtilize somente 3A0, A0, A1, A2, A3 ou E3.",
                    VB_OBJECT_ERROR + 1004,
                )
        padrao = normalize_format(padrao)

        # O formato de cada folha e os templates sao resolvidos antes de qualquer alteracao.
        report = TemplateReport(doc_cheio)
        c.report = report
        templates: Dict[str, str] = {}
        grupos: Dict[str, List[dict]] = {}
        folhas = []
        for pos, (objeto, nome, lido) in enumerate(lidas, 1):
            formato = lido
            if not is_valid_format(formato):
                formato = padrao
                if pos > 1:
                    report.warnings.append(f"Folha {pos} ({nome}): formato não identificado, usado {formato}.")
            formato = normalize_format(formato)
            report.sheets.append((nome, formato))
            folha = {"nome": nome, "objeto": objeto, "posicao": pos}
            folhas.append(folha)
            grupos.setdefault(formato, []).append(folha)
            if formato not in templates:
                templates[formato] = _localizar(pasta, formato)

        app.DisplayFileAlerts = False
        app.Interactive = False
        # Redesenhar a tela a cada comando deixa a conversao duas vezes mais lenta.
        app.RefreshDisplay = False
        # Cada template e aberto uma unica vez.
        for formato, caminho in templates.items():
            c.aplicar_template(caminho, grupos[formato], folhas)
        if status:
            status("Atualizando a numeração das folhas")
        with c.fase("Ativar as folhas no fim"):
            c.finalizar(folhas)
    except TemplateError as exc:
        exc.modified = exc.modified or c.modified
        c.restaurar(False)
        raise
    except COM_ERROR as exc:
        c.restaurar(False)
        raise TemplateError(_descricao_com(exc), exc.hresult, modified=c.modified) from exc
    except Exception:
        # Qualquer outro erro tambem nao pode deixar o CATIA sem alertas e sem tela.
        c.restaurar(False)
        raise
    with c.fase("Atualizar a tela"):
        c.restaurar(True)
    gravar_tempos(report, c.tempos, time.perf_counter() - c.inicio)
    return report


# ---------------------------------------------------------------------
# Leitura do template guardada entre uma conversao e outra
# ---------------------------------------------------------------------
VERSAO_DO_GUARDADO = 1


def caminho_do_guardado() -> str:
    teste = os.environ.get("E1DWGTOOLS_TEMPLATES")
    if teste:
        return teste
    return os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "E1DWGTools", "templates_lidos.json")


def _assinatura_do_arquivo(caminho: str) -> Optional[list]:
    try:
        st = os.stat(caminho)
    except OSError:
        return None
    return [VERSAO_DO_GUARDADO, st.st_size, st.st_mtime_ns]


def ler_template_guardado(caminho: str):
    """(links, margem) se o arquivo do template e o mesmo da ultima leitura. Senao, None."""
    assinatura = _assinatura_do_arquivo(caminho)
    if assinatura is None:
        return None
    try:
        with open(caminho_do_guardado(), encoding="utf-8") as f:
            item = json.load(f).get(caminho.lower())
        if not item or item["assinatura"] != assinatura:
            return None
        links = {chave: TextLink(**valor) for chave, valor in item["links"].items()}
        margem = [(float(x), float(y), int(c)) for x, y, c in item["margem"]]
        return links, margem
    except (OSError, ValueError, KeyError, TypeError):
        return None  # guardado ilegivel: le o template de novo


def guardar_template(caminho: str, links: Dict[str, TextLink], margem) -> None:
    assinatura = _assinatura_do_arquivo(caminho)
    if assinatura is None:
        return
    destino = caminho_do_guardado()
    try:
        try:
            with open(destino, encoding="utf-8") as f:
                tudo = json.load(f)
        except (OSError, ValueError):
            tudo = {}
        tudo[caminho.lower()] = {
            "assinatura": assinatura,
            "links": {chave: asdict(link) for chave, link in links.items()},
            "margem": [list(m) for m in margem],
        }
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        with open(destino, "w", encoding="utf-8") as f:
            json.dump(tudo, f)
    except OSError:
        pass  # sem guardar, a proxima conversao so le o template de novo


def caminho_dos_tempos() -> str:
    teste = os.environ.get("E1DWGTOOLS_TEMPOS")
    if teste:
        return teste
    return os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "E1DWGTools", "update_tempos.txt")


def gravar_tempos(report, tempos: Dict[str, float], total: float) -> None:
    """Diagnostico da lentidao: quanto cada fase levou na ultima conversao. Nao aparece na tela."""
    linhas = [f"Update Template: {len(report.sheets)} folha(s), formatos {', '.join(sorted({f for _, f in report.sheets}))}"]
    for nome, segundos in sorted(tempos.items(), key=lambda par: -par[1]):
        linhas.append(f"{segundos:8.1f} s  {nome}")
    linhas.append(f"{max(total - sum(tempos.values()), 0.0):8.1f} s  Resto (ler o desenho e achar os templates)")
    linhas.append(f"{total:8.1f} s  TOTAL")
    try:
        caminho = caminho_dos_tempos()
        os.makedirs(os.path.dirname(caminho), exist_ok=True)
        with open(caminho, "w", encoding="utf-8") as f:
            f.write("\n".join(linhas) + "\n")
    except OSError:
        pass  # o diagnostico nunca pode atrapalhar a conversao


def _localizar(pasta: str, formato: str) -> str:
    pesquisada = pasta if pasta.endswith("\\") else pasta + "\\"
    try:
        caminho = find_template(pasta, formato)
    except OSError as exc:
        # Pasta de rede fora do ar. O Dir$ do VBA tambem daria erro aqui.
        raise TemplateError(
            f"Não foi possível ler a pasta dos templates.\r\n\r\nPasta pesquisada:\r\n{pesquisada}\r\n\r\n{exc}",
            76,
        ) from exc
    if not caminho:
        raise TemplateError(
            f"Template não encontrado para o formato {formato}.\r\n\r\nPasta pesquisada:\r\n{pesquisada}",
            VB_OBJECT_ERROR + 1005,
        )
    return caminho
