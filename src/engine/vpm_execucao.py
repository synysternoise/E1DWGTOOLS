"""VPM: execucao do plano, PN por PN. Porte do Runner da macro "VPM Tools unificado".

Para cada PN: confere que os arquivos nao mudaram desde a previa, cria (se pedido) e faz o Update Content
de cada arquivo antes de passar ao proximo. Para no primeiro erro. Os historicos impedem repetir um
Create ou um Upload ja confirmados e bloqueiam os que ficaram sem confirmacao.

Os avisos para a tela chegam por um objeto com: log(texto), mudou(indice, linha), progresso(0-100),
perguntar(texto), aviso(texto) e terminou(ok, mensagem). A resposta da pergunta volta por responder(sim).
"""
from __future__ import annotations

import json
import threading
import traceback
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from engine import vpm_lote as L

ESPERA_RESPOSTA_S = 0.2


class ExecucaoVPM:
    def __init__(self, plano: List[dict], modo: str, avisos, criar: bool = True, pasta: Path = L.PASTA):
        self.plano = json.loads(json.dumps(plano))
        self.modo = modo
        self.avisos = avisos
        self.criar = criar  # False: so preenche, confere e cancela cada formulario
        self.pasta = pasta
        self.parar = threading.Event()
        self.encerrar = threading.Event()
        self._resposta = threading.Event()
        self._aceito = False
        self.nav = None
        self._cat = None
        self.indice = 0
        self.arquivo_ativo: Optional[dict] = None
        self.tem_arquivos = any(r["files"] for r in self.plano)
        self.relatorio = pasta / ("sequencia_vpm_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f") + ".json")
        self.caminho_criacao = pasta / L.HISTORICO_CRIACAO
        self.caminho_upload = pasta / L.HISTORICO_UPLOAD
        self.hist_criacao = L.ler_historico(self.caminho_criacao, "Histórico de criação") \
            if any(r["creation"] for r in self.plano) else {}
        self.hist_upload = L.ler_historico(self.caminho_upload, "Histórico de upload")

    # ------------------------------------------------------------------
    # Controle
    # ------------------------------------------------------------------
    def guarda(self) -> None:
        """Chamado o tempo todo durante o lote: para no pedido do usuario ou com o PICS desconectado."""
        if self.parar.is_set():
            raise RuntimeError("Interrompido pelo usuário.")
        if self.tem_arquivos and self.nav is not None:
            self.nav.conferir_pics()

    def confirmar(self, texto: str) -> None:
        self._resposta.clear()
        self._aceito = False
        self.avisos.perguntar(texto)
        while not self._resposta.wait(ESPERA_RESPOSTA_S):
            self.guarda()
        self.guarda()
        if not self._aceito:
            raise RuntimeError("Confirmação recusada. Lote interrompido.")

    def responder(self, sim: bool) -> None:
        self._aceito = sim
        self._resposta.set()

    # ------------------------------------------------------------------
    # Relatorio e historicos
    # ------------------------------------------------------------------
    def publicar(self) -> None:
        L.gravar_json(self.relatorio, self.plano)
        self.avisos.mudou(self.indice, dict(self.plano[self.indice]))

    def registrar_criacao(self, status: str) -> None:
        r = self.plano[self.indice]["creation"]
        self.hist_criacao[L.chave_criacao(r["ambiente"], r["part_number"])] = {
            "status": status, "data": L.agora(), "pn_origem": r["pn_origem"]}
        L.gravar_json(self.caminho_criacao, self.hist_criacao)

    def chave_upload(self, f: dict) -> str:
        r = self.plano[self.indice]
        return L.chave_upload(r["ambiente"], r["pn"], f["kind"], f["sha256"])

    def registrar_upload(self, f: dict) -> None:
        if f["status"] in ("ENVIO_INICIADO", "CONFIRMADO_PELO_USUARIO"):
            self.hist_upload[self.chave_upload(f)] = {"status": f["status"], "data": datetime.now().isoformat(),
                                                      "arquivo": f["arquivo"]}
            L.gravar_json(self.caminho_upload, self.hist_upload)
        L.gravar_json(self.relatorio, self.plano)

    # ------------------------------------------------------------------
    # Plano
    # ------------------------------------------------------------------
    def executar_plano(self, cat) -> Tuple[bool, str]:
        self._cat = cat
        total = len(self.plano)
        for i, r in enumerate(self.plano):
            self.indice = i
            self.arquivo_ativo = None
            self.avisos.log(f"[{i + 1}/{total}] {r['pn']}")
            try:
                self.guarda()
                for f in r["files"]:
                    if L.sha256_do_arquivo(f["arquivo"]) != f["sha256"]:
                        raise RuntimeError("Arquivo alterado desde a prévia. Nenhuma criação iniciada para este PN; "
                                           "monte a prévia de novo.")
                if r["creation"]:
                    self._criar(i, r, total)
                for f in r["files"]:
                    self._atualizar(r, f)
                if r["files"]:
                    r["conteudo"] = "CONFIRMADO_PELO_USUARIO_OU_HISTORICO"
                    r["mensagem"] = "Etapas solicitadas concluídas; Upload/Commit confirmados pelo usuário quando aplicável."
                self.publicar()
                self.avisos.progresso(int((i + 1) / total * 100))
            except Exception as exc:  # noqa: BLE001 - qualquer falha para o lote e fica no relatorio
                self._falhou(i, r, exc)
                return False, f"Lote interrompido em {r['pn']}. {exc}"
        return True, "Lote concluído. Relatório: " + self.relatorio.name

    def _criar(self, i: int, r: dict, total: int) -> None:
        linha = r["creation"]
        anterior = self.hist_criacao.get(L.chave_criacao(linha["ambiente"], linha["part_number"]), {}).get("status")
        if self.criar and anterior == "ENVIO_INICIADO":
            r["criacao"] = "REVISAO_NECESSARIA"
            raise RuntimeError("Criação anterior incerta. Confira no VPM; não será repetida.")
        if self.criar and anterior == "CONFIRMADO":
            r["criacao"] = "CONFIRMADO_HISTORICO_LOCAL"
            r["mensagem"] = "Criação não repetida; já confirmada no histórico local."
            self.publicar()
            return
        r["criacao"] = "EM_EXECUCAO"
        self.publicar()
        self.nav.enviado = False

        def etapa(n: int, texto: str) -> None:
            self.guarda()
            self.avisos.log(f"[{i + 1}/{total}] {texto}")
            self.avisos.progresso(int((i + n / 100) / total * 100))

        r["mensagem"] = self.nav.criar_pn(linha, self.criar, self.registrar_criacao, etapa)
        r["criacao"] = "CONFIRMADO" if self.criar else "VALIDADO_SEM_CRIAR"
        self.publicar()

    def _atualizar(self, r: dict, f: dict) -> None:
        self.arquivo_ativo = f
        self.nav.enviado = False
        self.guarda()
        if L.sha256_do_arquivo(f["arquivo"]) != f["sha256"]:
            raise RuntimeError("Arquivo alterado desde a prévia. Monte a prévia de novo.")
        prefixo = "|".join([r["ambiente"].upper(), r["pn"].upper(), f["kind"]]) + "|"
        if any(k.startswith(prefixo) and v.get("status") == "ENVIO_INICIADO" for k, v in self.hist_upload.items()):
            raise RuntimeError("Upload anterior incerto para este PN e tipo, mesmo que o arquivo tenha mudado. "
                               "Confira o VPM antes de repetir.")
        anterior = self.hist_upload.get(self.chave_upload(f), {}).get("status")
        if anterior == "CONFIRMADO_PELO_USUARIO":
            f["status"] = "IGNORADO_HISTORICO_LOCAL"
            self.avisos.log("Conteúdo já confirmado no histórico local para este arquivo: " + f["arquivo"])
            return
        r["conteudo"] = "EM_EXECUCAO " + f["kind"]
        f["status"] = "EM_EXECUCAO"
        self.publicar()
        self.nav.preparar_upload(r["ambiente"])
        if f["kind"] != "CATDRAWING":
            self.confirmar(f"3D EXPERIMENTAL: {f['kind']}\nArquivo: {f['arquivo']}\n"
                           "O documento DOCCAD correspondente precisa existir no VPM. Não cria CATPart/CATProduct "
                           "ausente, não importa dependências e não faz Commit automático. Continuar?")
        self.nav.update_content(self._cat, f, self.confirmar, self.registrar_upload)
        if f["status"] != "CONFIRMADO_PELO_USUARIO":
            raise RuntimeError("Upload sem confirmação final.")
        self.publicar()

    def _falhou(self, i: int, r: dict, exc: Exception) -> None:
        enviado = bool(self.nav is not None and self.nav.enviado)
        if r["creation"] and r["criacao"] == "EM_EXECUCAO":
            r["criacao"] = "CRIACAO_INCERTA" if enviado else "ERRO_ANTES_CREATE"
        if self.arquivo_ativo is not None:
            f = self.arquivo_ativo
            f["status"] = "UPLOAD_INCERTO" if enviado or f.get("status") == "ENVIO_INICIADO" else "ERRO_ANTES_UPLOAD"
            r["conteudo"] = f["status"]
        elif r["files"]:
            r["conteudo"] = "NAO_EXECUTADO"
        r["mensagem"] = str(exc)
        if r["criacao"] == "CRIACAO_INCERTA":
            r["mensagem"] += " O Create pode ter sido recebido. Não repita antes de conferir o PN no VPM."
        self.publicar()
        self._gravar_erro(traceback.format_exc())
        if self.nav is not None and self.tem_arquivos:
            try:
                self.nav.diagnostico()
            except Exception:  # noqa: BLE001
                pass
        for depois in self.plano[i + 1:]:
            if depois["criacao"] == "PENDENTE":
                depois["criacao"] = "NAO_EXECUTADO"
            if depois["conteudo"] == "PENDENTE":
                depois["conteudo"] = "NAO_EXECUTADO"
        L.gravar_json(self.relatorio, self.plano)
        self.avisos.log(traceback.format_exc())

    def _gravar_erro(self, texto: str) -> None:
        try:
            self.pasta.mkdir(parents=True, exist_ok=True)
            (self.pasta / "erro_unificado.txt").write_text(texto, encoding="utf-8")
        except OSError:
            pass

    # ------------------------------------------------------------------
    # Sessao: CATIA, Edge e espera ate o usuario encerrar
    # ------------------------------------------------------------------
    def rodar(self) -> Tuple[bool, str]:
        from playwright.sync_api import sync_playwright

        from engine.vpm_web import NavegadorVPM

        com = None
        try:
            if self.tem_arquivos:
                import pythoncom
                import win32com.client

                com = pythoncom
                com.CoInitialize()
                self._cat = win32com.client.GetActiveObject("CATIA.Application")
                self.avisos.log("CATIA aberto conectado. Nenhuma nova instância será iniciada.")
            L.gravar_json(self.relatorio, self.plano)
            with sync_playwright() as pw:
                ctx = None
                try:
                    ctx = pw.chromium.launch_persistent_context(str(self.pasta / "perfil_edge_vpm"), channel="msedge",
                                                                headless=False)
                    self.nav = NavegadorVPM(ctx, self.guarda, self.avisos.log, self.avisos.aviso, self.pasta)
                    resultado = self.executar_plano(self._cat)
                except Exception:  # noqa: BLE001
                    texto = traceback.format_exc()
                    self._gravar_erro(texto)
                    self.avisos.log(texto)
                    resultado = (False, "Falha ao iniciar ou continuar. Consulte o acompanhamento.")
                self.avisos.terminou(*resultado)
                if ctx is not None:
                    self.avisos.log("O Edge fica aberto para revisão. Use Encerrar sessão antes de outro lote.")
                    while not self.encerrar.is_set():
                        try:
                            if not ctx.pages:
                                break
                            ctx.pages[0].wait_for_timeout(250)
                        except Exception:  # noqa: BLE001 - o usuario fechou o Edge
                            break
                    try:
                        ctx.close()
                    except Exception:  # noqa: BLE001
                        pass
                return resultado
        except Exception:  # noqa: BLE001
            self.avisos.log(traceback.format_exc())
            resultado = (False, "Não foi possível iniciar. Confira o CATIA aberto, as bibliotecas e os históricos.")
            self.avisos.terminou(*resultado)
            return resultado
        finally:
            if com is not None:
                com.CoUninitialize()
