"""Position and Zone: acha os callouts do desenho, a zona e a quantidade de cada um.

Porte de vba_referencia/poszone (V3.5.1-SEM-PINTURA). A leitura roda dentro do CATIA
(catia_scripts/pos_zone.catvbs); as regras ficam aqui, testaveis sem o CATIA. Nenhum objeto
do desenho e alterado na leitura. A tabela fica no HUB e pode ir para uma copia da planilha de
Callouts. So o mover_balao altera o desenho, quando a pessoa pede.
"""
from __future__ import annotations

import math
import os
import re
import shutil
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from engine.catia_bridge import CatiaBridge, CatiaError, parse_number

SCRIPT = "pos_zone.catvbs"
MACRO_VERSION = "V3.5.1-SEM-PINTURA"
TEMPLATE_PLANILHA = "\\\\SJKFS17\\Mezcal\\Projects\\OEM\\EMB170-190\\05. Quality\\09. Macros\\_Callouts.xlsm"
TITULO = "Callout Check"

CALLOUT_FRAME_NONE = 0
CALLOUT_FRAME_CIRCLE = 3
CALLOUT_FRAME_LEGACY_53 = 53
STATUS_IGNORE, STATUS_ACCEPTED, STATUS_PENDING_GROUP, STATUS_PENDING_CONFLICT = range(4)
SOURCE_BALLOON, SOURCE_UNDERLINED, SOURCE_MULTILINE = 1, 2, 3

REF_TOL = 35.0  # distancia na folha entre o REF e o callout
QTY_TOL = 70.0  # distancia na folha entre o texto de quantidade e o callout
QTY_LINE_SLACK_RATIO = 0.5
QTY_LINE_DEFAULT = 5.0
BRACKET_VERTICAL_TOL = 0.05
BRACKET_GAP_RATIO = 2.0
BRACKET_END_SLACK_RATIO = 0.25
ZONE_MIN_ROWS = 2
ZONE_MIN_COLS = 3
ZONE_EDGE_RATIO = 0.12
ZONE_EDGE_MIN = 15.0
ZONE_EDGE_MAX = 80.0
ZONE_SPACING_ERROR_MAX = 0.25
CLUSTER_LINK_FACTOR = 4.5
CLUSTER_LINK_DEFAULT = 20.0
TEXT_WIDTH_RATIO = 0.8
TEXT_LINE_SPACING = 1.5
INFINITO = 1e99
MOTIVO_GRUPO = "Grupo ou ambíguo"
MOTIVO_CONFLITO = "Inconsistência de frame"
MAIOR_LONG = 2147483647

_ESPACOS_VBA = " "  # Trim do VBA tira so espacos


def trim(s: str) -> str:
    return s.strip(_ESPACOS_VBA)


# ---------------------------------------------------------------------
# Palavras-chave: REF precisa ser palavra isolada e a quantidade e o numero colado na palavra.
# ---------------------------------------------------------------------
_RE_REF = re.compile(r"(^|[^A-Z])REF([^A-Z]|\Z)", re.I | re.A)
_RE_QTD_ANTES = re.compile(r"\(?(\d+)\)?\s*X?\s*(PLCS|PLACES|PLS|PL|REQUIRED|REQ'D|REQD)([^A-Z]|\Z)", re.I | re.A)
_RE_QTD_DEPOIS = re.compile(r"(^|[^A-Z])(REQUIRED|REQ'D|REQD)\s*[:=]?\s*(\d+)", re.I | re.A)


def has_ref(s: str) -> bool:
    return _RE_REF.search(s) is not None


def extract_quantity(s: str) -> int:
    m = _RE_QTD_ANTES.search(s)
    numero = m.group(1) if m else None
    if numero is None:
        m = _RE_QTD_DEPOIS.search(s)
        numero = m.group(3) if m else None
    if numero is None:
        return 0
    valor = int(numero)
    return 0 if valor > MAIOR_LONG else valor  # CLng estouraria, e o VBA considera 0


def only_digits(s: str) -> bool:
    s = trim(s)
    return bool(s) and all("0" <= c <= "9" for c in s)


def normalize_callout(s: str) -> str:
    s = trim(s)
    if not only_digits(s):
        return s
    while len(s) > 1 and s[0] == "0":
        s = s[1:]
    return s


def non_empty_lines(s: str) -> List[str]:
    s = s.replace("\r\n", "\n").replace("\r", "\n").replace("\t", " ").replace("\xa0", " ")
    return [linha for linha in (trim(p) for p in s.split("\n")) if linha]


def count_callout_lines(linhas: List[str]) -> Tuple[int, str]:
    numeros = [l for l in linhas if only_digits(l)]
    return len(numeros), (numeros[0] if numeros else "")


def is_aux_view(nome: str) -> bool:
    s = trim(nome).upper()
    return s == "ZONE" or s.startswith("ZONE[") or s.startswith("ZONES_A1_SHT")


def is_zone_letter(s: str) -> bool:
    s = trim(s).upper()
    return len(s) == 1 and "A" <= s <= "F"


def is_zone_number(s: str) -> bool:
    if not only_digits(s) or len(trim(s)) > 3:
        return False
    return 0 < int(trim(s)) <= 999


def limit(v: float, minimo: float, maximo: float) -> float:
    return max(minimo, min(maximo, v))


def distance(x1: float, y1: float, x2: float, y2: float) -> float:
    return math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)


def add_unique(lista: str, novo: str) -> str:
    lista, novo = trim(lista), trim(novo)
    if not novo:
        return lista
    if not lista:
        return novo
    if any(trim(p).lower() == novo.lower() for p in lista.split(";")):
        return lista
    return f"{lista}; {novo}"


def _sgn(v: float) -> int:
    return (v > 0) - (v < 0)


# ---------------------------------------------------------------------
# O que o script le do CATIA
# ---------------------------------------------------------------------
@dataclass
class TextRead:
    index: int
    text: str
    x: float
    y: float
    font: float
    anchor: int
    frame_ok: bool
    frame: int
    underline: bool
    inner_ok: bool
    inner: int
    name: str = ""


