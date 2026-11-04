"""Split 2D e Split 3D: dividem um desenho por folha e um CATPart por Bodies.

Portes de vba_referencia/SPLIT 2D e SPLIT 3D. Rodam por COM, sem script dentro do CATIA e sem
redesenhar a tela: sao poucos comandos, todos pesados (abrir, colar, salvar).
"""
from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass, field
from typing import Callable, List, Optional

import pywintypes

from engine.catia_bridge import CatiaBridge, CatiaError

COM_ERROR = pywintypes.com_error
TITULO_SPLIT_3D = "Split CATPart"
PERGUNTA_PARTES = "Em quantas partes será dividido?"
PARTES_SUGERIDAS = "2"
CAT_VIS_NO_SHOW = 1


class SplitError(CatiaError):
    """Um erro parou o Split. O que ja foi exportado continua em report."""

    def __init__(self, descricao: str, numero: int = 0, report=None, ferramenta: str = "2D"):
        super().__init__(descricao, numero)
        self.report = report
        self.ferramenta = ferramenta

    @property
    def mensagem(self) -> str:
        if self.ferramenta == "3D":
            return f"Erro ao executar o SPLIT 3D:\r\n{self}"
        return f"Erro Nº {self.number}\r\n{self}"


@dataclass
class SplitReport:
    tool: str
    folder: str
    pn: str = ""
    bodies: int = 0
    locked_views: int = 0
    files: List[str] = field(default_factory=list)
    stopped: bool = False

    @property
    def mensagem(self) -> str:
        if self.tool == "3D":
            return f"Split concluído!\r\nPN: {self.pn}\r\nBodies: {self.bodies}\r\nArquivos: {len(self.files)}"
        return f"{len(self.files)} folha(s) exportada(s) com sucesso.\r\n\r\n{self.folder}"


def clean_file_name(nome: str) -> str:
    for ch in ("\\", "/", ":", "*", "?", '"', "<", ">", "|"):
        nome = nome.replace(ch, "_")
    return nome.strip(" ")


def val(texto: str) -> float:
    """Val do VBA: le o numero do comeco do texto, ignorando espacos, e devolve 0 se nao houver."""
    m = re.match(r"[+-]?(\d+\.?\d*|\.\d+)", re.sub(r"[ \t\r\n]", "", texto))
    return float(m.group(0)) if m else 0.0


def number_of_parts(texto: str) -> int:
    """CLng(Val(...)): arredonda o .5 para o par, como round do Python."""
    return int(round(val(texto)))


def split_ranges(reais: int, partes: int) -> List[tuple]:
    """Faixas de Bodies (de 1 em diante) de cada parte. As primeiras recebem o que sobra."""
    por_parte, sobra = divmod(reais, partes)
    faixas, inicio = [], 1
    for n in range(1, partes + 1):
        fim = inicio + por_parte - 1 + (1 if n <= sobra else 0)
        faixas.append((inicio, fim))
        inicio = fim + 1
    return faixas


def _apagar_arquivo(caminho: str) -> None:
    if os.path.isfile(caminho):
        os.remove(caminho)


def _descricao(exc: COM_ERROR) -> str:
    info = exc.excepinfo
    return (info[2] if info and info[2] else exc.strerror) or "erro desconhecido"


def _restaurar(app) -> None:
    """Devolve os alertas e a tela do CATIA. Nao pode esconder o erro original."""
    for nome in ("RefreshDisplay", "DisplayFileAlerts"):
        try:
            setattr(app, nome, True)
        except COM_ERROR:
            pass


# ---------------------------------------------------------------------
# Split 2D
# ---------------------------------------------------------------------
def _travar_vistas(doc) -> int:
    """Trava todas as vistas destravadas, menos o Background. Devolve quantas travou."""
    total = 0
    folhas = doc.Sheets
    for i in range(1, folhas.Count + 1):
        vistas = folhas.Item(i).Views
        for j in range(1, vistas.Count + 1):
            try:
                v = vistas.Item(j)
                if v.Name != "Background View" and not v.LockStatus:
                    v.LockStatus = True
                    total += 1
            except COM_ERROR:
                pass
    return total


def _exportar_folha(app, temporario: str, nome_folha: str, final: str) -> None:
    """Abre a copia do arquivo, tira as outras folhas e salva como arquivo final."""
    copia = app.Documents.Open(temporario)
    try:
        folhas = copia.Sheets
        for j in range(folhas.Count, 0, -1):
            if folhas.Item(j).Name != nome_folha:
                try:
                    folhas.Remove(j)
                except COM_ERROR:
                    sel = copia.Selection
                    sel.Clear()
                    sel.Add(folhas.Item(j))
                    sel.Delete()
        copia.SaveAs(final)
    except COM_ERROR:
        # Melhoria sobre a macro: a copia nao fica aberta depois de um erro.
        try:
            copia.Close()
        except COM_ERROR:
            pass
        raise
    copia.Close()


