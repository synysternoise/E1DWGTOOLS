"""Verificador do E1 Tools. Confere a instalacao, instala o que faltar e diz o que fazer.

Uso:  python verificar.py

Nao mexe no CATIA nem nos desenhos. Pode rodar quantas vezes precisar.

Com as macros do CATIA travadas:  python verificar.py --catia
Mostra o estado do CATIA, tira a selecao e religa alertas, tela e interacao. O desenho nao muda.
"""
import hashlib
import os
import re
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
PYTHON_MINIMO = (3, 10)
PIP_MINIMO = 24
BIBLIOTECAS = ("pywin32", "PySide6-Essentials")
IMPORTS = (
    ("pywin32", "import pythoncom, win32com.client"),
    ("PySide6-Essentials", "from PySide6 import QtCore, QtGui, QtSvg, QtWidgets"),
)
GITHUB = "https://github.com/synysternoise/E1DWGTOOLS/blob/migracao-dwgtools/"
PASTAS_IGNORADAS = {".venv", "venv", ".idea", ".git", "__pycache__", "E1tools"}

# Gerado com:  python verificar.py --manifesto
# arquivo: (linhas, assinatura)
MANIFESTO = {
    "main_qt.py": (18, 'e0f9ec4ebdcefb2e'),
    "src/engine/catia_bridge.py": (138, 'f6d41732974241a7'),
    "src/engine/font_check.py": (299, '067b23b7a20d700b'),
    "src/engine/fix_flags.py": (272, 'aab35321882e9640'),
    "src/engine/atualizar_template.py": (1283, '41f70ad8cde66900'),
    "src/engine/pos_zone.py": (1152, '23e278610959b4dd'),
    "src/engine/symbol_shape.py": (65, 'b3789405193e3595'),
    "src/engine/splits.py": (421, '1355a489c548390e'),
    "src/engine/part_list.py": (329, '0ba1c0b77078656a'),
    "src/engine/compare_dwg.py": (68, '8191ae9f49b2c46e'),
    "src/engine/template_check.py": (485, '1df75022e737f7db'),
    "src/engine/catia_scripts/font_check.catvbs": (416, 'd63899c71076bbed'),
    "src/engine/catia_scripts/fix_flags.catvbs": (806, '71db4441b9277b8e'),
    "src/engine/catia_scripts/symbol_shape.catvbs": (72, 'ab983ca8d9661894'),
    "src/engine/catia_scripts/pos_zone.catvbs": (366, 'cf49bbddb7037871'),
    "src/ui_qt/theme.py": (173, 'dc78f0ebe5b5e9bc'),
    "src/ui_qt/voo.py": (339, 'de6d17cfa8f8b742'),
    "src/ui_qt/icones.py": (85, '89eab1825e9374f3'),
    "src/ui_qt/catia_worker.py": (522, '892fd55d4ac42e0d'),
    "src/ui_qt/font_size_page.py": (464, '9e339e7165417d03'),
    "src/ui_qt/pecas.py": (226, '75ca9e75bdb7d59b'),
    "src/ui_qt/tool_page.py": (360, '8ccf6e2250356af3'),
    "src/ui_qt/fix_flags_page.py": (501, 'ba375a377209a63a'),
    "src/ui_qt/tool_pages.py": (372, 'a5cc1446f4be080f'),
    "src/ui_qt/sequencia_page.py": (595, '3a229102ed4eae85'),
    "src/ui_qt/check_fix_pages.py": (711, '3875eb8c5ac2e4a9'),
    "src/ui_qt/poszone_page.py": (785, '7ae7c3b8d68b8611'),
    "src/ui_qt/hub_window.py": (891, 'd8042cb0e71d9c0f'),
}

REDE = re.compile(
    r"ProxyError|SSLError|CERTIFICATE_VERIFY_FAILED|ConnectTimeout|ConnectionError|Max retries|"
    r"getaddrinfo|Temporary failure|Proxy Authentication|No matching distribution|Could not find a version",
    re.I,
)
PERMISSAO = re.compile(r"Permission denied|Access is denied|Acesso negado|WinError 5\b", re.I)