@dataclass
class ViewRead:
    index: int
    name: str
    is_background: bool
    x: float
    y: float
    scale: float
    angle: float
    texts: List[TextRead] = field(default_factory=list)

    def to_sheet(self, px: float, py: float) -> Tuple[float, float]:
        """Ponto da vista para mm de papel na folha."""
        if abs(self.angle) > 0.001:
            c, s = math.cos(self.angle), math.sin(self.angle)
            return (
                self.x + px * self.scale * c - py * self.scale * s,
                self.y + px * self.scale * s + py * self.scale * c,
            )
        return self.x + px * self.scale, self.y + py * self.scale

    def delta_to_view(self, dx: float, dy: float) -> Tuple[float, float]:
        """Deslocamento em mm de papel na folha para o mesmo deslocamento na vista."""
        if abs(self.angle) > 0.001:
            c, s = math.cos(self.angle), math.sin(self.angle)
            return (dx * c + dy * s) / self.scale, (-dx * s + dy * c) / self.scale
        return dx / self.scale, dy / self.scale


@dataclass
class SheetRead:
    name: str
    is_detail: bool
    width: float
    height: float
    views: List[ViewRead] = field(default_factory=list)


def parse_sheet(registros: List[List[str]]) -> SheetRead:
    folha = None
    vista = None
    for r in registros:
        if r[0] == "F":
            folha = SheetRead(r[1], r[2] == "1", parse_number(r[3]) if r[3] else 0.0, parse_number(r[4]) if r[4] else 0.0)
        elif r[0] == "V":
            vista = ViewRead(int(r[1]), r[2], r[3] == "1", parse_number(r[4]), parse_number(r[5]), parse_number(r[6]), parse_number(r[7]))
            folha.views.append(vista)
        elif r[0] == "T":
            vista.texts.append(TextRead(
                int(r[2]), r[3], parse_number(r[4]), parse_number(r[5]), parse_number(r[6]), int(r[7]),
                r[8] == "1", int(r[9]), r[10] == "1", r[11] == "1", int(r[12]), r[13] if len(r) > 13 else "",
            ))
    return folha


# ---------------------------------------------------------------------
# Zonas
# ---------------------------------------------------------------------
@dataclass
class Zone:
    name: str
    x: float
    y: float


def _sequence(candidatos: List[tuple], alpha: bool) -> Tuple[List[tuple], float, bool]:
    """Maior sequencia de rotulos consecutivos com espacamento regular. (rotulo, valor, posicao)"""
    if not candidatos:
        return [], -INFINITO, False
    a = _sort_by_position(candidatos)
    minimo = ZONE_MIN_ROWS if alpha else ZONE_MIN_COLS
    melhor_score, melhor = -INFINITO, None
    erro = 0.0  # a macro nao zera o erro medio entre as tentativas, e ele desempata as sequencias
    for s in range(len(a)):
        for e in range(s, len(a)):
            cnt = e - s + 1
            if cnt >= minimo and _consecutive(a, s, e):
                ok, erro = _spacing(a, s, e, erro)
                if ok:
                    score = cnt * 1000.0 - erro * 100.0
                    if score > melhor_score:
                        melhor_score, melhor = score, (s, e)
    if melhor is None:
        return [], melhor_score, False
    return a[melhor[0]:melhor[1] + 1], melhor_score, True


def _sort_by_position(candidatos: List[tuple]) -> List[tuple]:
    # A mesma troca do VBA, que nao e estavel: empates de posicao ficam na mesma ordem dele.
    a = list(candidatos)
    for i in range(len(a) - 1):
        for j in range(i + 1, len(a)):
            if a[j][2] < a[i][2]:
                a[i], a[j] = a[j], a[i]
    return a


def _consecutive(a: List[tuple], s: int, e: int) -> bool:
    if e <= s:
        return False
    direcao = a[s + 1][1] - a[s][1]
    if abs(direcao) != 1:
        return False
    return all(a[i + 1][1] - a[i][1] == direcao for i in range(s, e))


def _spacing(a: List[tuple], s: int, e: int, erro_medio: float) -> Tuple[bool, float]:
    intervalos = e - s
    if intervalos <= 0:
        return False, erro_medio
    total = 0.0
    for i in range(s, e):
        d = abs(a[i + 1][2] - a[i][2])
        if d <= 0.001:
            return False, erro_medio
        total += d
    media = total / intervalos
    erro_max = 0.0
    for i in range(s, e):
        er = abs(abs(a[i + 1][2] - a[i][2]) - media) / media
        erro_medio += er
        erro_max = max(erro_max, er)
    return erro_max <= ZONE_SPACING_ERROR_MAX, erro_medio / intervalos


def zone_column(coluna: int, numero_folha: int) -> int:
    """O carimbo repete as colunas 1, 2, 3...; na zona, a folha entra na dezena."""
    return coluna if numero_folha <= 1 else numero_folha * 10 + coluna


