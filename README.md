# E1DWGTOOLS

HUB de ferramentas para automação de desenhos (CATDrawing) no **CATIA V5**,
com interface gráfica própria (customtkinter). Porte em Python/pycatia de
macros VBA legadas, começando pela troca de template (Update Template).

## O que faz

- **HUB de ferramentas**: janela sem bordas, visual escuro/moderno. Cada
  módulo em `src/tools/` vira automaticamente uma aba no topo.
- **Detecção do CATIA ao vivo**: reconhece em ~2s quando o CATIA é aberto ou
  fechado, e quando um CATDrawing passa a ser (ou deixa de ser) o documento
  ativo.
- **Preview do desenho real**: espelha a folha ativa do CATIA
  (`Viewer.CaptureToFile`), centralizada; se não houver CATIA/desenho, mostra
  um esquema de fallback.
- **Ferramenta 1 — Update Template**: conversão real (porte do VBA via COM) —
  copia as views para um template novo e injeta os parâmetros.
- **Ferramenta 2 — Trocar Template (BG)**: método alternativo, in-place —
  copia o fundo (frame + etiqueta) do template para o desenho, sem mexer na
  geometria.

## Pré-requisitos

- Windows com **CATIA V5** instalado (o app controla o CATIA via COM).
- **Python 3.10+**.
- **Git** e, para desenvolver, **PyCharm** (opcional).

## Instalação

```bat
git clone https://github.com/synysternoise/E1DWGTOOLS.git
cd E1DWGTOOLS
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Como rodar

Com o CATIA aberto (idealmente com um CATDrawing ativo):

```bat
python src\ui\main_window.py
```

No PyCharm: botão direito em `src/ui/main_window.py` → **Run 'main_window'**.

## Estrutura

```
src/
  ui/
    main_window.py        # HUB: janela, cabeçalho, abas, descoberta de ferramentas
    theme.py              # paleta de cores
  tools/
    update_template_tool.py      # Ferramenta 1 (UI) + base reaproveitável
    template_background_tool.py  # Ferramenta 2 (subclasse: só troca o motor)
  engine/
    update_template.py    # conversão real (porte do VBA) + helpers COM
    swap_background.py     # método do background (in-place)
    drawing_snapshot.py    # leitura do desenho ativo e estado do CATIA
    catia_capture.py       # captura da folha para o preview
legacy_vba/               # macros VBA originais (referência)
```

## Observações

- O caminho dos templates é o da rede da empresa
  (`\\nfscad05.sjk.emb\...`, definido em `src/engine/update_template.py`).
  Fora dessa rede, a conversão para honestamente em "Template não encontrado".
- As ferramentas só executam ações reais com o CATIA em execução; sem ele, a
  interface abre e indica "CATIA desconectado".