def run_split_2d(
    bridge: CatiaBridge,
    warn: Callable[[str], None],
    info: Optional[Callable[[str], None]] = None,
    progress: Optional[Callable[[int, int], None]] = None,
    should_stop: Optional[Callable[[], bool]] = None,
    downloads: Optional[str] = None,
) -> Optional[SplitReport]:
    """Exporta cada folha do desenho ativo para um CATDrawing proprio, em Downloads."""
    app = bridge.app
    report = None
    alterou = False
    try:
        if app.Documents.Count == 0:
            warn("Nenhum documento aberto.")
            return None
        doc = app.ActiveDocument
        nome = str(doc.Name)
        if not nome.lower().endswith(".catdrawing"):
            warn("Abra um CATDrawing antes de executar.")
            return None
        if not doc.Path:
            warn("Salve o CATDrawing antes de executar a macro.")
            return None

        travadas = _travar_vistas(doc)
        if travadas > 0 and info:
            info(f"{travadas} vista(s) foram bloqueadas automaticamente.")

        original = doc.FullName
        base = downloads or os.path.join(os.environ.get("USERPROFILE", ""), "Downloads")
        pasta = os.path.join(base, nome[: nome.rfind(".")]) + "\\"
        if not os.path.isdir(pasta):
            os.mkdir(pasta)

        folhas = [str(doc.Sheets.Item(i).Name) for i in range(1, doc.Sheets.Count + 1)]
        report = SplitReport("2D", pasta, locked_views=travadas)
        alterou = True
        app.DisplayFileAlerts = False
        app.RefreshDisplay = False
        for i, folha in enumerate(folhas, 1):
            if should_stop and should_stop():
                report.stopped = True
                break
            limpo = clean_file_name(folha)
            temporario = f"{pasta}~TMP_{limpo}.CATDrawing"
            final = f"{pasta}{limpo}.CATDrawing"
            _apagar_arquivo(temporario)
            shutil.copyfile(original, temporario)
            _apagar_arquivo(final)
            _exportar_folha(app, temporario, folha, final)
            _apagar_arquivo(temporario)
            if final not in report.files:
                report.files.append(final)
            try:
                app.StatusBar = f"Exportado: {i} de {len(folhas)}"
            except COM_ERROR:
                pass
            if progress:
                progress(i, len(folhas))
    except COM_ERROR as exc:
        raise SplitError(_descricao(exc), exc.hresult, report) from exc
    except OSError as exc:
        raise SplitError(str(exc), exc.errno or 0, report) from exc
    finally:
        if alterou:
            _restaurar(app)
    return report


# ---------------------------------------------------------------------
# Split 3D
# ---------------------------------------------------------------------
@dataclass
class SplitPreview:
    doc_name: str
    full_name: str
    size_mb: float
    pn: str = ""
    bodies: List[str] = field(default_factory=list)
    sheets: List[str] = field(default_factory=list)
    locked_all: bool = True


def _tamanho_mb(caminho: str) -> float:
    try:
        return os.path.getsize(caminho) / (1024 * 1024)
    except OSError:
        return 0.0


def preview_2d(bridge: CatiaBridge) -> Optional[SplitPreview]:
    """Folhas do desenho ativo, sem alterar nada. None se nao houver desenho salvo."""
    app = bridge.app
    try:
        if app.Documents.Count == 0:
            return None
        doc = app.ActiveDocument
        nome = str(doc.Name)
        if not nome.lower().endswith(".catdrawing") or not doc.Path:
            return None
        cheio = str(doc.FullName)
        folhas = [str(doc.Sheets.Item(i).Name) for i in range(1, doc.Sheets.Count + 1)]
    except COM_ERROR:
        return None
    return SplitPreview(nome, cheio, _tamanho_mb(cheio), sheets=folhas)


def preview_3d(bridge: CatiaBridge) -> Optional[SplitPreview]:
    """Bodies do CATPart ativo, sem alterar nada. None se nao houver peca ativa."""
    app = bridge.app
    try:
        if app.Documents.Count == 0:
            return None
        doc = app.ActiveDocument
        nome = str(doc.Name)
        if not nome.lower().endswith(".catpart"):
            return None
        peca = doc.Part
        cheio = str(doc.FullName)
        corpos = [str(peca.Bodies.Item(i).Name) for i in range(1, peca.Bodies.Count + 1)]
        return SplitPreview(nome, cheio, _tamanho_mb(cheio), _numero_da_peca(doc, peca), [c for c in corpos if c.upper() != "PARTBODY"])
    except COM_ERROR:
        return None


def _numero_da_peca(doc, peca) -> str:
    try:
        pn = str(doc.Product.PartNumber)
        if not pn.strip(" "):
            pn = str(doc.Name)
        if not pn.strip(" "):
            pn = str(peca.Name)
        return pn
    except COM_ERROR:
        return ""