def zones_from_border(folha: SheetRead, numero_folha: int) -> List[Zone]:
    if folha.width <= 0 or folha.height <= 0:
        return []
    fundo = next((v for v in folha.views if v.is_background), None)
    if fundo is None:
        return []
    faixa_x = limit(folha.width * ZONE_EDGE_RATIO, ZONE_EDGE_MIN, ZONE_EDGE_MAX)
    faixa_y = limit(folha.height * ZONE_EDGE_RATIO, ZONE_EDGE_MIN, ZONE_EDGE_MAX)
    esq, dir_, topo, base = [], [], [], []
    for t in fundo.texts:
        valor = trim(t.text).upper()
        letra, numero = is_zone_letter(valor), is_zone_number(valor)
        if not (letra or numero):
            continue
        x, y = fundo.to_sheet(t.x, t.y)
        if letra:
            if 0 <= x <= faixa_x:
                esq.append((valor, ord(valor), y))
            if folha.width - faixa_x <= x <= folha.width:
                dir_.append((valor, ord(valor), y))
        else:
            n = int(valor)
            if folha.height - faixa_y <= y <= folha.height:
                topo.append((str(n), n, x))
            if 0 <= y <= faixa_y:
                base.append((str(n), n, x))
    m_esq, s_esq, ok_esq = _sequence(esq, True)
    m_dir, s_dir, ok_dir = _sequence(dir_, True)
    m_topo, _, ok_topo = _sequence(topo, False)
    m_base, _, ok_base = _sequence(base, False)
    if not ok_esq and not ok_dir:
        return []
    linhas = m_esq if ok_esq and (not ok_dir or s_esq >= s_dir) else m_dir
    if ok_base:
        colunas = m_base
    elif ok_topo:
        colunas = m_topo
    else:
        return []
    if len(linhas) < ZONE_MIN_ROWS or len(colunas) < ZONE_MIN_COLS:
        return []
    return [
        Zone(f"{r[0].upper()}{zone_column(c[1], numero_folha):03d}", c[2], r[2])
        for r in linhas for c in colunas
    ]


def normalize_aux_zone(s: str) -> str:
    s = trim(s).upper()
    if not 2 <= len(s) <= 4:
        return ""
    if not is_zone_letter(s[0]) or not only_digits(s[1:]):
        return ""
    n = int(trim(s[1:]))
    if n <= 0 or n > 999:
        return ""
    return f"{s[0]}{n:03d}"


def zones_from_aux_view(folha: SheetRead) -> List[Zone]:
    for v in folha.views:
        if is_aux_view(v.name):
            zonas = []
            for t in v.texts:
                nome = normalize_aux_zone(t.text)
                if nome:
                    x, y = v.to_sheet(t.x, t.y)
                    zonas.append(Zone(nome, x, y))
            if zonas:
                return zonas
    return []


def map_zones(folha: SheetRead, numero_folha: int) -> List[Zone]:
    return zones_from_border(folha, numero_folha) or zones_from_aux_view(folha)


def nearest_zone(x: float, y: float, zonas: List[Zone]) -> str:
    nome, menor = "N/A", INFINITO
    for z in zonas:
        d = distance(x, y, z.x, z.y)
        if d < menor:
            menor, nome = d, z.name
    return nome


# ---------------------------------------------------------------------
# Classificacao e ocorrencias
# ---------------------------------------------------------------------
def classify(t: TextRead, value: str) -> int:
    s = trim(value)
    if not only_digits(s):
        return STATUS_IGNORE
    circulo = (CALLOUT_FRAME_CIRCLE, CALLOUT_FRAME_LEGACY_53)
    gf = t.frame if t.frame_ok else 0
    inf = t.inner if t.inner_ok else 0
    if t.frame_ok and gf in circulo and len(s) <= 4:
        return STATUS_ACCEPTED
    if t.frame_ok and t.inner_ok:
        if gf == CALLOUT_FRAME_NONE and inf in circulo:
            return STATUS_ACCEPTED if len(s) <= 3 else STATUS_PENDING_GROUP
        if gf not in (CALLOUT_FRAME_NONE,) + circulo and inf in circulo:
            return STATUS_PENDING_CONFLICT
    return STATUS_IGNORE


def text_center(v: ViewRead, t: TextRead) -> Tuple[float, float, float, float, float]:
    """Centro aproximado do bloco de texto na folha: cx, cy, fonte, meia altura, meia largura."""
    ax, ay = v.to_sheet(t.x, t.y)
    if t.font <= 0:
        return ax, ay, 0.0, 0.0, 0.0
    linhas = non_empty_lines(t.text)
    if not linhas:
        return ax, ay, t.font, 0.0, 0.0
    w = max(len(l) for l in linhas) * t.font * TEXT_WIDTH_RATIO
    h = t.font + (len(linhas) - 1) * t.font * TEXT_LINE_SPACING
    cx, cy = ax, ay
    if t.anchor in (1, 2, 3, 11, 12, 13):
        cx = ax + w / 2
    elif t.anchor in (7, 8, 9, 17, 18, 19):
        cx = ax - w / 2
    if t.anchor in (1, 4, 7, 11, 14, 17):
        cy = ay - h / 2
    elif t.anchor in (3, 6, 9, 13, 16, 19):
        cy = ay + h / 2
    return cx, cy, t.font, h / 2, w / 2


@dataclass
class Occurrence:
    number: str
    qty: int
    zone: str
    sheet: str
    view: str
    x: float
    y: float
    source: int
    text_index: int
    is_reference: bool = False
    has_qty: bool = False
    cx: float = 0.0
    cy: float = 0.0
    font: float = 0.0
    half_h: float = 0.0
    half_w: float = 0.0
    cluster: int = 0
    view_index: int = 0
    item_name: str = ""
    underlined: bool = False
    is_dim = False

    # Os nomes que o navegador do CATIA usa.
    @property
    def sheet_name(self) -> str:
        return self.sheet

    @property
    def view_name(self) -> str:
        return self.view

    @property
    def item_index(self) -> int:
        return self.text_index


@dataclass
class Callout:
    number: str
    qty: int
    zone: str
    sheet: str
    view: str


@dataclass
class Pending:
    """Texto que nao entrou na conta por ser ambiguo. Os campos servem ao navegador do CATIA."""

    sheet_name: str
    view_index: int
    view_name: str
    item_index: int
    item_name: str
    number: str
    motivo: str
    is_dim = False


@dataclass
class Counters:
    validos: int = 0
    grupo: int = 0
    conflito: int = 0
    referencias: int = 0
    multilinha: int = 0
    chaves: int = 0


