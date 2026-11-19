"""VPM: leitura do Excel, busca dos arquivos, plano do lote e historicos. Nada aqui abre o VPM.

Porte da macro "VPM Tools unificado" (criacao de PN por Duplicate, Update Content e sequencia). As
regras de validacao, os nomes de status e os arquivos de historico sao os mesmos da macro, na mesma
pasta (%LOCALAPPDATA%\\VPMTools): o que ja foi criado ou enviado por ela continua valendo aqui.
"""
from __future__ import annotations

import ast
import base64
import hashlib
import json
import math
import os
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

PASTA = Path(os.environ.get("LOCALAPPDATA") or str(Path.home())) / "VPMTools"
URL = "https://vpmweb.cax.embraer.com.br/vpm170/webapps/VPMWAPP/vpm.html?version=118sp2hf06"
ABA_EXCEL = "Entrada_Python"
MODELO_REPO = Path(__file__).resolve().parent / "vpm_modelo.xlsx"

# Coluna do Excel -> rotulo do campo no formulario do Duplicate. A ordem e a do formulario.
CAMPOS = {
    "part_number": "Part Number", "part_instance": "Part Instance", "conc_version": "Conc. Version",
    "conf_type": "Conf. Type", "english_description": "English Description",
    "portuguese_description": "Portuguese Description", "type": "Type", "origin": "Origin",
    "production": "Production", "design": "Design", "calculated_weight_g": "Calculated Weight (g)",
    "ata_code": "ATA Code", "dbt_code": "DBT Code", "drawing_class": "Drawing Class", "class": "Class",
    "status": "Status", "cpl": "CPL", "type_program": "Type/Program", "traceability": "Traceability",
}
OBRIGATORIAS = ["executar", "pn_origem", "ambiente"] + list(CAMPOS)

# PN no nome do arquivo: 171-52382-001, SPD171-52382-001, 171-52382ABC-001...
RE_PN = re.compile(r"(?<![A-Z0-9])(?:SPD)?\d{3}-\d{5}(?:[A-Z]{3,4})?-?\d{3}(?![A-Z0-9])", re.I)
TIPOS = {".catdrawing": "CATDRAWING", ".catpart": "CATPART", ".catproduct": "CATPRODUCT"}
TIPOS_3D = ("CATPART", "CATPRODUCT")

HISTORICO_CRIACAO = "historico_criacao_vpm.json"
HISTORICO_UPLOAD = "historico_upload_unificado.json"


def normalizar(valor) -> str:
    """Compara opcoes de lista sem ligar para maiusculas, espacos e tipos de traco."""
    v = unicodedata.normalize("NFKC", str(valor)).strip().casefold()
    v = re.sub(r"[\u2010-\u2015\u2212]", "-", v)
    return re.sub(r"\s*-\s*", "-", re.sub(r"\s+", " ", v))


# ---------------------------------------------------------------------
# Excel
# ---------------------------------------------------------------------
def ler_excel(caminho: str) -> List[dict]:
    """Linhas com executar = SIM, ja conferidas. Levanta ValueError com todos os erros do lote."""
    from openpyxl import load_workbook

    if not caminho:
        raise ValueError("Selecione o Excel de entrada.")
    wb = load_workbook(caminho, read_only=True, data_only=True)
    try:
        if ABA_EXCEL not in wb.sheetnames:
            raise ValueError(f"Aba {ABA_EXCEL} ausente.")
        linhas = wb[ABA_EXCEL].iter_rows(values_only=True)
        topo = next(linhas, None)
        if topo is None:
            raise ValueError("Planilha vazia.")
        return validar_linhas([str(v).strip() if v is not None else "" for v in topo], linhas)
    finally:
        wb.close()