TESTE_TELA = r"""
import os, sys, time
pasta = sys.argv[1]
sys.path.insert(0, os.path.join(pasta, "src"))
from PySide6.QtCore import QCoreApplication, QEventLoop
from PySide6.QtWidgets import QApplication
from ui_qt.hub_window import HubWindow
app = QApplication([])
j = HubWindow()
j.show()
fim = time.perf_counter() + 2
while time.perf_counter() < fim:
    QCoreApplication.processEvents(QEventLoop.AllEvents, 50)
for nome in list(j.pills):
    j.pills[nome].click()
    QCoreApplication.processEvents()
raiz = os.path.normcase(pasta)
fora = [m.__name__ for m in list(sys.modules.values())
        if m.__name__.split(".")[0] in ("engine", "ui_qt") and getattr(m, "__file__", None)
        and not os.path.normcase(m.__file__).startswith(raiz)]
if fora:
    raise RuntimeError("Modulos vindos de outra pasta: " + ", ".join(fora))
print("TELAS", j._pages.count(), flush=True)
sys.stdout.flush()
os._exit(0)
"""

TESTE_CATIA = """
import win32com.client
try:
    win32com.client.GetActiveObject("CATIA.Application")
    print("ABERTO")
except Exception:
    print("FECHADO")
"""


def assinatura(dados: bytes) -> tuple:
    """Linhas e assinatura do conteudo. Ignora o que o editor muda ao salvar, sem mudar o codigo."""
    if dados.startswith(b"\xef\xbb\xbf"):
        dados = dados[3:]
    linhas = [l.rstrip(b" \t\r") for l in dados.split(b"\n")]
    while linhas and not linhas[-1]:
        linhas.pop()
    return len(linhas), hashlib.sha256(b"\n".join(linhas)).hexdigest()[:16]


def ok(texto: str) -> None:
    print(f"[OK]    {texto}", flush=True)


def erro(texto: str) -> None:
    print(f"[ERRO]  {texto}", flush=True)


def aviso(texto: str) -> None:
    print(f"[AVISO] {texto}", flush=True)


