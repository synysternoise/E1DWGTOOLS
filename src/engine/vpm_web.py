"""VPM: o que o HUB faz na pagina do VPM, pelo Edge (Playwright), e no CATIA durante o Update Content.

Porte da macro "VPM Tools unificado". Mesma ordem de cliques e mesmas protecoes:
- nada e escolhido por coordenada nem por indice: cada botao ou campo precisa ser encontrado uma vez so;
- Create e Upload sao clicados uma vez, com o historico gravado antes do clique;
- quando a arvore ou o menu nao sao encontrados, o passo vira manual e o usuario confirma;
- "PICS not connected" na pagina interrompe o lote.

O Update Content do CATPart e do CATProduct e o mesmo caminho do CATDrawing com o tipo trocado, como na
macro (experimental): o documento DOCCAD do tipo certo precisa existir no VPM.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Callable

from engine import vpm_lote as L

DESCOBRIR_CAMPOS = r"""labels=>{
const visible=e=>!!e.getClientRects().length&&getComputedStyle(e).visibility!=='hidden';
const norm=s=>(s||'').replace(/\s+/g,' ').trim().replace(/[:*]+$/,'').trim();
const controls=[...document.querySelectorAll('input:not([type=hidden]):not([type=button]):not([type=submit]),select,textarea')].filter(visible);
const all=[...document.querySelectorAll('body *')].filter(visible),result={},used=new Map();
for(const label of labels){let candidates=new Set();
for(const c of controls)if(norm(c.getAttribute('aria-label'))===label||[...(c.labels||[])].some(l=>norm(l.textContent)===label))candidates.add(c);
if(!candidates.size){const texts=all.filter(e=>norm(e.textContent)===label&&![...e.children].some(ch=>norm(ch.textContent)===label));
for(const e of texts){let p=e;for(let d=0;p&&d<9;d++,p=p.parentElement){const inside=controls.filter(c=>p.contains(c));if(inside.length===1){candidates.add(inside[0]);break;}if(inside.length>1)break;}}}
if(candidates.size===1){const c=[...candidates][0];if(used.has(c)){result[used.get(c)]={error:'Controle compartilhado'};result[label]={error:'Controle compartilhado'};continue;}used.set(c,label);const token='vpm-test-'+labels.indexOf(label);c.setAttribute('data-vpm-test',token);result[label]={token,tag:c.tagName,type:c.type,disabled:c.disabled,readonly:c.readOnly,options:c.tagName==='SELECT'?[...c.options].map(o=>({text:o.text.trim(),value:o.value})):[]};}
else result[label]={error:'Correspondencias: '+candidates.size};}return result;}"""

LER_ARVORE = r"""(tipo) => {
  const visible=e=>!!e.getClientRects().length;
  const all=[...document.querySelectorAll('*')];
  const re=new RegExp(tipo,'i');
  return {
    bodyText:(document.body?.innerText||'').slice(0,25000),
    canvas:all.filter(e=>e.tagName==='CANVAS').map(e=>({id:e.id,width:e.width,height:e.height})),
    shadowHosts:all.filter(e=>e.shadowRoot).map(e=>({tag:e.tagName,id:e.id})),
    drawingElements:all.filter(e=>visible(e)&&re.test(e.textContent||'')&&![...e.children].some(c=>re.test(c.textContent||''))).slice(0,30).map(e=>({tag:e.tagName,text:e.textContent.slice(0,500),html:e.outerHTML.slice(0,3000)}))
  };
}"""

LER_MENU = r"""() => {
  const visible=e=>!!e.getClientRects().length&&getComputedStyle(e).visibility!=='hidden';
  const all=[...document.querySelectorAll('*')].filter(visible);
  return {
    bodyText:(document.body?.innerText||'').slice(0,30000),
    menus:all.filter(e=>['menu','menuitem'].includes(e.getAttribute('role'))||/menu/i.test(typeof e.className==='string'?e.className:'')).slice(0,100).map(e=>({tag:e.tagName,role:e.getAttribute('role'),html:e.outerHTML.slice(0,5000)})),
    editElements:all.filter(e=>/^(Edit|Update\s+Content)(?:\s|[>›▶►]|$)/i.test((e.textContent||'').trim())&&e.textContent.length<200).slice(0,50).map(e=>({tag:e.tagName,text:e.textContent,html:e.outerHTML.slice(0,4000)}))
  };
}"""

LER_CONTROLES = ("els=>els.filter(e=>e.getClientRects().length).slice(0,300).map(e=>({tag:e.tagName,id:e.id,"
                 "role:e.getAttribute('role'),title:e.title,text:e.tagName==='INPUT'?'':e.textContent.trim().slice(0,600)}))")

TIPOS_TEXTO = ("text", "number", "search", "tel", "url", "email")
RE_AMBIENTE = re.compile(r"^[A-Z0-9_]+\.PART$")


def conferir_destino(texto: str, pn: str, tipo: str, mensagem: str = "") -> None:
    """A janela do Upload aponta para o PN do arquivo e para um DOCCAD do tipo certo? Senao, bloqueia."""
    if "Writing on existing part" not in texto or "Writing on existing object" not in texto:
        raise RuntimeError(mensagem or "Não foi possível validar o destino do Upload.")
    parte = texto.split("Writing on existing part", 1)[1].split("Writing on existing object", 1)[0]
    if {x.upper() for x in L.RE_PN.findall(parte)} != {pn.upper()}:
        raise RuntimeError(mensagem or "PN do destino não corresponde ao arquivo. Upload bloqueado.")
    if "DOCCAD" not in texto or tipo not in texto.upper():
        raise RuntimeError(mensagem or f"Destino não confirmado como DOCCAD/{tipo}. Upload bloqueado.")


def nome_do_tipo(tipo: str) -> str:
    return {"CATDRAWING": "desenho", "CATPART": "CATPart", "CATPRODUCT": "CATProduct"}.get(tipo, tipo)


class NavegadorVPM:
    """A pagina do VPM aberta no Edge. verificar() e chamado o tempo todo: levanta erro para parar."""

    def __init__(self, ctx, verificar: Callable[[], None], log: Callable[[str], None], aviso: Callable[[str], None],
                 pasta: Path = L.PASTA):
        self.ctx = ctx
        self.verificar = verificar
        self.log = log
        self.aviso = aviso
        self.pasta = pasta
        self.enviado = False  # Create ou Upload ja clicado no passo atual
        self.pics_desconectado = False

    # ------------------------------------------------------------------
    # Busca na pagina
    # ------------------------------------------------------------------
    def pagina_inicial(self):
        return self.ctx.pages[0] if self.ctx.pages else self.ctx.new_page()

    def um(self, fabrica, nome: str, timeout: float = 30, pagina=None):
        """O unico elemento visivel que a fabrica encontra. Zero ou mais de um: espera e, no fim, erro."""
        fim = time.monotonic() + timeout
        achados = []
        while time.monotonic() < fim:
            self.verificar()
            achados = []
            for pg in ([pagina] if pagina is not None else list(self.ctx.pages)):
                for fr in pg.frames:
                    try:
                        loc = fabrica(fr)
                        for n in range(loc.count()):
                            c = loc.nth(n)
                            if c.is_visible():
                                achados.append(c)
                    except Exception:  # noqa: BLE001 - frame que sumiu ou recusa a busca
                        continue
            if len(achados) == 1:
                return achados[0]
            (pagina or self.ctx.pages[0]).wait_for_timeout(250)
        raise RuntimeError(f"{nome}: {len(achados)} correspondências visíveis. Nenhum elemento foi escolhido ao acaso.")

    def texto(self, t: str, timeout: float = 30, pagina=None):
        return self.um(lambda f: f.get_by_text(t, exact=True), t, timeout, pagina)

    def botao(self, t: str):
        return self.um(lambda f: f.get_by_role("button", name=t, exact=True), t)

    def pesquisar(self, pn: str, pagina=None, timeout: float = 30) -> None:
        caixa = self.um(lambda f: f.locator("#inputdiv"), "Pesquisa", timeout, pagina)
        caixa.fill(pn)
        caixa.press("Enter")

    def conferir_pics(self) -> None:
        """O VPM mostra "PICS not connected" quando a ponte com o CATIA caiu: nada mais e enviado."""
        if self.pics_desconectado:
            raise RuntimeError("PICS desconectado. Lote interrompido.")
        for page in list(self.ctx.pages):
            for frame in page.frames:
                try:
                    achados = frame.get_by_text("PICS not connected", exact=False)
                    visto = any(achados.nth(i).is_visible() for i in range(achados.count()))
                except Exception:  # noqa: BLE001
                    continue
                if visto:
                    self.pics_desconectado = True
                    mensagem = ("PICS NÃO CONECTADO\n\nO VPM exibiu: PICS not connected. O lote foi interrompido para "
                                "impedir novos envios. Conecte o PICS pelo procedimento habitual e confira o último PN "
                                "antes de repetir. Este aviso não confirma nem desfaz um Upload anterior.")
                    self.log(mensagem)
                    self.aviso(mensagem)
                    raise RuntimeError("PICS not connected detectado no VPM. Lote interrompido.")

    def gravar(self, nome: str, dados) -> None:
        self.pasta.mkdir(parents=True, exist_ok=True)
        (self.pasta / nome).write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")

    # ------------------------------------------------------------------
    # Criacao por Duplicate
    # ------------------------------------------------------------------
    def criar_pn(self, r: dict, criar: bool, registrar: Callable[[str], None], etapa: Callable[[int, str], None]) -> str:
        """Duplicate do PN de origem, preenche e confere os 19 campos e cria (ou cancela, se criar=False)."""
        p = self.pagina_inicial()
        etapa(5, "Abrindo o VPM. Faça login se necessário.")
        p.goto(L.URL, wait_until="domcontentloaded", timeout=120000)
        self.um(lambda f: f.locator("#inputdiv"), "Aguardando login", 180, p)

        etapa(15, "Selecionando ambiente")
        desejado = r["ambiente"] + ".PART"
        nativos = []
        for fr in p.frames:
            sels = fr.locator("select")
            for j in range(sels.count()):
                sel = sels.nth(j)
                if sel.is_visible() and desejado in [v.strip() for v in sel.locator("option").all_text_contents()]:
                    nativos.append(sel)
        if len(nativos) == 1:
            nativos[0].select_option(label=desejado)
        elif len(nativos) > 1:
            raise RuntimeError("Ambiente ambíguo.")
        else:
            atual = self.um(lambda f: f.get_by_text(RE_AMBIENTE), "Tipo de pesquisa", pagina=p)
            if atual.inner_text().strip() != desejado:
                atual.click()
                self.texto(desejado, pagina=p).click()

        etapa(25, "Pesquisando origem: " + r["pn_origem"])
        self.pesquisar(r["pn_origem"], p)
        self.texto(r["pn_origem"], pagina=p).click(button="right")
        self.texto("Edit", pagina=p).hover()
        self.texto("Duplicate", pagina=p).click()
        self.texto("Select Environment", pagina=p)
        amb = re.compile("^" + re.escape(r["ambiente"]) + "$")
        self.um(lambda f: f.locator("select").filter(has=f.locator("option", has_text=amb)), "Ambiente do Duplicate",
                pagina=p).select_option(label=r["ambiente"])
        self.um(lambda f: f.get_by_role("button", name="Continue", exact=True), "Continue", pagina=p).click()
        self.texto("Part Number", pagina=p)
        p.wait_for_timeout(1500)

        etapa(40, "Validando formulário e opções")
        rotulos = list(L.CAMPOS.values())
        achados, diagnostico = [], []
        for pg in self.ctx.pages:
            for fr in pg.frames:
                mapa = fr.evaluate(DESCOBRIR_CAMPOS, rotulos)
                diagnostico.append({"frame_name": fr.name, "mapping": mapa})
                if all("error" not in mapa.get(rot, {"error": "ausente"}) for rot in rotulos):
                    achados.append((fr, mapa))
        self.gravar("diagnostico_vpm.json", diagnostico)
        if len(achados) != 1:
            raise RuntimeError("Formulário não identificado de forma única. Consulte diagnostico_vpm.json.")
        frame, mapa = achados[0]
        p = frame.page
        plano = []
        for chave, rotulo in L.CAMPOS.items():
            meta, opcao = mapa[rotulo], None
            if meta.get("disabled") or meta.get("readonly"):
                raise RuntimeError("Campo bloqueado: " + rotulo)
            if meta["tag"] == "SELECT":
                opcoes = [o for o in meta["options"] if L.normalizar(o["text"]) == L.normalizar(r[chave])]
                if len(opcoes) != 1:
                    raise RuntimeError(f"Opção inválida em {rotulo}: {r[chave]!r}. Disponíveis: {[o['text'] for o in meta['options']]}")
                opcao = opcoes[0]["value"]
            elif meta["tag"] != "TEXTAREA" and meta.get("type") not in TIPOS_TEXTO:
                raise RuntimeError("Controle não suportado: " + rotulo)
            plano.append((chave, rotulo, meta, opcao))

        etapa(55, "Preenchendo e conferindo atributos")
        for chave, rotulo, meta, opcao in plano:
            self.verificar()
            c = frame.locator('[data-vpm-test="%s"]' % meta["token"])
            if opcao is not None:
                c.select_option(value=opcao)
                valido = L.normalizar(c.locator("option:checked").inner_text().strip()) == L.normalizar(r[chave])
            else:
                c.fill(r[chave])
                c.press("Tab")
                valido = c.input_value().strip() == r[chave]
            if not valido:
                raise RuntimeError("Leitura divergente em " + rotulo + ". Revise o formulário.")

        campo_pn = frame.locator('[data-vpm-test="vpm-test-0"]')
        if not criar:
            self._botao_do_formulario(campo_pn, "Cancel", "Lote interrompido sem criar.").click()
            campo_pn.wait_for(state="hidden", timeout=15000)
            return "Formulário preenchido e conferido; cancelado SEM criar."

        etapa(75, "Criando PN: " + r["part_number"])
        if campo_pn.input_value().strip() != r["part_number"]:
            raise RuntimeError("PN divergente. Create bloqueado.")
        create = self._botao_do_formulario(campo_pn, "Create", "Create bloqueado.")
        if not create.is_enabled():
            raise RuntimeError("Create não disponível.")
        self.verificar()
        registrar("ENVIO_INICIADO")
        self.enviado = True
        self.log("Enviando Create UMA VEZ. Não repetir automaticamente.")
        create.click(timeout=15000)
        campo_pn.wait_for(state="hidden", timeout=60000)

        etapa(90, "Pesquisando novo PN: " + r["part_number"])
        self.pesquisar(r["part_number"], p)
        pn = r["part_number"]
        linha = self.um(lambda f: f.get_by_role("row").filter(has=f.get_by_text(pn, exact=True)), "Resultado do PN novo", 60, p)
        texto = linha.inner_text().strip()
        self.log(texto)
        self.gravar("resultado_criacao_vpm.json", {"pn": pn, "resultado": "localizado_apos_create", "linha_vpm": texto})
        registrar("CONFIRMADO")
        return "PN criado e localizado no VPM: " + pn

    @staticmethod
    def _botao_do_formulario(campo, nome: str, depois: str):
        """O botao do mesmo formulario do campo PN: sobe pelos pais ate achar um so."""
        escopo = campo
        for _ in range(16):
            escopo = escopo.locator("..")
            if escopo.count() != 1:
                break
            botoes = escopo.get_by_role("button", name=nome, exact=True)
            visiveis = [botoes.nth(i) for i in range(botoes.count()) if botoes.nth(i).is_visible()]
            if len(visiveis) == 1:
                return visiveis[0]
            if len(visiveis) > 1:
                raise RuntimeError(f"{nome} ambíguo no formulário. {depois}")
        raise RuntimeError(f"{nome} não encontrado no formulário. {depois}")

    # ------------------------------------------------------------------
    # Update Content
    # ------------------------------------------------------------------
    def preparar_upload(self, ambiente: str) -> None:
        p = self.pagina_inicial()
        p.goto(L.URL, wait_until="domcontentloaded", timeout=120000)
        self.um(lambda f: f.locator("#inputdiv"), "Aguardando VPM", 180)
        desejado = ambiente + ".PART"
        atual = self.um(lambda f: f.get_by_text(RE_AMBIENTE), "Ambiente de pesquisa")
        if atual.inner_text().strip() != desejado:
            atual.click()
            self.texto(desejado).click()

    @staticmethod
    def abrir_documento(cat, caminho: str):
        """Usa o documento ja aberto no CATIA ou abre. Precisa estar ativo e salvo."""
        alvo = os.path.normcase(os.path.abspath(caminho))
        doc = None
        for i in range(1, cat.Documents.Count + 1):
            d = cat.Documents.Item(i)
            try:
                if os.path.normcase(os.path.abspath(d.FullName)) == alvo:
                    doc = d
                    break
            except Exception:  # noqa: BLE001 - documento sem arquivo, aberto pelo VPM
                pass
        if doc is None:
            doc = cat.Documents.Open(caminho)
        doc.Activate()
        if os.path.normcase(os.path.abspath(cat.ActiveDocument.FullName)) != alvo:
            raise RuntimeError("Documento ativo diferente do arquivo esperado.")
        if not doc.Saved:
            raise RuntimeError("O documento tem alterações não salvas. Salve ou revise no CATIA e execute novamente.")
        return doc

    def update_content(self, cat, f: dict, confirmar: Callable[[str], None], registrar: Callable[[dict], None]) -> None:
        """Update Content de um arquivo no documento DOCCAD do PN. f['status'] termina CONFIRMADO_PELO_USUARIO."""
        tipo, pn = f["kind"], f["pn"]
        nome = nome_do_tipo(tipo)
        doc = self.abrir_documento(cat, f["arquivo"])
        self.log("CATIA ativo: " + str(doc.Name) + " | destino: " + pn)
        self.pesquisar(pn, timeout=180)
        self.texto(pn).dblclick()
        self.log(f"Expandindo filhos da Part e aguardando o {tipo}...")
        self.um(lambda fr: fr.locator('button[title="Expand all children"]'), "Expand all children").click()
        self.verificar()
        rotulo = re.compile(r"^\s*" + tipo + r"\s*\d+\b", re.I)
        try:
            documento = self.um(lambda fr: fr.get_by_text(rotulo), f"Documento {tipo} na árvore", timeout=60)
        except RuntimeError:
            self.verificar()
            self.diagnostico_arvore(tipo)
            confirmar(f"A árvore abriu, mas o {nome} não foi localizado pelo HTML. Nenhum Upload foi enviado.\n"
                      f"No VPM, confira o PN {pn} e faça SOMENTE: botão direito no {tipo} > Edit > Update Content.\n"
                      "Pare na janela Source = CATIA V5. Depois clique Sim aqui para continuar.\n"
                      "Esta etapa é manual; não clique em Upload.")
        else:
            documento.click()
            self.verificar()
            self.log(f"{tipo} selecionado com clique esquerdo; abrindo o menu de contexto.")
            documento.click(button="right")
            self.verificar()
            try:
                edit = self.um(lambda fr: fr.get_by_text(re.compile(r"^\s*Edit\s*[>›▶►]?\s*$", re.I)),
                               "Edit no menu de contexto", timeout=8)
                edit.hover()
                self.um(lambda fr: fr.get_by_text(re.compile(r"^\s*Update\s+Content\s*$", re.I)), "Update Content",
                        timeout=10).click()
                self.verificar()
            except RuntimeError:
                self.verificar()
                self.diagnostico_menu()
                confirmar(f"O {tipo} foi localizado, mas o menu Edit/Update Content não foi identificado. "
                          "Nenhum Upload foi enviado.\n"
                          f"Abra manualmente SOMENTE Edit > Update Content no {nome} do PN {pn}.\n"
                          "Pare na janela Source = CATIA V5 e clique Sim aqui para continuar.\n"
                          "Não clique em Upload nesta etapa.")

        source = self.um(lambda fr: fr.locator("select").filter(has=fr.locator("option", has_text=re.compile(r"^CATIA V5$"))),
                         "Source CATIA V5")
        source.select_option(label="CATIA V5")
        self._clicar_edit_da_janela_source(source)
        self.verificar()
        self.texto("Select the Document")
        upload = self.botao("Upload")
        escopo, alvo = upload, None
        for _ in range(14):
            escopo = escopo.locator("..")
            if escopo.count() != 1:
                break
            t = escopo.inner_text()
            if "Writing on existing part" in t and "Writing on existing object" in t:
                alvo = escopo
                break
        if alvo is None:
            raise RuntimeError("Não foi possível validar o destino do Upload.")
        conferir_destino(alvo.inner_text(), pn, tipo)
        caixas = alvo.get_by_role("checkbox", name="Save as New Document", exact=True)
        if caixas.count() != 1:
            raise RuntimeError("Save as New Document não identificado. Upload bloqueado.")
        if caixas.is_checked():
            caixas.uncheck()
        # Selecao pelo COM e uma tentativa: nao prova que a ponte do VPM reconheceu o documento.
        doc.Activate()
        try:
            doc.Selection.Clear()
            doc.Selection.Add(doc)
        except Exception as exc:  # noqa: BLE001
            self.log("Seleção pelo CATIA não aceita: " + str(exc))
        confirmar(f"Confira no CATIA o {nome} {Path(f['arquivo']).name} e, se a ponte pedir, selecione o documento.\n"
                  f"Destino validado no VPM: {pn}\nConfirma enviar Upload para esse destino?")
        if os.path.normcase(cat.ActiveDocument.FullName) != os.path.normcase(f["arquivo"]):
            raise RuntimeError("O documento ativo no CATIA mudou. Upload bloqueado.")
        if not doc.Saved:
            raise RuntimeError("Documento alterado depois da validação. Upload bloqueado.")
        conferir_destino(alvo.inner_text(), pn, tipo, "Destino mudou. Upload bloqueado.")
        if caixas.is_checked():
            raise RuntimeError("Save as New Document marcado. Upload bloqueado.")
        self.verificar()
        f["status"] = "ENVIO_INICIADO"
        registrar(f)
        self.enviado = True
        upload.click(timeout=15000)
        self.verificar()
        confirmar(f"O Upload foi acionado UMA VEZ para {pn}.\nVerifique o resultado no VPM e eventuais mensagens.\n"
                  "Se houver Commit obrigatório, conclua manualmente.\n"
                  "Clique Sim SOMENTE se a atualização terminou corretamente; Não interrompe o lote como resultado incerto.")
        f["status"] = "CONFIRMADO_PELO_USUARIO"
        registrar(f)

    @staticmethod
    def _clicar_edit_da_janela_source(source) -> None:
        """O Edit da mesma janela do Source, que tambem tem Cancel: assim nao e o Edit de um menu."""
        escopo = source
        for _ in range(14):
            escopo = escopo.locator("..")
            if escopo.count() != 1:
                break
            edits = escopo.get_by_role("button", name="Edit", exact=True)
            cancels = escopo.get_by_role("button", name="Cancel", exact=True)
            v_edits = [edits.nth(i) for i in range(edits.count()) if edits.nth(i).is_visible()]
            v_cancels = [cancels.nth(i) for i in range(cancels.count()) if cancels.nth(i).is_visible()]
            if len(v_edits) == 1 and len(v_cancels) == 1:
                if not v_edits[0].is_enabled():
                    raise RuntimeError("Edit da janela Source desabilitado. Nada enviado.")
                v_edits[0].click()
                return
            if len(v_edits) > 1:
                break
        raise RuntimeError("Edit não identificado de forma única dentro da janela Source. Nenhum Upload enviado.")

    # ------------------------------------------------------------------
    # Diagnosticos: o que a pagina mostrava quando algo nao foi encontrado
    # ------------------------------------------------------------------
    def _por_frame(self, nome_arquivo: str, ler) -> None:
        dados = []
        for pi, pg in enumerate(self.ctx.pages):
            for fi, fr in enumerate(pg.frames):
                try:
                    dados.append({"page": pi, "frame_index": fi, "frame_name": fr.name, "estrutura": ler(fr)})
                except Exception as exc:  # noqa: BLE001
                    dados.append({"page": pi, "frame_index": fi, "erro": str(exc)})
        self.gravar(nome_arquivo, dados)

    def diagnostico_arvore(self, tipo: str) -> None:
        self._por_frame("diagnostico_arvore_vpm.json", lambda fr: fr.evaluate(LER_ARVORE, tipo))
        self.log("Estrutura da árvore salva em diagnostico_arvore_vpm.json. Seleção manual solicitada; nenhum Upload enviado.")

    def diagnostico_menu(self) -> None:
        self._por_frame("diagnostico_menu_vpm.json", lambda fr: fr.evaluate(LER_MENU))
        self.log("Menu salvo em diagnostico_menu_vpm.json. Nenhum Upload enviado nesta etapa.")

    def diagnostico(self) -> None:
        dados = []
        for pg in list(self.ctx.pages):
            for fr in pg.frames:
                try:
                    dados.append({"frame": fr.name, "controles": fr.locator(
                        "button,input,select,[role=treeitem],[role=row]").evaluate_all(LER_CONTROLES)})
                except Exception:  # noqa: BLE001
                    pass
        self.gravar("diagnostico_update_content.json", dados)
