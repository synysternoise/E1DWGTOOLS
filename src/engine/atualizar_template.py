"""Update Template: troca o formato (etiqueta) no proprio desenho. As vistas nao sao tocadas.

Porte de update.txt, a versao de 23/10 do CONSERTO-E1DWGVBA. Substitui engine/update_template.py,
que veio da versao de 14/10, que copiava as vistas para um documento novo.

Roda inteiro por COM, sem script dentro do CATIA: abrir, copiar e colar ficam 10 vezes mais lentos
dentro de um script, e o comando seguinte a qualquer script tambem. A legenda tem poucos textos, e
por isso o custo de COM nela e pequeno.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

import pywintypes

from engine.catia_bridge import CatiaBridge, CatiaError

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


def find_template(pasta: str, formato: str) -> str:
    """Primeiro arquivo .CATDrawing da pasta que comeca com o nome do template do formato."""
    if not pasta.endswith("\\"):
        pasta += "\\"
    prefixo = f"E1_DRAWING TEMPLATE_SHEET {normalize_format(formato)}_CATIAV5R32".lower()
    # Sem ordenar: os.listdir devolve na mesma ordem que o Dir$ do VBA.
    for nome in os.listdir(pasta):
        minusculo = nome.lower()
        if minusculo.endswith(".catdrawing") and minusculo.startswith(prefixo):
            return pasta + nome
    return ""


def is_aux_view(nome: str) -> bool:
    """Mesmo criterio do Position and Zone, para nao apagar views do usuario com ZONE no nome."""
    s = nome.strip(" ").upper()
    return s == "ZONE" or s.startswith("ZONE[") or s.startswith("ZONES_A1_SHT")


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


def _apagar(sel, objeto) -> None:
    sel.Clear()
    sel.Add(objeto)
    sel.Delete()
    sel.Clear()


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
        documentos = self.app.Documents
        for i in range(1, documentos.Count + 1):
            try:
                cheio = documentos.Item(i).FullName
            except COM_ERROR:
                continue
            if cheio.lower() == caminho.lower():
                # doc.Saved nao serve para saber se ele foi alterado: e True ate depois de mudar um
                # parametro. A macro recusa sempre um template ja aberto, e aqui tambem.
                raise self.erro(
                    f"O template já está aberto:\r\n{caminho}\r\n\r\nFeche-o sem salvar e execute novamente.",
                    1006, "OpenTemplate",
                )
        # Abre com o CATIA interativo: uma janela do CATIA ou do SmarTeam ficaria invisivel e travaria.
        self.app.Interactive = True
        modelo = documentos.Open(caminho)
        self.app.Interactive = False
        return modelo

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
            modelo = self.abrir_template(caminho)
            self._aplicar(modelo, caminho, folhas, todas)
        except COM_ERROR as exc:
            raise TemplateError(_descricao_com(exc), exc.hresult, "ApplyTemplateToSheets", self.modified) from exc
        finally:
            try:
                if modelo is not None:
                    modelo.Selection.Clear()
                    modelo.Close()
                self.doc.Activate()
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
        links = map_text_links(modelo.Parameters, fundo_modelo)
        chave_total = link_key_for_parameter(links, SHEET_COUNT_PARAMETER)
        prefixos = []
        if chave_total:
            prefixos = sheet_field_prefixes(fundo_modelo, links[chave_total])
        else:
            self.report.warnings.append(
                f"Nenhum texto do template está ligado a {SHEET_COUNT_PARAMETER}: numeração das folhas não atualizada."
            )

        # O template precisa estar ativo: com ele inativo o CATIA recusa selecionar os textos.
        modelo.Activate()
        self.avisar_status("Conversão de template: copiando o formato novo...")
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
            folha.PaperSize = papel
            folha.Orientation = orientacao
            if papel == CAT_PAPER_USER:
                folha.SetPaperWidth(largura)
                folha.SetPaperHeight(altura)

            # Uma busca + um Delete apagam o formato antigo e um Paste cola o novo.
            if self.selecionar_conteudo(sel, fundo) > 0:
                sel.Delete()
            sel.Clear()
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
            if posicao == 1:
                self._apagar_numero_antigo(sel, folha.Views.Item(1))
            self._refazer_vinculos(indice, links, chave_total if posicao >= 2 else "", parametros)
            if posicao >= 2 and chave_total:
                self._numerar_folha(sel, indice, folha.Views.Item(1), links[chave_total], prefixos, posicao, f["nome"])
            self._apagar_views_auxiliares(sel, folha)

            self.feitas += 1
            if self.progress:
                self.progress(self.feitas, len(todas))

        # Views auxiliares do template (ex.: zonas). Views 1 e 2 sao Main e Background.
        for iv in range(3, folha_modelo.Views.Count + 1):
            vista = folha_modelo.Views.Item(iv)
            modelo.Activate()
            sel_modelo.Clear()
            sel_modelo.Add(vista)
            if sel_modelo.Count == 0:
                raise self.erro(f"Não foi possível selecionar a view {vista.Name} do template.", 1203)
            sel_modelo.Copy()
            sel_modelo.Clear()
            self.doc.Activate()
            for f in folhas:
                folha = f["objeto"]
                antes = folha.Views.Count
                sel.Clear()
                sel.Add(folha)
                sel.Paste()
                sel.Clear()
                # So reposiciona se a view foi colada; senao a ultima view do desenho seria movida.
                if folha.Views.Count <= antes:
                    raise self.erro(f"Não foi possível colar a view {vista.Name} na folha {f['nome']}.", 1204)
                colada = folha.Views.Item(folha.Views.Count)
                colada.x = vista.x
                colada.y = vista.y

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

    def _refazer_vinculos(self, indice: _IndiceTextos, links: Dict[str, TextLink], pular: str, cache: dict) -> None:
        """Cada reserva vira o parametro de mesmo nome do desenho, da direita para a esquerda."""
        for chave, link in links.items():
            if chave.lower() == pular.lower():
                continue
            t = indice.localizar(link.nome, link.x, link.y)
            if t is None:
                continue
            achados = [self._parametro(cache, n) for n in link.parametros]
            if any(p is None for p in achados):
                continue  # o texto fica como veio do template e a macro avisa
            try:
                t.Text = link.template_text
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
                campo.Text = str(numero)
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


def run_update_template(
    bridge: CatiaBridge,
    ask_format: Callable[[str, str, str], Optional[str]],
    status: Optional[Callable[[str], None]] = None,
    progress: Optional[Callable[[int, int], None]] = None,
    pasta: str = PASTA_TEMPLATES,
) -> Optional[TemplateReport]:
    """Atualiza o template do desenho ativo. Retorna None se o usuario cancelar o pedido de formato."""
    c = _Conversao(bridge, status, progress)
    app = bridge.app
    try:
        if app.Documents.Count == 0:
            raise TemplateError("Nenhum documento aberto.", VB_OBJECT_ERROR + 1001)
        doc = app.ActiveDocument
        if not str(doc.Name).lower().endswith(".catdrawing"):
            raise TemplateError("O documento ativo não é um CATDrawing.", VB_OBJECT_ERROR + 1002)
        c.doc = doc
        folhas_doc = drawing_sheets(doc)
        if not folhas_doc:
            raise TemplateError("O documento não possui folhas de desenho.", VB_OBJECT_ERROR + 1003)
        doc_cheio = doc.FullName
        lidas = [(f, str(f.Name), format_from_background(f)) for f in folhas_doc]
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
        c.modified = True
        for formato, caminho in templates.items():
            c.aplicar_template(caminho, grupos[formato], folhas)
        if status:
            status("Atualizando a numeração das folhas")
        c.finalizar(folhas)
    except TemplateError as exc:
        exc.modified = exc.modified or c.modified
        c.restaurar(False)
        raise
    except COM_ERROR as exc:
        c.restaurar(False)
        raise TemplateError(_descricao_com(exc), exc.hresult, modified=c.modified) from exc
    c.restaurar(True)
    return report


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