def validar_linhas(cabecalho: List[str], linhas) -> List[dict]:
    faltando = [k for k in OBRIGATORIAS if k not in cabecalho]
    if faltando:
        raise ValueError("Colunas ausentes: " + ", ".join(faltando))
    if any(cabecalho.count(k) != 1 for k in OBRIGATORIAS):
        raise ValueError("Há cabeçalhos obrigatórios repetidos.")
    saida, erros, vistos = [], [], {}
    for numero, valores in enumerate(linhas, 2):
        bruta = dict(zip(cabecalho, valores))
        if str(bruta.get("executar", "")).strip().upper() != "SIM":
            continue
        linha = {k: str(v).strip() if v is not None else "" for k, v in bruta.items()}
        linha["_linha"] = numero
        vazios = [k for k in OBRIGATORIAS if not linha.get(k)]
        if vazios:
            erros.append(f"Linha {numero}: campos vazios: " + ", ".join(vazios))
        pn = linha.get("part_number", "")
        chave = pn.upper()
        if pn and chave == linha.get("pn_origem", "").upper():
            erros.append(f"Linha {numero}: PN novo igual à origem.")
        if pn and chave in vistos:
            erros.append(f"Linha {numero}: PN destino repetido na linha {vistos[chave]}: {pn}")
        vistos[chave] = numero
        try:
            peso = float(linha.get("calculated_weight_g", ""))
            if not math.isfinite(peso) or peso < 0:
                raise ValueError
        except ValueError:
            erros.append(f"Linha {numero}: peso deve ser numérico, finito e não negativo (ponto decimal).")
        try:
            versao = float(linha.get("conc_version", ""))
            if not versao.is_integer() or versao < 1:
                raise ValueError
            linha["conc_version"] = str(int(versao))
        except ValueError:
            erros.append(f"Linha {numero}: Conc. Version deve ser inteiro positivo.")
        saida.append(linha)
    if not saida:
        raise ValueError("Nenhuma linha com executar = SIM.")
    if erros:
        raise ValueError("Corrija o lote antes de iniciar:\n" + "\n".join(erros[:40]))
    return saida


def extrair_modelo_da_macro(caminho_py: str) -> bytes:
    """O Excel modelo que a macro antiga guarda em TEMPLATE_BASE64. Le o arquivo sem executar nada."""
    arvore = ast.parse(Path(caminho_py).read_text(encoding="utf-8", errors="replace"))
    for no in arvore.body:
        if isinstance(no, ast.Assign) and any(getattr(a, "id", "") == "TEMPLATE_BASE64" for a in no.targets):
            if isinstance(no.value, ast.Constant) and isinstance(no.value.value, str):
                dados = base64.b64decode(no.value.value)
                if not dados.startswith(b"PK"):
                    raise ValueError("TEMPLATE_BASE64 não é um arquivo Excel.")
                return dados
    raise ValueError("Esse arquivo não tem o TEMPLATE_BASE64 da macro do VPM.")


def caminho_do_modelo() -> Optional[Path]:
    """O modelo que vem com o HUB; senao, o que foi tirado da macro antiga neste PC."""
    for p in (MODELO_REPO, PASTA / "vpm_modelo.xlsx"):
        if p.is_file():
            return p
    return None


def salvar_modelo_vazio(origem: Path, destino: str) -> None:
    """Copia o modelo sem os dados: mantem as listas suspensas e deixa a primeira linha como NAO."""
    from openpyxl import load_workbook

    wb = load_workbook(origem)
    try:
        ws = wb[ABA_EXCEL]
        for linha in ws.iter_rows(min_row=2):
            for celula in linha:
                celula.value = None
        ws["A2"] = "NAO"
        wb.save(destino)
    finally:
        wb.close()


# ---------------------------------------------------------------------
# Arquivos CATIA
# ---------------------------------------------------------------------
def pn_do_arquivo(nome: str) -> str:
    """O PN no nome do arquivo, ou "" se nao houver exatamente um."""
    achados = {m.upper() for m in RE_PN.findall(Path(nome).stem)}
    return next(iter(achados)) if len(achados) == 1 else ""