class Analyzer:
    """Processa as folhas na ordem, acumulando as ocorrencias. Mesma sequencia da macro."""

    def __init__(self, carregar_linhas: Callable[[int, int], List[Tuple[float, float, float, float]]]):
        self.carregar_linhas = carregar_linhas
        self.occs: List[Occurrence] = []
        self.c = Counters()
        self.pendencias: List[Pending] = []
        self.folhas: Dict[str, SheetRead] = {}
        self.zonas: Dict[str, List[Zone]] = {}
        self._numero_folha = 0

    def process_sheet(self, indice: int, folha: SheetRead) -> None:
        if not folha.is_detail:
            self._numero_folha += 1
        zonas = map_zones(folha, self._numero_folha)
        self.folhas[folha.name] = folha
        self.zonas[folha.name] = zonas
        for v in folha.views:
            if v.is_background or is_aux_view(v.name):
                continue
            self._process_view(indice, folha, v, zonas)

    def _process_view(self, indice: int, folha: SheetRead, v: ViewRead, zonas: List[Zone]) -> None:
        tem_ref = {t.index: has_ref(t.text) for t in v.texts}
        qtd = {t.index: (0 if tem_ref[t.index] else extract_quantity(t.text)) for t in v.texts}
        inicio = len(self.occs)
        for t in v.texts:
            linhas = non_empty_lines(t.text)
            if linhas and not tem_ref[t.index]:
                n, linha = count_callout_lines(linhas)
                if n == 1 and (len(linhas) == 1 or qtd[t.index] > 0):
                    self._simple(folha, v, t, linha, qtd[t.index], zonas)
                elif n > 0 and len(linhas) > 1:
                    self._multiline(folha, v, t, linhas, qtd[t.index], zonas)
        vista_occs = self.occs[inicio:]
        if vista_occs:
            self._references(v, tem_ref, vista_occs)
            self._quantities(indice, v, tem_ref, qtd, vista_occs)

    def _add(self, v, folha, numero, qty, zona, x, y, source, t) -> Occurrence:
        o = Occurrence(
            numero, qty if qty > 0 else 1, zona, folha.name, v.name, x, y, source, t.index, cx=x, cy=y,
            view_index=v.index, item_name=t.name, underlined=t.underline,
        )
        self.occs.append(o)
        return o

    def _simple(self, folha, v, t, value, qty, zonas) -> None:
        if not only_digits(value):
            return
        status = classify(t, value)
        if status == STATUS_PENDING_GROUP:
            self.c.grupo += 1
            self.pendencias.append(Pending(folha.name, v.index, v.name, t.index, t.name, trim(value), MOTIVO_GRUPO))
            return
        if status == STATUS_PENDING_CONFLICT:
            self.c.conflito += 1
            self.pendencias.append(Pending(folha.name, v.index, v.name, t.index, t.name, trim(value), MOTIVO_CONFLITO))
            return
        if status == STATUS_ACCEPTED:
            source = SOURCE_BALLOON
        elif t.underline:
            source = SOURCE_UNDERLINED
        else:
            return
        x, y = v.to_sheet(t.x, t.y)
        o = self._add(v, folha, normalize_callout(value), qty, nearest_zone(x, y, zonas), x, y, source, t)
        o.cx, o.cy, o.font, o.half_h, o.half_w = text_center(v, t)
        if qty > 0:
            o.has_qty = True
        self.c.validos += 1

    def _multiline(self, folha, v, t, linhas, qty, zonas) -> None:
        if not t.underline:
            return
        x, y = v.to_sheet(t.x, t.y)
        achou = False
        for i, linha in enumerate(linhas):
            numero = trim(linha)
            if only_digits(numero):
                o = self._add(v, folha, normalize_callout(numero), qty, nearest_zone(x, y, zonas), x, y, SOURCE_MULTILINE, t)
                o.cx, o.cy, o.font, o.half_h, o.half_w = text_center(v, t)
                # Cada linha fica na sua altura, para o "2 PL" ao lado ir para a linha certa.
                if o.font > 0:
                    o.cy = o.cy + o.half_h - o.font / 2 - i * o.font * TEXT_LINE_SPACING
                    o.half_h = o.font / 2
                if qty > 0:
                    o.has_qty = True
                self.c.multilinha += 1
                achou = True
        if achou:
            self.c.validos += 1

    def _references(self, v, tem_ref, occs) -> None:
        for t in v.texts:
            if tem_ref[t.index]:
                x, y = v.to_sheet(t.x, t.y)
                for o in occs:
                    if not o.is_reference and o.source in (SOURCE_UNDERLINED, SOURCE_MULTILINE):
                        if distance(x, y, o.x, o.y) <= REF_TOL:
                            o.is_reference = True
                            self.c.referencias += 1

    # ---- quantidades ----
    def _quantities(self, indice, v, tem_ref, qtd, occs) -> None:
        self._chaves = None
        tamanhos = _group_balloons(occs)
        qtd_aglomerado = {}
        capturado = {o.text_index for o in occs}
        for t in v.texts:
            q = 0 if (t.index in capturado or tem_ref[t.index]) else qtd[t.index]
            if q <= 0:
                continue
            cx, cy, fs, hh, hw = text_center(v, t)
            melhor = _nearest(cx, cy, QTY_TOL, occs)
            if melhor is not None and _is_cluster_qty(melhor, cx, cy, tamanhos):
                # Quantidade embaixo do ultimo balao do aglomerado: vale para todos.
                qtd_aglomerado[melhor.cluster] = q
            elif self._apply_bracket(indice, v, cx, cy, hw, fs, q, occs):
                # Linha vertical englobando 2 ou mais callouts: a quantidade vale para todos eles.
                self.c.chaves += 1
            else:
                # Ao lado: so para o callout na mesma linha. Se for REF, a quantidade e descartada.
                melhor = _same_line(cx, cy, hh, fs, QTY_TOL, occs)
                if melhor is not None and not melhor.is_reference:
                    melhor.qty = q
                    melhor.has_qty = True
        # Quantidade do aglomerado multiplica a individual: "2 PL" do grupo + "2 PL" do balao = 4.
        for o in occs:
            if _is_balloon(o) and o.cluster > 0 and qtd_aglomerado.get(o.cluster, 0) > 0:
                o.qty = o.qty * qtd_aglomerado[o.cluster] if o.has_qty else qtd_aglomerado[o.cluster]
                o.has_qty = True

    def _load_brackets(self, indice, v) -> list:
        if self._chaves is None:
            self._chaves = []
            for x1p, y1p, x2p, y2p in self.carregar_linhas(indice, v.index):
                x1, y1 = v.to_sheet(x1p, y1p)
                x2, y2 = v.to_sheet(x2p, y2p)
                comprimento = abs(y1 - y2)
                if comprimento > 0.001 and abs(x1 - x2) <= comprimento * BRACKET_VERTICAL_TOL:
                    self._chaves.append(((x1 + x2) / 2, min(y1, y2), max(y1, y2)))
        return self._chaves

    def _apply_bracket(self, indice, v, x, y, half_w, fs, qty, occs) -> bool:
        if fs <= 0:
            return False
        chaves = self._load_brackets(indice, v)
        if not chaves:
            return False
        folga = fs * BRACKET_END_SLACK_RATIO
        melhor, melhor_gap = None, INFINITO
        for k in chaves:
            if k[1] - folga <= y <= k[2] + folga:
                gap = abs(x - k[0]) - half_w
                if -folga <= gap <= fs * BRACKET_GAP_RATIO and gap < melhor_gap:
                    if _bracket_callouts(k, x, fs, 0, occs) >= 2:
                        melhor, melhor_gap = k, gap
        if melhor is None:
            return False
        _bracket_callouts(melhor, x, fs, qty, occs)
        return True


