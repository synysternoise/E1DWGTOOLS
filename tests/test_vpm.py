"""Aba VPM sem o VPM: Excel, PN no nome do arquivo, plano, destino do Upload e o lote com um VPM simulado.

Uso:  python -m unittest discover -s tests
"""
import base64
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from engine import vpm_lote as L  # noqa: E402
from engine.vpm_execucao import ExecucaoVPM  # noqa: E402
from engine.vpm_web import conferir_destino  # noqa: E402

try:
    import openpyxl
except ModuleNotFoundError:  # o teste do Excel so roda com a biblioteca
    openpyxl = None


def linha_valida(**mudar):
    base = {"executar": "SIM", "pn_origem": "171-11111-001", "ambiente": "EGN2ENG", "part_number": "171-22222-001",
            "part_instance": "1", "conc_version": "1", "conf_type": "A", "english_description": "PANEL",
            "portuguese_description": "PAINEL", "type": "P", "origin": "M", "production": "S", "design": "E",
            "calculated_weight_g": "12.5", "ata_code": "25", "dbt_code": "X", "drawing_class": "C", "class": "1",
            "status": "D", "cpl": "N", "type_program": "E1", "traceability": "N"}
    base.update(mudar)
    return base


def tabela(*linhas):
    cab = list(L.OBRIGATORIAS)
    return cab, [tuple(l.get(c) for c in cab) for l in linhas]