def rodar(args: list, timeout: int = 300) -> tuple:
    """Devolve (codigo de saida, texto). Nunca fica preso nem levanta excecao."""
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    try:
        r = subprocess.run(args, cwd=AQUI, env=env, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 124, "O teste nao terminou e foi interrompido."
    except OSError as exc:
        return 1, str(exc)
    return r.returncode, (r.stdout + r.stderr).decode("utf-8", "replace")


def ultimas(texto: str, n: int = 6) -> str:
    linhas = [l for l in texto.strip().splitlines() if l.strip()]
    return "\n".join("        " + l for l in linhas[-n:])


def procurar_em_outra_pasta(nome: str) -> str:
    for raiz, pastas, arquivos in os.walk(AQUI):
        pastas[:] = [p for p in pastas if p not in PASTAS_IGNORADAS]
        if nome in arquivos:
            return os.path.relpath(os.path.join(raiz, nome), AQUI)
    return ""


def conferir_python() -> bool:
    versao = ".".join(str(v) for v in sys.version_info[:3])
    if sys.version_info[:2] < PYTHON_MINIMO:
        erro(f"Python {versao} é antigo demais. Precisa de 3.10 ou mais novo.")
        return False
    ok(f"Python {versao} ({sys.executable})")
    return True


def conferir_arquivos() -> list:
    """Devolve a lista do que esta errado, cada item com o arquivo e o que fazer."""
    problemas = []
    for relativo, (linhas, assinado) in MANIFESTO.items():
        caminho = os.path.join(AQUI, *relativo.split("/"))
        destino = relativo.replace("/", "\\")
        link = GITHUB + relativo
        if not os.path.isfile(caminho):
            outro = procurar_em_outra_pasta(os.path.basename(caminho))
            if outro:
                problemas.append(f"{destino}: está em {outro}. Mova para a pasta certa.")
            else:
                problemas.append(f"{destino}: não existe. Crie e cole de:\n        {link}")
            continue
        with open(caminho, "rb") as f:
            dados = f.read()
        try:
            dados.decode("utf-8")
        except UnicodeDecodeError:
            problemas.append(f"{destino}: salvo na codificação errada. Salve como UTF-8.")
            continue
        n, a = assinatura(dados)
        if n != linhas:
            problemas.append(f"{destino}: tem {n} linhas e devia ter {linhas}. Cole de novo de:\n        {link}")
        elif a != assinado:
            problemas.append(f"{destino}: o conteúdo está diferente. Cole de novo de:\n        {link}")
    return problemas


def biblioteca_falhando() -> dict:
    """Devolve {biblioteca: texto do erro} para o que nao carrega."""
    falhas = {}
    for nome, comando in IMPORTS:
        codigo, texto = rodar([sys.executable, "-c", comando], 120)
        if codigo != 0:
            falhas[nome] = texto
    return falhas


def preparar_pip() -> bool:
    """Um pip antigo quebra em Python novo. O proprio Python traz um novo, sem precisar de internet."""
    codigo, texto = rodar([sys.executable, "-m", "pip", "--version"], 120)
    achado = re.search(r"pip (\d+)", texto)
    if codigo == 0 and achado and int(achado.group(1)) >= PIP_MINIMO:
        return True
    print("        Atualizando o pip...", flush=True)
    codigo, texto = rodar([sys.executable, "-m", "ensurepip", "--upgrade"], 300)
    if codigo != 0:
        erro("Não consegui atualizar o pip:")
        print(ultimas(texto), flush=True)
        return False
    return True


def instalar() -> bool:
    if not preparar_pip():
        return False
    print("        Instalando as bibliotecas...", flush=True)
    args = [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "--no-input",
            "--retries", "2", "--timeout", "30", *BIBLIOTECAS]
    codigo, texto = rodar(args, 1800)
    if codigo == 0:
        return True
    if REDE.search(texto):
        erro("A internet ou a rede da empresa bloqueou o download.")
        print("        Peça à TI para liberar pypi.org e files.pythonhosted.org,", flush=True)
        print("        ou para instalar pywin32 e PySide6-Essentials nesse Python.", flush=True)
    elif PERMISSAO.search(texto):
        erro("O Windows não deu permissão para instalar nessa pasta.")
    else:
        erro("A instalação falhou:")
    print(ultimas(texto), flush=True)
    return False


def conferir_bibliotecas() -> bool:
    falhas = biblioteca_falhando()
    faltando = [n for n, t in falhas.items() if "ModuleNotFoundError" in t]
    if faltando:
        aviso(f"Faltam bibliotecas: {', '.join(faltando)}")
        if not instalar():
            return False
        falhas = biblioteca_falhando()
    if falhas:
        for nome, texto in falhas.items():
            erro(f"{nome} está instalado, mas não carrega:")
            print(ultimas(texto, 3), flush=True)
            if "DLL load failed" in texto:
                print("        Peça à TI para instalar o Microsoft Visual C++ Redistributable.", flush=True)
        return False
    ok("Bibliotecas pywin32 e PySide6 carregam")
    return True


def conferir_tela() -> bool:
    print("        Abrindo a janela do HUB para testar...", flush=True)
    codigo, texto = rodar([sys.executable, "-c", TESTE_TELA, AQUI], 180)
    achado = re.search(r"TELAS (\d+)", texto)
    if codigo != 0 or not achado:
        erro("O HUB não abriu:")
        print(ultimas(texto), flush=True)
        return False
    ok(f"O HUB abre, com {achado.group(1)} telas")
    return True


def informar_programas() -> None:
    _, texto = rodar([sys.executable, "-c", TESTE_CATIA], 60)
    if "ABERTO" in texto:
        ok("CATIA aberto")
    else:
        aviso("CATIA fechado. O HUB abre, mas as ferramentas precisam dele aberto.")
    try:
        import winreg
        winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "Excel.Application"))
        ok("Excel instalado")
    except OSError:
        aviso("Excel não encontrado. O Position and Zone precisa dele para ler o Part List e abrir a planilha.")