def _is_balloon(o: Occurrence) -> bool:
    return o.source == SOURCE_BALLOON and not o.is_reference


def _group_balloons(occs: List[Occurrence]) -> dict:
    """Baloes empilhados na vertical formam um aglomerado. Devolve aglomerado -> quantos baloes."""
    grupo = [i if _is_balloon(o) else -1 for i, o in enumerate(occs)]
    for i, a in enumerate(occs):
        if grupo[i] < 0:
            continue
        for j in range(i + 1, len(occs)):
            b = occs[j]
            if grupo[j] >= 0 and grupo[j] != grupo[i]:
                fs = max(a.font, b.font)
                limite = fs * CLUSTER_LINK_FACTOR if fs > 0 else CLUSTER_LINK_DEFAULT
                if distance(a.cx, a.cy, b.cx, b.cy) <= limite and abs(a.cy - b.cy) > abs(a.cx - b.cx):
                    velho, novo = grupo[j], grupo[i]
                    grupo = [novo if g == velho else g for g in grupo]
    mapa, tamanhos = {}, {}
    for i, o in enumerate(occs):
        if grupo[i] >= 0:
            if grupo[i] not in mapa:
                mapa[grupo[i]] = len(mapa) + 1
            o.cluster = mapa[grupo[i]]
            tamanhos[o.cluster] = tamanhos.get(o.cluster, 0) + 1
        else:
            o.cluster = 0
    return tamanhos


def _is_cluster_qty(o: Occurrence, cx: float, cy: float, tamanhos: dict) -> bool:
    if o.source != SOURCE_BALLOON or o.cluster <= 0 or tamanhos.get(o.cluster, 0) < 2:
        return False
    return (o.cy - cy) > abs(cx - o.cx)


def _nearest(x: float, y: float, maximo: float, occs: List[Occurrence]) -> Optional[Occurrence]:
    melhor, menor = None, INFINITO
    for o in occs:
        if not o.is_reference:
            d = distance(x, y, o.cx, o.cy)
            if d <= maximo and d < menor:
                menor, melhor = d, o
    return melhor


def _same_line(x, y, half_h, fs, max_dx, occs) -> Optional[Occurrence]:
    melhor, min_dx, min_dy = None, INFINITO, INFINITO
    for o in occs:
        if o.has_qty:
            continue
        dx, dy = abs(x - o.cx), abs(y - o.cy)
        f = max(fs, o.font)
        tol = QTY_LINE_DEFAULT if f <= 0 else half_h + o.half_h + f * QTY_LINE_SLACK_RATIO
        if dx <= max_dx and dy <= tol:
            if dx < min_dx - 0.001 or (abs(dx - min_dx) <= 0.001 and dy < min_dy):
                min_dx, min_dy, melhor = dx, dy, o
    return melhor


def _bracket_callouts(k, x_qtd, fs_qtd, qty, occs) -> int:
    """Callouts do outro lado da chave. qty = 0 so conta; qty > 0 tambem aplica."""
    lado = _sgn(x_qtd - k[0])
    total = 0
    for o in occs:
        if o.is_reference:
            continue
        fs = max(fs_qtd, o.font)
        if (
            _sgn(o.cx - k[0]) == -lado
            and abs(o.cx - k[0]) - o.half_w <= fs * BRACKET_GAP_RATIO
            and k[1] - fs * BRACKET_END_SLACK_RATIO <= o.cy <= k[2] + fs * BRACKET_END_SLACK_RATIO
        ):
            total += 1
            if qty > 0:
                o.qty = o.qty * qty if o.has_qty else qty
                o.has_qty = True
    return total


def consolidate(occs: List[Occurrence]) -> List[Callout]:
    saida: List[Callout] = []
    por_numero = {}
    # A zona vem do balao sem sublinhado. O sublinhado so conta a quantidade. Um balao que tambem
    # esta sublinhado so da a zona se a posicao nao tiver outro balao.
    com_balao_limpo = {
        o.number.lower() for o in occs if not o.is_reference and o.source == SOURCE_BALLOON and not o.underlined
    }

    def da_zona(o: Occurrence) -> bool:
        return o.source == SOURCE_BALLOON and (not o.underlined or o.number.lower() not in com_balao_limpo)

    for o in occs:
        if o.is_reference:
            continue
        zona = o.zone if da_zona(o) else ""
        c = por_numero.get(o.number.lower())
        if c is None:
            c = Callout(o.number, o.qty, zona, o.sheet, o.view)
            por_numero[o.number.lower()] = c
            saida.append(c)
        else:
            c.qty += o.qty
            if da_zona(o) and trim(o.zone) and trim(o.zone).lower() != "n/a":
                c.zone = add_unique(c.zone, o.zone)
            c.sheet = add_unique(c.sheet, o.sheet)
            c.view = add_unique(c.view, o.view)
    return saida