class Excel(unittest.TestCase):
    def test_linha_valida_e_nao_ignorada(self):
        cab, linhas = tabela(linha_valida(conc_version="2.0"), linha_valida(executar="NAO", part_number="x"))
        saida = L.validar_linhas(cab, linhas)
        self.assertEqual(len(saida), 1)
        self.assertEqual(saida[0]["conc_version"], "2")
        self.assertEqual(saida[0]["_linha"], 2)

    def test_erros_do_lote_juntos(self):
        cab, linhas = tabela(
            linha_valida(), linha_valida(),  # PN repetido
            linha_valida(part_number="171-11111-001"),  # igual a origem
            linha_valida(part_number="171-33333-001", calculated_weight_g="-1", conc_version="1.5"),
        )
        with self.assertRaises(ValueError) as erro:
            L.validar_linhas(cab, linhas)
        texto = str(erro.exception)
        self.assertIn("PN destino repetido", texto)
        self.assertIn("igual à origem", texto)
        self.assertIn("peso", texto)
        self.assertIn("Conc. Version", texto)

    def test_coluna_faltando(self):
        with self.assertRaises(ValueError) as erro:
            L.validar_linhas(["executar", "pn_origem"], [])
        self.assertIn("Colunas ausentes", str(erro.exception))

    def test_nenhuma_linha_sim(self):
        cab, linhas = tabela(linha_valida(executar="NAO"))
        with self.assertRaises(ValueError):
            L.validar_linhas(cab, linhas)

    @unittest.skipIf(openpyxl is None, "openpyxl nao instalado")
    def test_le_arquivo_e_modelo(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = os.path.join(pasta, "lote.xlsx")
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = L.ABA_EXCEL
            cab, linhas = tabela(linha_valida())
            ws.append(cab)
            for l in linhas:
                ws.append(list(l))
            wb.save(caminho)
            self.assertEqual(L.ler_excel(caminho)[0]["part_number"], "171-22222-001")

            vazio = os.path.join(pasta, "modelo.xlsx")
            L.salvar_modelo_vazio(Path(caminho), vazio)
            ws2 = openpyxl.load_workbook(vazio)[L.ABA_EXCEL]
            self.assertEqual(ws2["A1"].value, "executar")
            self.assertEqual(ws2["A2"].value, "NAO")
            self.assertIsNone(ws2["D2"].value)

            # O modelo sai da macro antiga sem executar o arquivo.
            macro = os.path.join(pasta, "vpm_tools.py")
            dados = Path(caminho).read_bytes()
            Path(macro).write_text("raise SystemExit('nao pode rodar')\nTEMPLATE_BASE64='"
                                   + base64.b64encode(dados).decode() + "'\n", encoding="utf-8")
            self.assertEqual(L.extrair_modelo_da_macro(macro), dados)


class Arquivos(unittest.TestCase):
    def test_pn_do_arquivo(self):
        self.assertEqual(L.pn_do_arquivo("171-52382-001.CATDrawing"), "171-52382-001")
        self.assertEqual(L.pn_do_arquivo("spd171-52382-001_rev.CATPart"), "SPD171-52382-001")
        self.assertEqual(L.pn_do_arquivo("171-52382ABC-001.CATProduct"), "171-52382ABC-001")
        self.assertEqual(L.pn_do_arquivo("171-52382-001 e 171-52382-002.CATDrawing"), "")
        self.assertEqual(L.pn_do_arquivo("desenho.CATDrawing"), "")

    def test_plano_upload_e_sequencia(self):
        with tempfile.TemporaryDirectory() as pasta:
            for nome in ("171-22222-001.CATDrawing", "171-22222-001.CATPart", "outro.txt"):
                Path(pasta, nome).write_bytes(b"conteudo " + nome.encode())
            plano = L.montar_plano(L.MODO_UPLOAD, "", pasta, ["CATDRAWING", "CATPART"], "EGN2ENG")
            self.assertEqual(sorted(r["files"][0]["kind"] for r in plano), ["CATDRAWING", "CATPART"])
            self.assertTrue(all(len(r["files"][0]["sha256"]) == 64 for r in plano))
            self.assertTrue(all(r["criacao"] == "NAO_SOLICITADA" for r in plano))

            with self.assertRaises(ValueError):
                L.montar_plano(L.MODO_UPLOAD, "", pasta, ["CATDRAWING"], "egn 2")

            Path(pasta, "171-99999-001.CATDrawing").write_bytes(b"x")
            Path(pasta, "171-99999-001_copia.CATDrawing").write_bytes(b"y")
            with self.assertRaises(ValueError) as erro:
                L.montar_plano(L.MODO_UPLOAD, "", pasta, ["CATDRAWING"], "EGN2ENG")
            self.assertIn("duplicado", str(erro.exception))


class Destino(unittest.TestCase):
    TEXTO = "Writing on existing part 171-22222-001 A Writing on existing object DOCCAD CATDrawing 1"

    def test_destino_certo(self):
        conferir_destino(self.TEXTO, "171-22222-001", "CATDRAWING")

    def test_destino_errado(self):
        with self.assertRaises(RuntimeError):
            conferir_destino(self.TEXTO, "171-22222-002", "CATDRAWING")
        with self.assertRaises(RuntimeError):
            conferir_destino(self.TEXTO, "171-22222-001", "CATPART")
        with self.assertRaises(RuntimeError):
            conferir_destino(self.TEXTO.replace("DOCCAD", "DOC"), "171-22222-001", "CATDRAWING")
        with self.assertRaises(RuntimeError) as erro:
            conferir_destino("nada", "171-22222-001", "CATDRAWING", "Destino mudou.")
        self.assertEqual(str(erro.exception), "Destino mudou.")


class NavFalso:
    def __init__(self, falhar_depois_do_create=False):
        self.enviado = False
        self.falhar = falhar_depois_do_create
        self.criados, self.enviados, self.ambientes = [], [], []

    def conferir_pics(self):
        pass

    def criar_pn(self, linha, criar, registrar, etapa):
        etapa(50, "meio")
        if not criar:
            return "cancelado"
        registrar("ENVIO_INICIADO")
        self.enviado = True
        if self.falhar:
            raise RuntimeError("caiu depois do Create")
        registrar("CONFIRMADO")
        self.criados.append(linha["part_number"])
        return "criado"

    def preparar_upload(self, ambiente):
        self.ambientes.append(ambiente)

    def update_content(self, cat, f, confirmar, registrar):
        f["status"] = "ENVIO_INICIADO"
        registrar(f)
        self.enviado = True
        confirmar("terminou?")
        f["status"] = "CONFIRMADO_PELO_USUARIO"
        registrar(f)
        self.enviados.append((f["pn"], f["kind"]))

    def diagnostico(self):
        pass


class AvisosFalsos:
    def __init__(self, resposta=True):
        self.resposta = resposta
        self.perguntas, self.logs = [], []
        self.execucao = None

    def log(self, t):
        self.logs.append(t)

    def mudou(self, i, linha):
        pass

    def progresso(self, p):
        pass

    def perguntar(self, t):
        self.perguntas.append(t)
        self.execucao.responder(self.resposta)

    def aviso(self, t):
        pass

    def terminou(self, ok, m):
        pass


class Lote(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.pasta = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def plano(self, pns, tipos=()):
        plano = []
        for pn in pns:
            arquivos = []
            for tipo in tipos:
                caminho = self.pasta / f"{pn}.{tipo}"
                caminho.write_bytes(pn.encode() + tipo.encode())
                arquivos.append({"pn": pn, "arquivo": str(caminho), "kind": tipo, "status": "PENDENTE",
                                 "sha256": L.sha256_do_arquivo(str(caminho))})
            plano.append({"pn": pn, "ambiente": "EGN2ENG", "creation": linha_valida(part_number=pn), "files": arquivos,
                          "criacao": "PENDENTE", "conteudo": "PENDENTE" if arquivos else "NAO_SOLICITADO", "mensagem": ""})
        return plano

    def rodar(self, plano, nav=None, criar=True, resposta=True):
        avisos = AvisosFalsos(resposta)
        ex = ExecucaoVPM(plano, L.MODO_SEQUENCIA, avisos, criar, self.pasta)
        avisos.execucao = ex
        ex.nav = nav or NavFalso()
        ok, msg = ex.executar_plano(cat=None)
        return ex, ok, msg, avisos

    def historico(self, nome):
        return json.loads((self.pasta / nome).read_text(encoding="utf-8"))

    def test_sequencia_cria_e_atualiza_e_nao_repete(self):
        ex, ok, _msg, avisos = self.rodar(self.plano(["171-22222-001"], ["CATDRAWING", "CATPART"]))
        self.assertTrue(ok)
        self.assertEqual(ex.plano[0]["criacao"], "CONFIRMADO")
        self.assertEqual(ex.nav.enviados, [("171-22222-001", "CATDRAWING"), ("171-22222-001", "CATPART")])
        self.assertTrue(any("3D EXPERIMENTAL" in p for p in avisos.perguntas))
        self.assertEqual(self.historico(L.HISTORICO_CRIACAO)["EGN2ENG|171-22222-001"]["status"], "CONFIRMADO")
        self.assertEqual(len(self.historico(L.HISTORICO_UPLOAD)), 2)

        ex2, ok2, _m, _a = self.rodar(self.plano(["171-22222-001"], ["CATDRAWING", "CATPART"]))
        self.assertTrue(ok2)
        self.assertEqual(ex2.plano[0]["criacao"], "CONFIRMADO_HISTORICO_LOCAL")
        self.assertEqual(ex2.nav.criados, [])
        self.assertEqual(ex2.nav.enviados, [])
        self.assertTrue(all(f["status"] == "IGNORADO_HISTORICO_LOCAL" for f in ex2.plano[0]["files"]))

    def test_falha_depois_do_create_fica_incerta_e_bloqueia(self):
        ex, ok, _m, _a = self.rodar(self.plano(["171-22222-001", "171-22222-002"], ["CATDRAWING"]),
                                    NavFalso(falhar_depois_do_create=True))
        self.assertFalse(ok)
        self.assertEqual(ex.plano[0]["criacao"], "CRIACAO_INCERTA")
        self.assertEqual(ex.plano[0]["conteudo"], "NAO_EXECUTADO")
        self.assertEqual(ex.plano[1]["criacao"], "NAO_EXECUTADO")
        ex2, ok2, msg2, _a = self.rodar(self.plano(["171-22222-001"]))
        self.assertFalse(ok2)
        self.assertIn("incerta", msg2)
        self.assertEqual(ex2.plano[0]["criacao"], "REVISAO_NECESSARIA")

    def test_arquivo_mudou_depois_da_previa(self):
        plano = self.plano(["171-22222-001"], ["CATDRAWING"])
        Path(plano[0]["files"][0]["arquivo"]).write_bytes(b"mudou")
        ex, ok, msg, _a = self.rodar(plano)
        self.assertFalse(ok)
        self.assertIn("alterado", msg)
        self.assertEqual(ex.nav.criados, [])

    def test_confirmacao_recusada_deixa_upload_incerto(self):
        ex, ok, _m, _a = self.rodar(self.plano(["171-22222-001"], ["CATDRAWING"]), resposta=False)
        self.assertFalse(ok)
        self.assertEqual(ex.plano[0]["conteudo"], "UPLOAD_INCERTO")
        hist = self.historico(L.HISTORICO_UPLOAD)
        self.assertEqual(list(hist.values())[0]["status"], "ENVIO_INICIADO")
        # Com o envio sem confirmacao no historico, o proximo lote para antes de enviar de novo.
        plano = self.plano(["171-22222-001"], ["CATDRAWING"])
        plano[0]["creation"] = None
        ex2, ok2, msg2, _a = self.rodar(plano)
        self.assertFalse(ok2)
        self.assertIn("Upload anterior incerto", msg2)
        self.assertEqual(ex2.nav.enviados, [])

    def test_so_conferir_nao_toca_no_historico(self):
        ex, ok, _m, _a = self.rodar(self.plano(["171-22222-001"]), criar=False)
        self.assertTrue(ok)
        self.assertEqual(ex.plano[0]["criacao"], "VALIDADO_SEM_CRIAR")
        self.assertFalse((self.pasta / L.HISTORICO_CRIACAO).exists())

    def test_interromper(self):
        avisos = AvisosFalsos()
        ex = ExecucaoVPM(self.plano(["171-22222-001"]), L.MODO_CRIAR, avisos, True, self.pasta)
        avisos.execucao = ex
        ex.nav = NavFalso()
        ex.parar.set()
        ok, msg = ex.executar_plano(None)
        self.assertFalse(ok)
        self.assertIn("Interrompido", msg)

    def test_historico_ilegivel_nao_comeca(self):
        (self.pasta / L.HISTORICO_UPLOAD).write_text("{quebrado", encoding="utf-8")
        with self.assertRaises(ValueError):
            ExecucaoVPM(self.plano(["171-22222-001"]), L.MODO_CRIAR, AvisosFalsos(), True, self.pasta)


if __name__ == "__main__":
    unittest.main()