def diagnosticar_catia() -> int:
    """Para quando as macros do CATIA travam: mostra o estado, limpa e pede para testar de novo."""
    try:
        import win32com.client
        app = win32com.client.GetActiveObject("CATIA.Application")
    except Exception as exc:  # sem pywin32 ou sem CATIA, a resposta e a mesma
        erro(f"Não consegui falar com o CATIA: {exc}")
        return 1
    print("\nESTADO DO CATIA\n", flush=True)
    for nome in ("Interactive", "DisplayFileAlerts", "RefreshDisplay"):
        try:
            print(f"    {nome}: {getattr(app, nome)}", flush=True)
        except Exception as exc:  # um campo que nao le nao impede os outros
            print(f"    {nome}: não leu ({exc})", flush=True)
    try:
        print(f"    Documentos carregados: {app.Documents.Count}", flush=True)
        print(f"    Janelas: {app.Windows.Count}", flush=True)
        ativo = app.ActiveDocument
        print(f"    Documento ativo: {ativo.Name}", flush=True)
        print(f"    Itens selecionados: {ativo.Selection.Count}", flush=True)
    except Exception as exc:
        print(f"    Sem documento ativo ({exc})", flush=True)
    _, processos = rodar(["tasklist", "/FO", "CSV", "/NH"], 30)
    for programa in ("python.exe", "CNEXT.exe", "EXCEL.EXE"):
        print(f"    {programa} rodando: {processos.lower().count(programa.lower())}", flush=True)

    for nome in ("Interactive", "DisplayFileAlerts", "RefreshDisplay"):
        try:
            setattr(app, nome, True)
        except Exception:  # noqa: S110 - o resultado aparece no teste da macro
            pass
    try:
        app.ActiveDocument.Selection.Clear()
    except Exception:  # noqa: S110
        pass
    print("\nTirei a seleção e religuei alertas, tela e interação. O desenho não mudou.", flush=True)
    print("Clique agora na macro e mande uma foto desta tela, dizendo se ela voltou a funcionar.", flush=True)
    return 0


def manifesto() -> None:
    """Imprime o bloco MANIFESTO a partir dos arquivos desta pasta."""
    for relativo in MANIFESTO:
        with open(os.path.join(AQUI, *relativo.split("/")), "rb") as f:
            print(f'    "{relativo}": {assinatura(f.read())},')


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    if "--manifesto" in sys.argv:
        manifesto()
        return 0
    if "--catia" in sys.argv:
        return diagnosticar_catia()
    print("\nVERIFICADOR DO E1 TOOLS\n", flush=True)
    if not conferir_python():
        return 1
    tudo_certo = True
    problemas = conferir_arquivos()
    if problemas:
        tudo_certo = False
        erro(f"{len(problemas)} de {len(MANIFESTO)} arquivos com problema:")
        for p in problemas:
            print(f"      - {p}", flush=True)
    else:
        ok(f"{len(MANIFESTO)} arquivos certos")
    bibliotecas = conferir_bibliotecas()
    tudo_certo = tudo_certo and bibliotecas
    if tudo_certo:
        tudo_certo = conferir_tela()
    if bibliotecas:
        informar_programas()
    print("", flush=True)
    if tudo_certo:
        print("TUDO CERTO. Para abrir, rode:  python main_qt.py", flush=True)
        return 0
    print("AINDA NÃO ESTÁ PRONTO. Resolva os itens [ERRO], rode de novo", flush=True)
    print("e, se continuar, mande uma foto desta tela.", flush=True)
    return 1


if __name__ == "__main__":
    sys.exit(main())
