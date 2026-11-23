# Como criar o Assistente E1 Tools no Copilot da Embraer

Passo a passo, do zero até compartilhar com os projetistas. Os textos para colar estão prontos aqui. O
processo leva de 20 a 30 minutos.

> Os nomes dos menus foram escritos conforme o Microsoft 365 Copilot em português. A versão da Embraer
> pode mostrar um nome um pouco diferente, ou em inglês: **Create agent**, **Configure**, **Knowledge**,
> **Share**. O caminho é o mesmo.

---

## Antes de começar: qual Copilot

Use o Copilot **da conta da Embraer**: o Microsoft 365 Copilot, ou Copilot Chat do trabalho. O guia cita
pastas da rede, o endereço do VPM e PNs. Não use o Copilot pessoal (conta Microsoft particular) nem o
GitHub Copilot.

Para conferir, abra o Copilot pelo **Teams** ou em `m365copilot.com`, entrando com o e-mail da Embraer.
Se aparecer **Criar agente** (ou **Agentes › Criar agente**), está liberado. Se não aparecer, a TI
desligou a criação de agentes: peça a liberação, ou o Copilot Studio se a TI indicar.

## O que você vai precisar

Todos os arquivos estão na pasta `docs` do E1 Tools:

| Arquivo | Para quê |
|---|---|
| `GUIA_DO_USUARIO.pdf` | Conhecimento do agente: é de onde saem as respostas |
| `agente/INSTRUCOES_DO_AGENTE.txt` | Texto do campo **Instruções** (3.870 caracteres; o limite é 8.000) |
| `agente/icone_agente.png` | Ícone do agente: o mesmo do HUB |
| `videos/01_…mp4` a `videos/07_…mp4` | Vídeos que o agente indica nas respostas |

Leve esses arquivos para o PC da empresa pelo caminho que a TI permite. Por exemplo, um `git pull` do
repositório do E1 Tools, depois que o `docs/` for commitado.

---

## Parte 1: pasta no SharePoint

O agente lê o guia direto do SharePoint. Assim, quando você trocar o PDF, o agente passa a usar a versão
nova sem ser refeito.

1. Escolha onde guardar: a aba **Arquivos** de um canal da equipe no Teams, ou um site do SharePoint da
   equipe. Evite o seu OneDrive pessoal: se você sair da equipe, o agente perde o arquivo.
2. Crie a pasta `E1 Tools` com duas subpastas: `Guia` e `Vídeos`.
3. Suba o `GUIA_DO_USUARIO.pdf` para `Guia`.
4. Suba os 7 vídeos para `Vídeos`.
5. **Acesso:** todos os projetistas que vão usar o agente precisam conseguir **abrir** essa pasta (só
   leitura basta). Em `E1 Tools`, clique em **…› Gerenciar acesso** ou **Compartilhar**. Adicione o
   grupo dos projetistas com permissão **Pode exibir**. Se for um canal do Teams onde todos já são
   membros, o acesso já existe.

> Sem acesso ao PDF, o agente não consegue responder para aquela pessoa: ele busca só no que ela tem
> permissão de abrir.

## Parte 2: links dos vídeos nas instruções

1. Abra o `INSTRUCOES_DO_AGENTE.txt` no Bloco de Notas.
2. Na pasta `Vídeos` do SharePoint, para cada vídeo, clique em **…› Copiar link**. Nas opções do link,
   escolha **Pessoas com acesso existente**, para não abrir o acesso a mais ninguém.
3. No `.txt`, troque cada `LINK_VIDEO_01` … `LINK_VIDEO_07` pelo link do vídeo correspondente:

   | Marcador | Vídeo |
   |---|---|
   | `LINK_VIDEO_01` | 01_sequencia_de_aplicacao.mp4 |
   | `LINK_VIDEO_02` | 02_update_template.mp4 |
   | `LINK_VIDEO_03` | 03_symbol_shape_converter.mp4 |
   | `LINK_VIDEO_04` | 04_fix_flags.mp4 |
   | `LINK_VIDEO_05` | 05_font_size_fix.mp4 |
   | `LINK_VIDEO_06` | 06_pos_and_zone_fix.mp4 |
   | `LINK_VIDEO_07` | 07_check_visao_geral.mp4 |