def indice_de_arquivos(pasta: str, tipos) -> Dict[tuple, str]:
    """(PN, tipo) -> arquivo. So a pasta escolhida, sem subpastas."""
    if not pasta:
        raise ValueError("Selecione a pasta dos arquivos.")
    indice, erros = {}, []
    for p in sorted(Path(pasta).iterdir()):
        tipo = TIPOS.get(p.suffix.lower())
        if not p.is_file() or tipo not in tipos:
            continue
        pn = pn_do_arquivo(p.name)
        if not pn:
            erros.append("Nome sem PN único: " + p.name)
            continue
        chave = (pn, tipo)
        if chave in indice:
            erros.append(f"Arquivo duplicado para {pn} / {tipo}")
        indice[chave] = str(p.resolve())
    if erros:
        raise ValueError("\n".join(erros))
    if not indice:
        raise ValueError("Nenhum arquivo dos tipos selecionados na pasta. Subpastas não são incluídas.")
    return indice


def sha256_do_arquivo(caminho: str) -> str:
    h = hashlib.sha256()
    with Path(caminho).open("rb") as f:
        for bloco in iter(lambda: f.read(1024 * 1024), b""):
            h.update(bloco)
    return h.hexdigest()


# ---------------------------------------------------------------------
# Plano
# ---------------------------------------------------------------------
MODO_CRIAR, MODO_UPLOAD, MODO_SEQUENCIA = "create", "upload", "sequence"


def montar_plano(modo: str, excel: str, pasta: str, tipos, ambiente: str) -> List[dict]:
    """Uma entrada por PN: criacao (linha do Excel ou None) e arquivos para o Update Content."""
    if modo == MODO_UPLOAD and not re.fullmatch(r"[A-Z0-9_]+", ambiente or ""):
        raise ValueError("Ambiente inválido.")
    if modo != MODO_CRIAR and not tipos:
        raise ValueError("Selecione pelo menos um tipo de arquivo.")
    linhas = ler_excel(excel) if modo in (MODO_CRIAR, MODO_SEQUENCIA) else []
    indice = indice_de_arquivos(pasta, tipos) if modo in (MODO_UPLOAD, MODO_SEQUENCIA) else {}
    plano, erros = [], []
    if modo == MODO_UPLOAD:
        for (pn, tipo), caminho in indice.items():
            plano.append({"pn": pn, "ambiente": ambiente, "creation": None,
                          "files": [{"pn": pn, "arquivo": caminho, "kind": tipo, "status": "PENDENTE"}]})
    else:
        for r in linhas:
            arquivos = []
            if modo == MODO_SEQUENCIA:
                for tipo in tipos:
                    caminho = indice.get((r["part_number"].upper(), tipo))
                    if not caminho:
                        erros.append("Arquivo ausente: " + r["part_number"] + " / " + tipo)
                    else:
                        arquivos.append({"pn": r["part_number"], "arquivo": caminho, "kind": tipo, "status": "PENDENTE"})
            plano.append({"pn": r["part_number"], "ambiente": r["ambiente"], "creation": dict(r), "files": arquivos})
    if erros:
        raise ValueError("Nenhum PN foi criado. Corrija a associação:\n" + "\n".join(erros))
    if not plano:
        raise ValueError("Plano vazio.")
    for r in plano:
        r.update(criacao="PENDENTE" if r["creation"] else "NAO_SOLICITADA",
                 conteudo="PENDENTE" if r["files"] else "NAO_SOLICITADO", mensagem="")
        for f in r["files"]:
            f["sha256"] = sha256_do_arquivo(f["arquivo"])
    return plano


# ---------------------------------------------------------------------
# Historicos
# ---------------------------------------------------------------------
def gravar_json(caminho: Path, dados) -> None:
    """Grava inteiro ou nao grava: um arquivo pela metade apagaria o historico."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    tmp = caminho.with_suffix(".tmp")
    tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, caminho)


def ler_historico(caminho: Path, nome: str) -> dict:
    if not caminho.exists():
        return {}
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"{nome} ilegível. Não apague sem revisar o que já foi enviado: {exc}") from exc
    if not isinstance(dados, dict):
        raise ValueError(f"{nome} em formato inválido. Revise antes de continuar.")
    return dados


def chave_criacao(ambiente: str, pn: str) -> str:
    return ambiente.upper() + "|" + pn.upper()


def chave_upload(ambiente: str, pn: str, tipo: str, sha: str) -> str:
    return "|".join([ambiente.upper(), pn.upper(), tipo, sha])


def agora() -> str:
    return datetime.now().isoformat(timespec="seconds")
