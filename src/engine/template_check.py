"""Check de Template: confere numeracao, formato e escala da legenda de cada folha.

So le: nao ativa folha, nao seleciona e nao escreve nada no desenho. Por isso nao usa o
map_text_links do Update Template, que escreve marcadores nos parametros.

Os campos sao achados pelo rotulo, como na legenda real: SCALE e SHEET/OF em cima, o valor embaixo,
na mesma celula. O nome dos textos nao serve: muda de um template para outro.

O rotulo pode estar num componente 2D (ditto) do Background, como a moldura da legenda dos templates
antigos: os textos de dentro dele tambem sao lidos. Sem rotulo nenhum, o campo e procurado pela posicao
na legenda, e o resultado avisa que foi achado assim.

Tres resultados: Certo, Errado e Conferir. Conferir e o que o programa nao tem como afirmar, como um
campo que nao achou. Nao e dado como certo nem como errado.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Sequence, Tuple

from engine.atualizar_template import (
    CAT_PAPER_USER, COM_ERROR, SHEET_COUNT_PARAMETER, drawing_sheets, format_from_background,
)
from engine.catia_bridge import CatiaBridge, CatiaError
from engine.documento import eh_desenho

CERTO, ERRADO, CONFERIR = "Certo", "Errado", "Conferir"
NUMERACAO, FORMATO, ESCALA, TOTAL = "Numeração", "Formato", "Escala", "Total de folhas"

ROTULOS_FOLHA = ("SHEET/OF", "SHEETOF", "SHT/OF", "SHTOF", "SHEET", "SHT")
ROTULOS_ESCALA = ("SCALE",)
# Celula da legenda, em mm na folha: o valor fica embaixo do rotulo. A linha REV e o numero da zona
# ficam mais abaixo que isto, e a celula vizinha fica mais longe na horizontal.
JANELA_X = 15.0
JANELA_Y = 18.0
# Sem rotulo: a legenda fica no canto de baixo, a direita, e os valores da mesma linha ficam alinhados.
LEGENDA_LARGURA = 260.0
LEGENDA_ALTURA = 90.0
MESMA_LINHA = 4.0
PELA_POSICAO = "Campo achado pela posição na legenda, sem o rótulo."

PAPEIS = {2: "A0", 3: "A1", 4: "A2", 5: "A3"}  # CatPaperSize
MEDIDAS = {"A0": (841.0, 1189.0), "A1": (594.0, 841.0), "A2": (420.0, 594.0), "A3": (297.0, 420.0)}
TOLERANCIA_PAPEL = 1.0  # mm
TOLERANCIA_ESCALA = 0.005  # relativa: 1:3 fica gravado como 0,3333

RE_NUMERO_FOLHA = re.compile(r"^[\d\s/]*\d[\d\s/]*$|^\s*/\s*$")
RE_ESCALA = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*[:/]\s*(\d+(?:[.,]\d+)?)\s*$")
RE_FOLHA_NO_TEXTO = re.compile(r"^\s*(?:SHEET|SHT)(?:\s*/\s*OF)?\s*:?\s+([\d\s/]*\d[\d\s/]*)$", re.IGNORECASE)
RE_ESCALA_NO_TEXTO = re.compile(r"^\s*SCALE\s*:?\s+(\S.*)$", re.IGNORECASE | re.DOTALL)
RE_ZONA = re.compile(r"^\s*ZONES?(?![A-Z])")
RE_ISO = re.compile(r"\bISO\b")
# Nao contam para a escala: podem ter outra escala, a pedido de quem usa a ferramenta.
# A isometrica nunca conta. PLAN VIEW tambem fica fora: ninguem garante a escala dela.
NOMES_FORA_DA_ESCALA = ("ISOMETRIC", "SECTION", "VIEW")
# Excecao: VIEW LOOKING FWD, AFT etc. e as vistas de projecao (Front view, Top view...) tem a escala da folha.
RE_VIEW_LOOKING = re.compile(r"\bVIEW\s+LOOKING\b|\b(?:FRONT|TOP|BOTTOM|LEFT|RIGHT|REAR|BACK)\s+VIEW\b")


# ---------------------------------------------------------------------
# Regras, sem CATIA
# ---------------------------------------------------------------------
@dataclass
class TextoLido:
    texto: str
    x: float  # na folha
    y: float


@dataclass
class VistaLida:
    nome: str
    escala: float


def numeracao_esperada(posicao: int, total: int) -> str:
    """Primeira folha: 1/total. As outras: so o proprio numero."""
    return f"1/{total}" if posicao == 1 else str(posicao)


def conferir_numeracao(lido: Optional[str], posicao: int, total: int) -> Tuple[str, str]:
    """lido None: o campo nao foi achado. Devolve situacao e explicacao."""
    if lido is None:
        return CONFERIR, "Não achei o campo SHEET/OF nesta folha."
    esperado = numeracao_esperada(posicao, total)
    if lido.replace(" ", "") == esperado:
        return CERTO, ""
    if not lido.strip():
        return ERRADO, "O campo SHEET/OF está vazio."
    if posicao > 1:
        return ERRADO, f"Da folha 2 em diante aparece só o número da folha: {esperado}."
    return ERRADO, f"A primeira folha mostra 1 e o total de folhas: {esperado}."


def parse_escala(texto: str) -> Optional[float]:
    """1:4 vira 0,25 e 2:1 vira 2. Devolve None se o texto nao for uma escala, como NTS."""
    achado = RE_ESCALA.match(texto or "")
    if not achado:
        return None
    a, b = (float(g.replace(",", ".")) for g in achado.groups())
    return a / b if a > 0 and b > 0 else None


def formato_escala(valor: float) -> str:
    if valor >= 1:
        return f"{round(valor, 2):g}:1"
    return f"1:{round(1 / valor, 2):g}"


def mesma_escala(a: float, b: float) -> bool:
    return abs(a - b) <= TOLERANCIA_ESCALA * max(abs(a), abs(b))


def conta_para_escala(nome: str) -> bool:
    """Isometrica, section e view podem ter outra escala, menos VIEW LOOKING e as de projecao. As zonas sao do template."""
    n = nome.upper()
    if RE_ZONA.match(n) or RE_ISO.search(n):
        return False
    n = RE_VIEW_LOOKING.sub("", n)
    return not any(p in n for p in NOMES_FORA_DA_ESCALA)


def _lista_vistas(vistas: Sequence[VistaLida]) -> str:
    return ", ".join(f"{v.nome} {formato_escala(v.escala)}" for v in vistas)


def conferir_escala(lido: Optional[str], vistas: Sequence[VistaLida]) -> Tuple[str, str, str]:
    """Compara o campo SCALE com as vistas que contam. Devolve situacao, esperado e explicacao.

    Se so parte das vistas bate, o campo nao esta errado, mas alguem precisa olhar: Conferir.
    """
    contam = [v for v in vistas if conta_para_escala(v.nome) and v.escala > 0]
    fora = [v.nome for v in vistas if not conta_para_escala(v.nome)]
    nota_fora = f" Fora da comparação: {', '.join(fora)}." if fora else ""
    esperado = " ou ".join(dict.fromkeys(formato_escala(v.escala) for v in contam))
    if lido is None:
        return CONFERIR, esperado, "Não achei o campo SCALE nesta folha." + nota_fora
    if not contam:
        return CONFERIR, "", "Nenhuma vista desta folha entra na comparação." + nota_fora
    if not lido.strip():
        return ERRADO, esperado, f"O campo SCALE está vazio. Vistas: {_lista_vistas(contam)}." + nota_fora
    valor = parse_escala(lido)
    if valor is None:
        return CONFERIR, esperado, f"O campo SCALE não é uma escala. Vistas: {_lista_vistas(contam)}." + nota_fora
    batem = [v for v in contam if mesma_escala(v.escala, valor)]
    if not batem:
        return ERRADO, esperado, f"Nenhuma vista está nessa escala. Vistas: {_lista_vistas(contam)}." + nota_fora
    diferentes = [v for v in contam if v not in batem]
    if diferentes:
        return CONFERIR, esperado, f"Só parte das vistas bate. Diferentes: {_lista_vistas(diferentes)}." + nota_fora
    return CERTO, esperado, f"Vistas: {_lista_vistas(contam)}." + nota_fora


def conferir_formato(formato: str, papel: int, largura: float, altura: float) -> Tuple[str, str, str]:
    """Etiqueta do formato contra o tamanho do papel. Devolve situacao, esperado e explicacao."""
    if papel in PAPEIS:
        tamanho = PAPEIS[papel]
    elif papel == CAT_PAPER_USER:
        tamanho = _formato_pela_medida(largura, altura)
    else:
        tamanho = ""
    medida = f"Papel de {largura:g} x {altura:g} mm."
    if not formato:
        return CONFERIR, tamanho, "Não achei a etiqueta do formato nesta folha."
    if tamanho:
        if formato == tamanho:
            return CERTO, tamanho, ""
        return ERRADO, tamanho, f"A etiqueta diz {formato} e o papel é {tamanho}. {medida}"
    if papel == CAT_PAPER_USER and formato in ("3A0", "E3"):
        # 3A0 e E3 sao papel personalizado, e as medidas certas estao so no template.
        return CONFERIR, "", f"Sem medida de referência para {formato}. {medida}"
    return ERRADO, "", f"O papel não é um {formato}. {medida}"


def _formato_pela_medida(largura: float, altura: float) -> str:
    menor, maior = sorted((largura, altura))
    for nome, (a, b) in MEDIDAS.items():
        if abs(menor - a) <= TOLERANCIA_PAPEL and abs(maior - b) <= TOLERANCIA_PAPEL:
            return nome
    return ""


def _sem_espacos(texto: str) -> str:
    """So letras, numeros e a barra: SHEET: OF, SHEET  OF e SHEET/OF. viram o mesmo rotulo."""
    return re.sub(r"[^A-Z0-9/]", "", texto.upper())


def _rotulos_na_folha(textos: Sequence[TextoLido], rotulos: Sequence[str]) -> List[TextoLido]:
    return [t for t in textos if _sem_espacos(t.texto) in rotulos]


def _valor_no_mesmo_texto(textos: Sequence[TextoLido], padrao: "re.Pattern[str]") -> Optional[str]:
    """Rotulo e valor no mesmo texto, como SCALE 1:4 ou com uma quebra de linha no meio."""
    for t in textos:
        achado = padrao.match(t.texto)
        if achado:
            return achado.group(1).strip()
    return None


def _na_celula(rotulo: TextoLido, t: TextoLido) -> bool:
    return abs(t.x - rotulo.x) <= JANELA_X and 0 < rotulo.y - t.y <= JANELA_Y


def campo_folha(textos: Sequence[TextoLido]) -> Optional[str]:
    """Valor do SHEET/OF: junta os pedacos, porque "1 /" e o total podem ser textos separados."""
    rotulos = _rotulos_na_folha(textos, ROTULOS_FOLHA)
    if not rotulos:
        return _valor_no_mesmo_texto(textos, RE_FOLHA_NO_TEXTO)
    for rotulo in rotulos:
        pedacos = [t for t in textos if _na_celula(rotulo, t) and RE_NUMERO_FOLHA.match(t.texto)]
        if pedacos:
            pedacos.sort(key=lambda t: t.x)
            return " ".join(t.texto.strip() for t in pedacos)
    return ""


def campo_escala(textos: Sequence[TextoLido]) -> Optional[str]:
    """Valor do SCALE. Se nada na celula parecer escala, devolve o texto mais perto, como NTS."""
    rotulos = _rotulos_na_folha(textos, ROTULOS_ESCALA)
    if not rotulos:
        return _valor_no_mesmo_texto(textos, RE_ESCALA_NO_TEXTO)
    for rotulo in rotulos:
        na_celula = [t for t in textos if _na_celula(rotulo, t) and t.texto.strip()]
        if na_celula:
            escalas = [t for t in na_celula if RE_ESCALA.match(t.texto)]
            mais_perto = min(escalas or na_celula, key=lambda t: rotulo.y - t.y)
            return mais_perto.texto.strip()
    return ""


def escala_pela_posicao(textos: Sequence[TextoLido], largura: float) -> Optional[TextoLido]:
    """Sem o rotulo SCALE: o unico texto com cara de escala no canto da legenda. Dois valores diferentes
    nao deixam escolher, e ai nao devolve nada."""
    candidatos = [t for t in textos if RE_ESCALA.match(t.texto) and t.y <= LEGENDA_ALTURA
                  and (largura <= 0 or t.x >= largura - LEGENDA_LARGURA)]
    valores = {parse_escala(t.texto) for t in candidatos}
    if len(valores) != 1 or None in valores:
        return None
    return max(candidatos, key=lambda t: t.x)


def folha_pela_linha(textos: Sequence[TextoLido], escala: TextoLido) -> Optional[str]:
    """Sem o rotulo SHEET/OF: os numeros na mesma linha da escala, a direita dela."""
    pedacos = [t for t in textos if t is not escala and RE_NUMERO_FOLHA.match(t.texto)
               and abs(t.y - escala.y) <= MESMA_LINHA and t.x > escala.x]
    if not pedacos:
        return None
    pedacos.sort(key=lambda t: t.x)
    return " ".join(t.texto.strip() for t in pedacos)


# ---------------------------------------------------------------------
# Resultado
# ---------------------------------------------------------------------
@dataclass
class ItemTemplate:
    sheet_name: str
    posicao: int
    regra: str
    lido: str
    esperado: str
    situacao: str
    detalhe: str = ""


@dataclass
class TemplateCheckReport:
    doc_full_name: str
    total_folhas: int = 0
    items: List[ItemTemplate] = field(default_factory=list)
    stopped: bool = False

    def _conta(self, situacao: str) -> int:
        return sum(1 for i in self.items if i.situacao == situacao)

    @property
    def certos(self) -> int:
        return self._conta(CERTO)

    @property
    def errados(self) -> int:
        return self._conta(ERRADO)

    @property
    def conferir(self) -> int:
        return self._conta(CONFERIR)


# ---------------------------------------------------------------------
# Leitura do desenho
# ---------------------------------------------------------------------
def _escala_da_vista(vista) -> float:
    for nome in ("Scale2", "Scale"):
        try:
            valor = float(getattr(vista, nome))
        except (COM_ERROR, AttributeError, TypeError, ValueError):
            continue
        if valor > 0:
            return valor
    return 0.0


def _textos_da_vista(vista, so_numero_de_folha: bool = False) -> List[TextoLido]:
    """Textos com a posicao na folha. Na Main View, so os que podem ser o numero da folha."""
    saida: List[TextoLido] = []
    try:
        textos = vista.Texts
        total = textos.Count
        vx, vy = vista.x, vista.y
    except COM_ERROR:
        return saida
    escala = _escala_da_vista(vista) or 1.0
    for i in range(1, total + 1):
        try:
            t = textos.Item(i)
            texto = str(t.Text)
            if so_numero_de_folha and not RE_NUMERO_FOLHA.match(texto):
                continue
            saida.append(TextoLido(texto, vx + t.x * escala, vy + t.y * escala))
        except COM_ERROR:
            continue
    return saida


def _textos_dos_componentes(vista) -> List[TextoLido]:
    """Textos de dentro dos componentes 2D (dittos) da vista, ja na posicao em que aparecem na folha."""
    saida: List[TextoLido] = []
    try:
        componentes = vista.Components
        total = componentes.Count
        vx, vy = vista.x, vista.y
    except (COM_ERROR, AttributeError, TypeError, ValueError):
        return saida
    escala_vista = _escala_da_vista(vista) or 1.0
    for i in range(1, total + 1):
        try:
            comp = componentes.Item(i)
            textos = comp.CompRef.Texts
            n = textos.Count
            cx, cy = float(comp.x), float(comp.y)
        except (COM_ERROR, AttributeError, TypeError, ValueError):
            continue
        escala = _escala_da_vista(comp) or 1.0
        try:
            angulo = float(comp.Angle)
        except (COM_ERROR, AttributeError, TypeError, ValueError):
            angulo = 0.0
        cos, sen = math.cos(angulo), math.sin(angulo)
        for k in range(1, n + 1):
            try:
                t = textos.Item(k)
                lx, ly = float(t.x) * escala, float(t.y) * escala
                x, y = cx + lx * cos - ly * sen, cy + lx * sen + ly * cos
                saida.append(TextoLido(str(t.Text), vx + x * escala_vista, vy + y * escala_vista))
            except (COM_ERROR, AttributeError, TypeError, ValueError):
                continue
    return saida


def _vistas_da_folha(folha) -> List[VistaLida]:
    """Da terceira em diante: 1 e a Main View e 2 e o Background."""
    saida: List[VistaLida] = []
    try:
        vistas = folha.Views
        total = vistas.Count
    except COM_ERROR:
        return saida
    for i in range(3, total + 1):
        try:
            v = vistas.Item(i)
            saida.append(VistaLida(str(v.Name), _escala_da_vista(v)))
        except COM_ERROR:
            continue
    return saida


def _papel(folha) -> Tuple[int, float, float]:
    try:
        return int(folha.PaperSize), float(folha.GetPaperWidth()), float(folha.GetPaperHeight())
    except COM_ERROR:
        return -1, 0.0, 0.0


def _conferir_folha(folha, nome: str, posicao: int, total: int) -> List[ItemTemplate]:
    try:
        fundo = folha.Views.Item(2)
        principal = folha.Views.Item(1)
    except COM_ERROR:
        return [ItemTemplate(nome, posicao, r, "", "", CONFERIR, "Não consegui ler esta folha.") for r in (NUMERACAO, FORMATO, ESCALA)]
    # A moldura da legenda pode ser um componente 2D: os rotulos ficam dentro dele.
    textos_fundo = _textos_da_vista(fundo) + _textos_dos_componentes(fundo)
    # O numero da folha pode estar na Main View, em cima do campo do Background.
    com_principal = textos_fundo + _textos_da_vista(principal, so_numero_de_folha=True)
    papel, largura, altura = _papel(folha)

    escala = campo_escala(textos_fundo)
    numero = campo_folha(com_principal)
    nota_escala = nota_numero = ""
    if escala is None or numero is None:
        achada = escala_pela_posicao(textos_fundo, largura)
        if achada is not None:
            if escala is None:
                escala, nota_escala = achada.texto.strip(), " " + PELA_POSICAO
            if numero is None:
                numero = folha_pela_linha(com_principal, achada)
                nota_numero = " " + PELA_POSICAO if numero is not None else ""

    situacao, detalhe = conferir_numeracao(numero, posicao, total)
    itens = [ItemTemplate(nome, posicao, NUMERACAO, numero or "", numeracao_esperada(posicao, total), situacao,
                          (detalhe + nota_numero).strip())]

    formato = format_from_background(folha)
    situacao, esperado, detalhe = conferir_formato(formato, papel, largura, altura)
    itens.append(ItemTemplate(nome, posicao, FORMATO, formato, esperado, situacao, detalhe))

    situacao, esperado, detalhe = conferir_escala(escala, _vistas_da_folha(folha))
    itens.append(ItemTemplate(nome, posicao, ESCALA, escala or "", esperado, situacao, (detalhe + nota_escala).strip()))
    return itens


def _conferir_total(doc, folha: str, total: int) -> Optional[ItemTemplate]:
    """No_of_Sheets e o que alimenta o campo da folha 1. Desenho sem ele nao tem o que conferir."""
    try:
        valor = doc.Parameters.Item(SHEET_COUNT_PARAMETER).ValueAsString()
        lido = int(float(str(valor).strip().replace(",", ".")))
    except (COM_ERROR, ValueError):
        return None
    if lido == total:
        return ItemTemplate(folha, 1, TOTAL, str(lido), str(total), CERTO, f"Parâmetro {SHEET_COUNT_PARAMETER}.")
    return ItemTemplate(folha, 1, TOTAL, str(lido), str(total), ERRADO, f"O parâmetro {SHEET_COUNT_PARAMETER} não bate com o número de folhas.")


def conferir_template(
    bridge: CatiaBridge,
    progress: Optional[Callable[[int, int], None]] = None,
    should_stop: Optional[Callable[[], bool]] = None,
) -> TemplateCheckReport:
    app = bridge.app
    try:
        if app.Documents.Count == 0:
            raise CatiaError("Nenhum documento aberto.")
        doc = app.ActiveDocument
        if not eh_desenho(doc.Name):
            raise CatiaError("O documento ativo não é um CATDrawing.")
        folhas = drawing_sheets(doc)
        if not folhas:
            raise CatiaError("O documento não possui folhas de desenho.")
        report = TemplateCheckReport(str(doc.FullName), len(folhas))
        nomes = [str(f.Name) for f in folhas]
    except COM_ERROR as exc:
        raise CatiaError(f"Não consegui ler o desenho: {exc}") from exc

    total_folhas = _conferir_total(doc, nomes[0], len(folhas))
    if total_folhas is not None:
        report.items.append(total_folhas)
    for posicao, (folha, nome) in enumerate(zip(folhas, nomes), 1):
        if should_stop and should_stop():
            report.stopped = True
            break
        report.items.extend(_conferir_folha(folha, nome, posicao, len(folhas)))
        if progress:
            progress(posicao, len(folhas))
    return report


def ir_para_folha(bridge: CatiaBridge, report: TemplateCheckReport, item: ItemTemplate) -> bool:
    """Mostra a folha inteira, com a legenda. Devolve False se a folha ou o desenho nao existem mais."""
    app = bridge.app
    try:
        documentos = app.Documents
        for i in range(1, documentos.Count + 1):
            doc = documentos.Item(i)
            if str(doc.FullName) != report.doc_full_name:
                continue
            doc.Activate()
            for folha in drawing_sheets(doc):
                if str(folha.Name) == item.sheet_name:
                    folha.Activate()
                    app.ActiveWindow.ActiveViewer.Reframe()
                    return True
    except COM_ERROR:
        return False
    return False