def _criar_parte(app, doc, peca, indices, nomes, nome_principal, inicio, fim, novo_pn, arquivo) -> None:
    sel = doc.Selection
    sel.Clear()
    sel.Add(peca.MainBody)
    for i in range(inicio, fim + 1):
        sel.Add(peca.Bodies.Item(indices[i - 1]))
    sel.Copy()

    novo = app.Documents.Add("Part")
    try:
        nova = novo.Part
        try:
            novo.Product.PartNumber = novo_pn
        except COM_ERROR:
            pass
        destino = novo.Selection
        destino.Clear()
        destino.Add(nova.MainBody)
        try:
            destino.PasteSpecial("CATPrtResultWithOutLink")
        except COM_ERROR:
            destino.Clear()
            destino.Add(nova.MainBody)
            destino.PasteSpecial("CATPrtResult")
        nova.Update()
        try:
            nova.MainBody.Name = nome_principal
        except COM_ERROR:
            pass
        indice = 2
        for i in range(inicio, fim + 1):
            if indice <= nova.Bodies.Count:
                try:
                    nova.Bodies.Item(indice).Name = nomes[i - 1]
                except COM_ERROR:
                    pass
                indice += 1
        _esconder_referencias(novo, nova)
        novo.SaveAs(arquivo)
    except COM_ERROR:
        # Melhoria sobre a macro: a peca incompleta nao fica aberta depois de um erro.
        try:
            novo.Close()
        except COM_ERROR:
            pass
        raise
    novo.Close()


def _esconder_referencias(novo, nova) -> None:
    sel = novo.Selection
    try:
        sel.Clear()
        origem = nova.OriginElements
        sel.Add(origem.PlaneXY)
        sel.Add(origem.PlaneYZ)
        sel.Add(origem.PlaneZX)
        sel.VisProperties.SetShow(CAT_VIS_NO_SHOW)
        sel.Clear()
        if nova.AxisSystems.Count > 0:
            sel.Add(nova.AxisSystems.Item(1))
            sel.VisProperties.SetShow(CAT_VIS_NO_SHOW)
            sel.Clear()
    except COM_ERROR:
        pass


def run_split_3d(
    bridge: CatiaBridge,
    ask: Callable[[str, str, str], Optional[str]],
    warn: Callable[[str], None],
    progress: Optional[Callable[[int, int], None]] = None,
    should_stop: Optional[Callable[[], bool]] = None,
) -> Optional[SplitReport]:
    """Divide os Bodies do CATPart ativo em partes, na subpasta SPLIT_PARTS."""
    app = bridge.app
    report = None
    alterou = False
    try:
        doc = app.ActiveDocument
        if not str(doc.Name).lower().endswith(".catpart"):
            warn("Abra um CATPart.")
            return None
        cheio = str(doc.FullName)
        if not cheio:
            warn("Salve o CATPart antes de executar.")
            return None
        peca = doc.Part
        pn = _numero_da_peca(doc, peca)
        nome_principal = peca.MainBody.Name
        indices, nomes = [], []
        for i in range(1, peca.Bodies.Count + 1):
            nome = str(peca.Bodies.Item(i).Name)
            if nome.upper() != "PARTBODY":
                indices.append(i)
                nomes.append(nome)
        if not indices:
            warn("Nenhum Body encontrado.")
            return None

        partes = number_of_parts(ask(PERGUNTA_PARTES, TITULO_SPLIT_3D, PARTES_SUGERIDAS) or "")
        if partes < 2:
            return None
        partes = min(partes, len(indices))

        pasta_peca, arquivo = os.path.split(cheio)
        base = arquivo[: arquivo.rfind(".")] if "." in arquivo else arquivo
        pasta = os.path.join(pasta_peca, "SPLIT_PARTS") + "\\"
        if not os.path.isdir(pasta):
            os.mkdir(pasta)

        report = SplitReport("3D", pasta, pn=pn, bodies=len(indices))
        alterou = True
        app.RefreshDisplay = False
        app.DisplayFileAlerts = False
        for n, (inicio, fim) in enumerate(split_ranges(len(indices), partes), 1):
            if should_stop and should_stop():
                report.stopped = True
                break
            destino = f"{pasta}{base}_P{n:02d}.CATPart"
            _criar_parte(app, doc, peca, indices, nomes, nome_principal, inicio, fim, f"{pn}_P{n:02d}", destino)
            report.files.append(destino)
            if progress:
                progress(n, partes)
    except COM_ERROR as exc:
        raise SplitError(_descricao(exc), exc.hresult, report, "3D") from exc
    except OSError as exc:
        raise SplitError(str(exc), exc.errno or 0, report, "3D") from exc
    finally:
        if alterou:
            _restaurar(app)
    return report