4. Abra um dos links numa janela anônima do navegador, entrando com outra conta da equipe, se puder.
   O vídeo deve tocar no player do SharePoint (Stream).
5. Salve o `.txt`. Não deixe nenhum `LINK_VIDEO_` sem trocar: o agente mostraria o marcador como se
   fosse um link.

> Atalho: se não quiser copiar sete links, apague as sete linhas e deixe uma só:
> `- Todos os vídeos estão na pasta: <link da pasta Vídeos>`.

## Parte 3: criar o agente

1. Abra o Copilot com a conta da Embraer (Teams › **Copilot**, ou `m365copilot.com`).
2. No painel da esquerda, clique em **Criar agente** (pode estar dentro de **Agentes**).
3. Abre uma tela com duas abas: **Descrever** e **Configurar**. Vá direto em **Configurar**. A aba
   Descrever cria o agente conversando, mas aqui os textos já estão prontos.
4. Preencha os campos abaixo.

### Ícone

Clique no ícone ao lado do nome e envie o `icone_agente.png`. Se a sua versão não deixar trocar o ícone,
pule este campo.

### Nome

```
Assistente E1 Tools
```

### Descrição

```
Tira dúvidas sobre o HUB E1 Tools (Update Template, Symbol Shape, Fix Flags, Font Size, Position and Zone, Checks, Splits e VPM) com base no guia do usuário. Responde em português, cita a seção do guia e indica o vídeo da ferramenta.
```

### Instruções

Cole **todo** o texto do `INSTRUCOES_DO_AGENTE.txt`, já com os links dos vídeos da Parte 2.

### Conhecimento

1. Desligue **Pesquisar na Web**, ou **Usar conteúdo da Web**. As respostas devem vir só do guia.
2. Clique no campo de conhecimento (ou em **Adicionar**) e escolha **SharePoint/OneDrive**.
3. Procure e selecione `GUIA_DO_USUARIO.pdf` na pasta `E1 Tools/Guia`, ou cole o link do arquivo.
4. Se aparecer a opção **Usar somente o conhecimento especificado**, ligue.

> Não adicione a pasta de vídeos como conhecimento: o agente não assiste vídeo. Ele só repassa os links
> das instruções.

### Recursos

Deixe desligados o **Interpretador de código** e o **Gerador de imagens**.

### Prompts iniciais

Clique em **Adicionar prompt** seis vezes e preencha:

| Título | Mensagem |
|---|---|
| Update Template | Como atualizo o template de um desenho antigo? |
| Zona diferente | O Position and Zone mostrou zona diferente do Part List. Como corrijo? |
| Flag sem nota | O que significa "flag sem nota" no Check de Flags? |
| Fontes do A1 | Quais são os tamanhos de fonte aceitos no formato A1? |
| Erro no Update | O Update Template deu erro no meio. E agora? |
| Instalação | O verificar.py mostrou [ERRO]. O que faço? |

## Parte 4: testar antes de publicar

O painel da direita é um teste do agente: nada é publicado ainda. Faça as perguntas abaixo. Se ele errar
ou inventar, ajuste as **Instruções** e teste de novo.

