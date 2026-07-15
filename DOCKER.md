# Rodando o AgroAudit em container (Docker ou Podman)

Este guia cobre build, execução, atualização de chave, volumes e os erros mais
comuns. Os comandos são intercambiáveis entre `docker` e `podman` — troque um
pelo outro conforme a ferramenta que você usa. Onde há diferença real, está
marcado explicitamente.

## Pré-requisitos

- Docker Desktop **ou** Podman instalado e rodando.
- O projeto já extraído numa pasta local, com o `.env` configurado (veja o
  `README.md` principal se ainda não fez isso — é o mesmo `.env` usado na
  execução sem container).

Verifique que a ferramenta está funcionando:

```bash
docker --version      # ou: podman --version
```

## 1. Build da imagem

Rode a partir da raiz do projeto (onde está o `Dockerfile`):

```bash
docker build -t agroaudit .
```

```bash
podman build -t agroaudit .
```

O que acontece nesse passo: o Docker/Podman instala as dependências
(`requirements.txt`) e copia o código (`main.py`, `gemini_service.py`,
`prompts.py`) e as imagens de exemplo (`images/`) para dentro da imagem.
**O `.env` nunca entra aqui** — isso é proposital, veja a seção de segurança
mais abaixo.

Você só precisa rodar o build de novo quando mudar **código ou dependências**.
Trocar a chave no `.env` não exige rebuild (veja a seção 4).

## 2. Rodando o container

### Opção A — comando direto

Linux/macOS (bash/zsh):
```bash
docker run --rm --env-file .env -v "$(pwd)/output:/app/output" agroaudit images/01_aerea_unidade_industrial_silos_as_margens_do_rio.jpeg
```

Windows (PowerShell):
```powershell
docker run --rm --env-file .env -v "${PWD}/output:/app/output" agroaudit images/01_aerea_unidade_industrial_silos_as_margens_do_rio.jpeg
```

Com Podman no Linux, se aparecer erro de permissão ao escrever no volume,
adicione o sufixo `:Z` (relacionado ao SELinux — não existe no Windows/macOS):
```bash
podman run --rm --env-file .env -v "$(pwd)/output:/app/output:Z" agroaudit images/01_aerea_unidade_industrial_silos_as_margens_do_rio.jpeg
```

O que cada parte do comando faz:

| Parte | Para que serve |
|---|---|
| `--rm` | remove o container assim que ele termina (não deixa lixo acumulando) |
| `--env-file .env` | injeta a `GEMINI_API_KEY` na hora de rodar, sem gravá-la na imagem |
| `-v "...:/app/output"` | espelha a pasta `output/` do container para uma pasta real no seu PC, para os dossiês sobreviverem depois que o container é removido |
| `agroaudit` | nome da imagem que você buildou no passo 1 |
| `images/01_aerea_unidade_industrial_silos_as_margens_do_rio.jpeg` | argumento passado direto para o `main.py` dentro do container |

Para analisar outra imagem, só troque o último argumento:
```bash
docker run --rm --env-file .env -v "${PWD}/output:/app/output" agroaudit images/imagem-fogo.webp
```

Se quiser usar uma imagem sua que ainda não está na pasta `images/` do
projeto, monte também essa pasta como volume (assim não precisa rebuildar a
imagem toda vez que adicionar uma foto nova):
```bash
docker run --rm --env-file .env \
  -v "${PWD}/images:/app/images" \
  -v "${PWD}/output:/app/output" \
  agroaudit images/minha_foto_nova.jpg
```

### Opção B — docker-compose / podman-compose (mais prático no dia a dia)

O projeto já inclui um `docker-compose.yml` que monta `images/` e `output/`
automaticamente, então você não precisa digitar os `-v` toda vez.

Com Docker:
```bash
docker compose run --rm agroaudit images/01_aerea_unidade_industrial_silos_as_margens_do_rio.jpeg
```

Com Podman (versão 4.x+, que já traz `compose` embutido):
```bash
podman compose run --rm agroaudit images/01_aerea_unidade_industrial_silos_as_margens_do_rio.jpeg
```

Se seu Podman não tiver o subcomando `compose`, instale o `podman-compose`
separadamente e use:
```bash
podman-compose run --rm agroaudit images/01_aerea_unidade_industrial_silos_as_margens_do_rio.jpeg
```

## 3. Onde ficam os resultados

Cada execução salva o dossiê em `output/<vistoria_id>.json` — e, como essa
pasta está montada como volume, o arquivo aparece direto na pasta `output/`
do seu computador, do lado de fora do container. Você pode abrir esses
arquivos normalmente no VS Code.

## 4. Trocando a chave de API

Só edite o `.env` e rode o container de novo — **não precisa rebuildar a
imagem**. O `--env-file .env` (ou o `env_file:` do compose) é lido no momento
exato do `run`, então sempre pega o conteúdo mais atual do arquivo.

Você só precisa rebuildar (`docker build` / `podman build`) quando mudar
código, `requirements.txt`, ou as imagens que ficam copiadas dentro da
imagem (pasta `images/` no momento do build).

## 5. Limpando containers e imagens antigas

Remover a imagem depois de testar bastante e não precisar mais dela:
```bash
docker image rm agroaudit      # ou: podman image rm agroaudit
```

Ver o que está ocupando espaço:
```bash
docker system df               # ou: podman system df
```

## 6. Erros comuns

**`GEMINI_API_KEY não encontrada` mesmo com `--env-file .env`**
Confira se o comando está sendo rodado na mesma pasta onde o `.env` existe, e
se o arquivo realmente se chama `.env` (não `.env.txt` nem `env`).

**`403 PERMISSION_DENIED` / `SERVICE_DISABLED`**
Não é erro de container — é a chave de API vinda de um projeto do Google
Cloud onde a Gemini API ainda não foi habilitada. Gere uma chave nova em
https://aistudio.google.com/apikey (ela já vem com a API habilitada).

**`503 UNAVAILABLE` / "high demand"**
O serviço do Gemini está temporariamente sobrecarregado do lado do Google. O
programa já tenta de novo automaticamente algumas vezes; se persistir, espere
um pouco e rode de novo.

**Erro de permissão ao escrever em `output/` (comum no Podman/Linux)**
Adicione o sufixo `:Z` no volume, como mostrado na seção 2.

**`no such file or directory` para a imagem passada como argumento**
O caminho é relativo ao **dentro do container** (`/app/...`), não ao seu PC.
Use sempre `images/nome-do-arquivo.jpg` — que é exatamente onde a pasta
`images/` foi copiada/montada dentro do container.

## Nota de segurança

O `.env` nunca é copiado para dentro da imagem (está bloqueado no
`.dockerignore`, de propósito). Ele só existe no seu computador e é injetado
em memória no momento do `run`. Isso evita que a chave fique gravada
permanentemente numa camada da imagem — o que seria um problema sério se essa
imagem um dia fosse publicada num registry (Docker Hub, GHCR, etc.), mesmo
que "por engano".