# ---------------------------------------------------------------------
# Planilha
# ---------------------------------------------------------------------
def clean_file_name(s: str) -> str:
    s = trim(s)
    for ch in ("\\", "/", ":", "*", "?", '"', "<", ">", "|"):
        s = s.replace(ch, "_")
    return s or "Drawing"


def output_path(pasta: str, nome: str, carimbo: str) -> str:
    caminho = f"{pasta}{nome}_Callouts_{carimbo}.xlsm"
    i = 1
    while os.path.exists(caminho):
        caminho = f"{pasta}{nome}_Callouts_{carimbo}_{i:03d}.xlsm"
        i += 1
    return caminho


def temp_folder() -> str:
    pasta = trim(os.environ.get("TEMP", "")) or trim(os.environ.get("TMP", "")) or "C:\\Temp"
    return pasta if pasta.endswith("\\") else pasta + "\\"


def rgb(r: int, g: int, b: int) -> int:
    return r + g * 256 + b * 65536


def write_workbook(caminho: str, pn: str, callouts: List[Callout]):
    """Abre a copia no Excel e grava a tabela. Devolve (Excel, pasta). Quem chama nao fecha."""
    import win32com.client

    xl = win32com.client.DispatchEx("Excel.Application")
    xl.Visible = True
    xl.DisplayAlerts = True
    wb = xl.Workbooks.Open(Filename=caminho, UpdateLinks=False, ReadOnly=True)
    try:
        ws = wb.Worksheets("Dados_Callouts")
    except Exception as exc:
        raise PosZoneError(f"Não foi possível abrir ou preparar a cópia:\r\n{caminho}\r\nA planilha Dados_Callouts não foi encontrada.") from exc
    ultima = ws.Cells(ws.Rows.Count, 1).End(-4162).Row
    if ultima >= 4:
        r = ws.Range(f"A4:D{ultima}")
        r.ClearContents()
        r.Interior.Pattern = -4142
        r.Font.Color = rgb(0, 0, 0)
    a1 = ws.Range("A1")
    a1.Value = f"PN: {pn}"
    a1.Font.Name = "Segoe UI"
    a1.Font.Size = 14
    a1.Font.Bold = True
    a1.Font.Color = rgb(255, 255, 255)
    a1.HorizontalAlignment = -4108
    a1.VerticalAlignment = -4108
    xl.ScreenUpdating = False
    if callouts:
        fim = len(callouts) + 3
        dados = tuple(
            (float(c.number) if only_digits(c.number) else c.number, c.zone, c.qty, f"{c.sheet} - {c.view}")
            for c in callouts
        )
        r = ws.Range(f"A4:D{fim}")
        r.Value = dados
        r.Font.Name = "Segoe UI"
        r.Font.Size = 10
        r.Borders.LineStyle = 1
        r.Borders.Color = rgb(217, 217, 217)
        ws.Range(f"A4:C{fim}").HorizontalAlignment = -4108
        # Pelo objeto Sort: em Range.Sort, por nome ou por posicao, o Header nao chega por COM e o
        # cabecalho seria ordenado junto com os dados.
        ordem = ws.Sort
        ordem.SortFields.Clear()
        ordem.SortFields.Add(ws.Range("A4"), 0, 1)  # Key, SortOn = valores, Order = crescente
        ordem.SetRange(ws.Range(f"A3:D{fim}"))
        ordem.Header = 1  # xlYes
        ordem.Apply()
    ws.Columns("A:D").AutoFit()
    xl.ScreenUpdating = True
    wb.Saved = False
    ws.Activate()
    return xl, wb


# ---------------------------------------------------------------------
# Execucao
# ---------------------------------------------------------------------
class PosZoneError(CatiaError):
    @property
    def mensagem(self) -> str:
        return str(self)

    report = None


@dataclass
class PosZoneReport:
    pn: str
    workbook_path: str
    counters: Counters
    occurrences: int
    callouts: List[Callout] = field(default_factory=list)
    pendencias: List[Pending] = field(default_factory=list)
    doc_full_name: str = ""
    xl_app: object = None
    xl_book: object = None
    occs: List[Occurrence] = field(default_factory=list)
    folhas: Dict[str, SheetRead] = field(default_factory=dict)
    zonas: Dict[str, List[Zone]] = field(default_factory=dict)
    abertas: Optional[int] = None  # o que falta revisar na tela; None antes de a tela calcular

    @property
    def mensagem(self) -> str:
        c = self.counters
        return (
            f"Macro {MACRO_VERSION}\r\n"
            f"Processamento concluído para o PN {self.pn}!\r\n\r\n"
            f"Objetos válidos identificados: {c.validos}\r\n"
            f"Linhas multilinha contabilizadas: {c.multilinha}\r\n"
            f"Referências ignoradas por REF: {c.referencias}\r\n"
            f"Quantidades aplicadas por chave (linha vertical): {c.chaves}\r\n"
            f"Agrupados/ambíguos não contabilizados: {c.grupo}\r\n"
            f"Inconsistentes não contabilizados: {c.conflito}\r\n"
            f"Ocorrências válidas encontradas: {self.occurrences - c.referencias}\r\n"
            f"Callouts consolidados no Excel: {len(self.callouts)}"
        )