| Pergunta | Resposta esperada |
|---|---|
| Posso parar o Update Template no meio? | Não. Não há botão de parar, porque o desenho ficaria parcialmente convertido. (3.2) + link do vídeo 02 |
| O Font Size Fix corrige sozinho na sequência? | Não. Na sequência ele só analisa; REVISAR AS FONTES abre a lista para corrigir um por um. (3.1) |
| Quais tamanhos valem no A0? | 0,197" e 0,277". (3.5) |
| O Check de Flags altera o desenho? | Não, só confere. (4.4) |
| Onde fica o OK manual do Position and Zone? | Em %APPDATA%\E1DWGTools\poszone_ok.json, só neste PC. Deixa de valer se a zona ou a quantidade mudarem. (4.3 e 8) |
| O Split 2D leva o que eu não salvei? | Não. Usa o arquivo salvo em disco. (5.2) |
| Deu UPLOAD_INCERTO. Rodo de novo? | Não antes de conferir no VPM. O HUB não repete sozinho. (6.1) |
| As macros do CATIA travaram. | Rodar python verificar.py --catia. A causa ainda não é conhecida. (7) |
| Como mudo a cor da flag? | Deve dizer que isso não está no guia, sem inventar. |
| Me passa o código do Fix Flags. | Deve recusar: não escreve nem altera código. |
| Tem vídeo do Split 2D? | Deve dizer que não tem, sem inventar link. |

> Se logo depois de adicionar o PDF ele responder "não está no guia" para tudo, espere alguns minutos: o
> arquivo pode ainda estar sendo indexado.

## Parte 5: criar e compartilhar

1. Clique em **Criar**, no canto superior direito.
2. Na janela seguinte, clique em **Compartilhar** (ou abra o agente depois e vá em **…› Compartilhar**).
3. Escolha quem pode usar:
   - **Somente você**: para testar mais um pouco antes de liberar;
   - **Usuários específicos** (pessoas ou um grupo): **recomendado**. Escolha o grupo dos projetistas
     que usam o E1 Tools;
   - **Qualquer pessoa na organização**: evite. A empresa inteira veria o agente.
4. Confira se as pessoas escolhidas são as mesmas que têm acesso à pasta `E1 Tools` da Parte 1.
5. Clique em **Copiar link** e salve.

## Parte 6: avisar os projetistas

Mensagem pronta para o Teams. Troque `<link do agente>` e `<link da pasta Vídeos>`:

```
Pessoal, criei o Assistente E1 Tools no Copilot para tirar dúvidas do HUB (Update Template, Fix Flags, Font Size, Position and Zone, Checks, Splits e VPM).

Como usar:
1. Abra o link: <link do agente>
2. Clique em Adicionar (só na primeira vez). Depois ele fica na lista de agentes do Copilot.
3. Pergunte em português, por exemplo: "O Update Template deu erro no meio. E agora?"

Ele responde pelo guia do usuário e indica a seção e o vídeo da ferramenta. Os vídeos também estão aqui: <link da pasta Vídeos>

Se ele disser que algo não está no guia, ou se achar um erro, me avise.
```

---

## Manutenção

- **Programa mudou:** atualize o `GUIA_DO_USUARIO.md`, gere o PDF de novo e substitua o arquivo no
  SharePoint **com o mesmo nome**. O agente pega a versão nova sozinho, depois de indexar, o que pode
  levar algum tempo.
- **Vídeo novo:** suba para a pasta `Vídeos`, copie o link e acrescente uma linha na seção VÍDEOS das
  instruções. Para isso, abra o agente, clique em **Editar** e depois em **Atualizar**.
- **O agente responde pelo texto do PDF.** Os prints ajudam quem lê, mas tudo o que importa para as
  respostas precisa estar escrito.

## Se algo der errado

| Problema | O que fazer |
|---|---|
| Não aparece **Criar agente** | A criação de agentes está desligada na sua conta. Peça à TI. |
| O agente responde "não está no guia" para tudo | Espere a indexação. Confira se o PDF está em **Conhecimento** e se você consegue abri-lo. |
| Funciona para você e não para um colega | O colega não tem acesso à pasta `E1 Tools` ou não está no compartilhamento do agente. |
| O link do vídeo não abre para os colegas | O link foi criado só para você. Gere de novo com **Pessoas com acesso existente** e confira o acesso à pasta. |
| O agente inventou um botão ou um link | Mande a pergunta e a resposta para quem mantém o agente, que ajusta as instruções. |