def _ler_desenho(bridge: CatiaBridge, cheio: str, total: int, progress) -> Analyzer:
    def linhas(i_folha: int, i_vista: int):
        return [
            tuple(parse_number(c) for c in r[1:5])
            for r in bridge.call(SCRIPT, "LerLinhas", cheio, i_folha, i_vista)
        ]

    analise = Analyzer(linhas)
    try:
        bridge.call(SCRIPT, "Tela", False)
        for i in range(1, total + 1):
            analise.process_sheet(i, parse_sheet(bridge.call(SCRIPT, "LerFolha", cheio, i)))
            if progress:
                progress(i, total)
    finally:
        try:
            bridge.call(SCRIPT, "Tela", True)
        except CatiaError:
            pass
    return analise


def _relatorio(pn: str, caminho: str, cheio: str, analise: Analyzer) -> PosZoneReport:
    return PosZoneReport(
        pn, caminho, analise.c, len(analise.occs), consolidate(analise.occs), analise.pendencias, cheio,
        occs=analise.occs, folhas=analise.folhas, zonas=analise.zonas,
    )


def _situacao(bridge: CatiaBridge, warn) -> Optional[Tuple[str, str, int]]:
    situacao = bridge.call(SCRIPT, "LerDesenho")[0]
    if situacao[0] == "0":
        warn("Nenhum Drawing ativo foi encontrado.", TITULO)
        return None
    _, cheio, nome, total = situacao
    return cheio, (nome[: nome.rfind(".")] if nome.rfind(".") > 0 else nome), int(total)


def analisar_desenho(
    bridge: CatiaBridge,
    warn: Callable[[str, str], None],
    progress: Optional[Callable[[int, int], None]] = None,
) -> Optional[PosZoneReport]:
    """Le o desenho ativo. A tabela fica no HUB: nada abre no Excel."""
    lido = _situacao(bridge, warn)
    if lido is None:
        return None
    cheio, pn, total = lido
    report = _relatorio(pn, "", cheio, _ler_desenho(bridge, cheio, total, progress))
    bridge.call(SCRIPT, "RestaurarVistas", cheio)
    return report


def exportar_planilha(report: PosZoneReport, template: str = TEMPLATE_PLANILHA, pasta_saida: Optional[str] = None) -> str:
    """Grava a tabela numa copia da planilha, que fica aberta no Excel. Devolve o caminho."""
    if not os.path.exists(template):
        raise PosZoneError(f"O template não foi encontrado:\r\n\r\n{template}")
    caminho = output_path(pasta_saida or temp_folder(), clean_file_name(report.pn), time.strftime("%Y%m%d_%H%M%S"))
    try:
        shutil.copyfile(template, caminho)
    except OSError as exc:
        raise PosZoneError(f"Não foi possível criar a cópia temporária:\r\n{caminho}\r\n{exc}") from exc
    try:
        write_workbook(caminho, report.pn, report.callouts)
    except PosZoneError:
        raise
    except Exception as exc:  # o Excel pode falhar de muitas formas; a mensagem e a mesma da macro
        raise PosZoneError(f"Não foi possível abrir ou preparar a cópia:\r\n{caminho}\r\n{exc}") from exc
    report.workbook_path = caminho
    return caminho


def run_pos_zone(
    bridge: CatiaBridge,
    warn: Callable[[str, str], None],
    progress: Optional[Callable[[int, int], None]] = None,
    template: str = TEMPLATE_PLANILHA,
    pasta_saida: Optional[str] = None,
) -> Optional[PosZoneReport]:
    """O caminho da macro: le o desenho e grava a tabela numa copia da planilha, aberta no Excel."""
    lido = _situacao(bridge, warn)
    if lido is None:
        return None
    cheio, pn, total = lido
    if not os.path.exists(template):
        warn(f"O template não foi encontrado:\r\n\r\n{template}", "Template não encontrado")
        return None
    caminho = output_path(pasta_saida or temp_folder(), clean_file_name(pn), time.strftime("%Y%m%d_%H%M%S"))
    try:
        shutil.copyfile(template, caminho)
    except OSError as exc:
        raise PosZoneError(f"Não foi possível criar a cópia temporária:\r\n{caminho}\r\n{exc}") from exc
    try:
        analise = _ler_desenho(bridge, cheio, total, progress)
    except CatiaError as exc:
        raise PosZoneError(f"Não foi possível abrir ou preparar a cópia:\r\n{caminho}\r\n{exc}", exc.number) from exc
    report = _relatorio(pn, caminho, cheio, analise)
    try:
        report.xl_app, report.xl_book = write_workbook(caminho, pn, report.callouts)
    except PosZoneError:
        raise
    except Exception as exc:  # o Excel pode falhar de muitas formas; a mensagem e a mesma da macro
        raise PosZoneError(f"Não foi possível abrir ou preparar a cópia:\r\n{caminho}\r\n{exc}") from exc
    bridge.call(SCRIPT, "RestaurarVistas", cheio)
    return report


# ---------------------------------------------------------------------
# Mover um balao para outra zona
# ---------------------------------------------------------------------
TEXTO_COLADO_FOLGA = 0.75  # em alturas de fonte: entre dois textos encostados
TEXTO_COLADO_FOLGA_BALAO = 1.5  # o circulo do balao e maior que o texto dentro dele
TEXTO_COLADO_MAX = 20  # caracteres: uma nota comprida perto do balao nao anda junto
MARGEM_ZONA = 0.8  # fica um pouco para dentro da divisa, e nao em cima dela


@dataclass
class Movimento:
    occ: Occurrence
    zona_antes: str
    zona_depois: str
    # (vista, texto, x antes, y antes, x depois, y depois), em coordenadas da vista
    textos: List[Tuple[ViewRead, TextRead, float, float, float, float]] = field(default_factory=list)
    x_antes: float = 0.0
    y_antes: float = 0.0
    cx_antes: float = 0.0
    cy_antes: float = 0.0


def _eh_balao(t: TextRead) -> bool:
    _, numero = count_callout_lines(non_empty_lines(t.text))
    return bool(numero) and classify(t, numero) != STATUS_IGNORE


def textos_colados(v: ViewRead, t: TextRead) -> List[TextRead]:
    """Flag, quantidade e numero encostados no balao: andam junto, senao ficam para tras."""
    colados: List[TextRead] = []
    fila = [t]
    vistos = {t.index}
    while fila:
        a = fila.pop()
        ax, ay, af, ah, aw = text_center(v, a)
        for b in v.texts:
            if b.index in vistos or _eh_balao(b) or len(trim(b.text)) > TEXTO_COLADO_MAX:
                continue
            bx, by, bf, bh, bw = text_center(v, b)
            f = max(af, bf)
            if f <= 0:
                continue
            folga = TEXTO_COLADO_FOLGA_BALAO if a is t else TEXTO_COLADO_FOLGA
            if max(abs(ax - bx) - aw - bw, abs(ay - by) - ah - bh) <= f * folga:
                vistos.add(b.index)
                colados.append(b)
                fila.append(b)
    return colados


def ponto_na_zona(x: float, y: float, alvo: str, zonas: List[Zone]) -> Tuple[float, float]:
    """O ponto da zona pedida mais perto de onde o balao esta, para o leader mudar o minimo."""
    centro = next(z for z in zonas if z.name == alvo)
    dentro, fora = 0.0, 1.0
    for _ in range(30):
        meio = (dentro + fora) / 2
        px, py = centro.x + (x - centro.x) * meio, centro.y + (y - centro.y) * meio
        if nearest_zone(px, py, zonas) == alvo:
            dentro = meio
        else:
            fora = meio
    t = dentro * MARGEM_ZONA
    return centro.x + (x - centro.x) * t, centro.y + (y - centro.y) * t


def zonas_da_folha(report: PosZoneReport, folha: str) -> List[str]:
    return sorted(z.name for z in report.zonas.get(folha, []))


def _localizar(report: PosZoneReport, occ: Occurrence) -> Tuple[ViewRead, TextRead]:
    folha = report.folhas[occ.sheet]
    v = next(x for x in folha.views if x.index == occ.view_index)
    t = next(x for x in v.texts if x.index == occ.text_index)
    return v, t


def colados_do_balao(report: PosZoneReport, occ: Occurrence) -> List[str]:
    v, t = _localizar(report, occ)
    return [trim(b.text).replace("\r", "").replace("\n", " / ") for b in textos_colados(v, t)]


def _gravar_posicao(bridge: CatiaBridge, report: PosZoneReport, occ: Occurrence, v: ViewRead, t: TextRead, x: float, y: float) -> Tuple[float, float]:
    r = bridge.call(SCRIPT, "MoverTexto", report.doc_full_name, occ.sheet, v.index, v.name, t.index, t.name, x, y)[0]
    return parse_number(r[0]), parse_number(r[1])


def mover_balao(bridge: CatiaBridge, report: PosZoneReport, occ: Occurrence, alvo: str) -> Movimento:
    """Move o balao para a zona pedida, com o que esta colado nele. Confere lendo de volta."""
    if occ.source != SOURCE_BALLOON:
        raise CatiaError("Só o balão define a zona: este número é sublinhado.")
    zonas = report.zonas.get(occ.sheet, [])
    if not zonas:
        raise CatiaError(f"A folha {occ.sheet} não tem zonas mapeadas.")
    if alvo not in {z.name for z in zonas}:
        raise CatiaError(f"A zona {alvo} não existe na folha {occ.sheet}.")
    if alvo == occ.zone:
        raise CatiaError(f"O balão já está na zona {alvo}.")
    v, t = _localizar(report, occ)
    nx, ny = ponto_na_zona(occ.x, occ.y, alvo, zonas)
    dvx, dvy = v.delta_to_view(nx - occ.x, ny - occ.y)
    mov = Movimento(occ, occ.zone, alvo, x_antes=occ.x, y_antes=occ.y, cx_antes=occ.cx, cy_antes=occ.cy)
    try:
        for u in [t] + textos_colados(v, t):
            x0, y0 = u.x, u.y
            x1, y1 = _gravar_posicao(bridge, report, occ, v, u, x0 + dvx, y0 + dvy)
            mov.textos.append((v, u, x0, y0, x1, y1))
        sx, sy = v.to_sheet(mov.textos[0][4], mov.textos[0][5])
        lida = nearest_zone(sx, sy, zonas)
        if lida != alvo:
            raise CatiaError(f"O balão ficou na zona {lida}, e não na {alvo}. Voltei para onde estava.")
    except CatiaError:
        for vista, u, x0, y0, _, _ in reversed(mov.textos):
            try:
                _gravar_posicao(bridge, report, occ, vista, u, x0, y0)
            except CatiaError:
                pass
        raise
    _aplicar(report, occ, mov, depois=True)
    return mov


def desfazer_movimento(bridge: CatiaBridge, report: PosZoneReport, mov: Movimento) -> None:
    for v, t, x0, y0, _, _ in reversed(mov.textos):
        _gravar_posicao(bridge, report, mov.occ, v, t, x0, y0)
    _aplicar(report, mov.occ, mov, depois=False)


def _aplicar(report: PosZoneReport, occ: Occurrence, mov: Movimento, depois: bool) -> None:
    """Atualiza o que foi lido e a tabela, sem ler o desenho inteiro de novo."""
    for _, t, x0, y0, x1, y1 in mov.textos:
        t.x, t.y = (x1, y1) if depois else (x0, y0)
    v, t = mov.textos[0][0], mov.textos[0][1]
    if depois:
        occ.x, occ.y = v.to_sheet(t.x, t.y)
        occ.cx, occ.cy = occ.cx + occ.x - mov.x_antes, occ.cy + occ.y - mov.y_antes
        occ.zone = mov.zona_depois
    else:
        occ.x, occ.y, occ.cx, occ.cy = mov.x_antes, mov.y_antes, mov.cx_antes, mov.cy_antes
        occ.zone = mov.zona_antes
    report.callouts = consolidate(report.occs)
