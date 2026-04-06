---
projeto: ResolveAI CICD
descrição: Documentação técnica completa do sistema de revisão de código automatizada com IA integrado ao GitHub Actions
autor: Matheus Rosa
data: 2026-04-06
data_atualizacao: 2026-04-06
status: Aceito
---

# Registro de Decisão de Arquitetura (ADR) — ResolveAI CICD

## 1. Contexto e Objetivo

### 1.1 Origem

A ideia original surgiu de um conceito do Julio: um **issue solver** utilizando modelos da Anthropic para geração de planos com **Claude Opus 4.6** e execução com **Claude Sonnet 4.6**. A primeira versão foi implementada com **n8n** para validação do conceito.

### 1.2 Problemas da Versão Anterior

A versão baseada em n8n enfrentava limitações significativas:
- **Dificuldade com repositórios privados** — o fluxo não conseguia acessar código de repositórios privados de forma eficiente
- **Escalabilidade limitada** — a arquitetura não suportava bem um volume crescente de requisições
- **Manutenção complexa** — fluxos visuais tornam-se difíceis de versionar e auditar

### 1.3 Objetivo Desta Versão

Esta POC visa resolver os problemas identificados criando uma **API robusta e escalável** em Python com **FastAPI**, que:
- Funciona com **repositórios privados** (a GitHub Action roda dentro do contexto do repositório)
- É **escalável** por volume de requisições
- Permite **futura migração para Go** para ganho de performance em alta carga
- Utiliza **SQLite** nesta POC com intenção de migrar para **PostgreSQL** em produção

## 2. Visão Geral do Sistema

### 2.1 O Que É

O **ResolveAI CICD** é uma ferramenta de **revisão de código automatizada com IA** que se integra ao **GitHub Actions**. Quando um Pull Request é aberto, o sistema:

1. Extrai o **diff** das alterações
2. Analisa o código contra os **padrões de codificação** do repositório usando **Claude** (Anthropic)
3. Publica **comentários inline** diretamente nas linhas relevantes do PR

### 2.2 Fluxo de Funcionamento

#### Fluxo Padrão (PR já existe)

```
PR aberto/atualizado
  └─ GitHub Action extrai o diff
       └─ Envia diff para a API ResolveAI (POST /api/v1/review)
            ├─ Carrega os padrões de codificação do banco de dados
            ├─ Fase 1: Claude analisa o diff → lista estruturada de problemas
            ├─ Fase 2: Claude gera correções de código concretas
            └─ Publica revisão com comentários inline no PR via GitHub API
```

#### Fluxo Auto-Review (sem PR existente)

```
Commit pushado em branch sem PR
  └─ GitHub Action extrai o diff
       └─ Envia diff para a API ResolveAI (POST /api/v1/auto-review, create_pr=true)
            ├─ Fase 0: API cria um novo PR automaticamente
            ├─ Carrega os padrões de codificação do banco de dados
            ├─ Fase 1: Claude analisa o diff → lista estruturada de problemas
            ├─ Fase 2: Claude gera correções de código concretas
            ├─ Fase 3: Publica revisão com comentários inline no PR
            └─ Fase 4: Cria review-report.md na branch com relatório completo
```

> O endpoint `auto-review` é **híbrido**: se `pr_number` for informado, funciona como `/review`; se `create_pr=true` e nenhum `pr_number` existir, cria o PR automaticamente e gera o relatório markdown.

### 2.3 Revisão em Duas Fases

O sistema utiliza uma abordagem de **duas fases** para gerar reviews de qualidade:

| Fase | Modelo | Objetivo |
|------|--------|----------|
| **Planejamento** | Claude Sonnet (futuramente Opus) | Identifica bugs, violações de padrão, problemas de segurança e performance |
| **Execução** | Claude Sonnet | Gera sugestões de código concretas para cada problema identificado |

> **Nota:** As reviews são publicadas como eventos `COMMENT` (não `REQUEST_CHANGES`), portanto **nunca bloqueiam merges** até que o sistema seja considerado confiável.

## 3. Stack Tecnológico

| Camada | Tecnologia | Justificativa |
|--------|-----------|---------------|
| **API** | Python 3.11+ / FastAPI | Async nativo, tipado, fácil manutenção |
| **Banco de Dados** | SQLAlchemy async + aiosqlite | MVP com zero ops; swap para PostgreSQL = mudar 1 variável de ambiente |
| **IA** | Anthropic API (Claude Sonnet 4-6) | Modelo equilibrado entre custo e qualidade; Opus swap via config |
| **GitHub API** | httpx | Async-native, leve, precisamos de apenas 2 chamadas à API |
| **CI/CD** | GitHub Actions (composite action) | Rode dentro do contexto do repo, funciona com repos privados |
| **Pre-Commit** | Hook multi-linguagem | Linting local antes do commit |

### 3.1 Futura Migração para Go

Existe a intenção de reimplementar a API em **Go** no futuro para:
- Maior robustez sob **alto volume de requisições**
- Melhor performance em ambientes de produção com carga elevada
- Binário autocontido com menor overhead de deployment

## 4. Estrutura do Projeto

```
app/
  main.py              # Aplicação FastAPI, lifespan (cria tabelas do DB automaticamente)
  config.py            # pydantic-settings (configuração via variáveis de ambiente)
  database.py          # SQLAlchemy async engine + session factory
  models/pattern.py    # ORM: tabelas patterns + api_keys
  schemas/             # Modelos Pydantic de request/response
    review.py          # ReviewRequest, ReviewResponse
    auto_review.py     # AutoReviewRequest, AutoReviewResponse
  auth/api_key.py      # Validação do header X-API-Key (hash SHA-256)
  routers/
    patterns.py        # CRUD /api/v1/patterns/{owner}/{repo}
    review.py          # POST /api/v1/review (orquestra o fluxo completo)
    auto_review.py     # POST /api/v1/auto-review (cria PR + review + relatório .md)
  services/
    prompts.py         # Prompts de sistema: Planner + Executor
    anthropic_service.py  # plan_review() + generate_fixes()
    github_service.py     # post_review(), create_pull_request(), create_or_update_file()
action/action.yml      # GitHub Action composite
.github/workflows/     # Exemplo de workflow do usuário
pre_commit/hook.py     # Hook local de linting multi-linguagem
tests/                 # 15 testes, todos passando
```

## 5. Endpoints da API

### 5.1 POST `/api/v1/review` — Revisão de Diff

**Descrição:** Recebe o diff de um Pull Request existente, executa a análise com IA e publica os comentários inline no PR.

**Request Body:**

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `repository` | `str` | Rota no formato `"owner/repo"` |
| `pr_number` | `int` | Número do Pull Request |
| `diff_raw` | `str` | Texto completo do `git diff` |
| `base_ref` | `str` | Commit de referência base |
| `head_ref` | `str` | Commit onde a HEAD se localiza |
| `github_token` | `str` | Token de autenticação do GitHub (PAT com scope `pull-requests: write`) |
| `commit_sha` | `str` | Hash do novo commit |

**Response:**

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `status` | `str` | Status da operação (`success` ou `failed`) |
| `review_id` | `str` | Identificador único da review |
| `comments_count` | `int` | Número de comentários feitos no PR |
| `summary` | `str` | Resumo das alterações analisadas |

### 5.2 POST `/api/v1/auto-review` — Revisão Automática com Criação de PR

**Descrição:** Endpoint híbrido que pode **criar um PR automaticamente** quando nenhum existe, realizar a revisão com IA, postar comentários inline e gerar um **relatório markdown** (`review-report.md`) na branch de origem.

**Comportamento:**
- Se `pr_number` for informado → funciona como `/review` (comentários inline no PR existente)
- Se `create_pr=true` e `pr_number` não informado → **cria um novo PR**, posta comentários inline e gera o arquivo `review-report.md`
- Se `create_pr=false` e `pr_number` não informado → retorna **400 Bad Request**

**Request Body:**

| Campo | Tipo | Obrigatório | Padrão | Descrição |
|-------|------|-------------|--------|-----------|
| `repository` | `str` | Sim | — | Rota no formato `"owner/repo"` |
| `pr_number` | `int \| null` | Não | `null` | Número do Pull Request (omitir para auto-criação) |
| `diff_raw` | `str` | Sim | — | Texto completo do `git diff` |
| `base_ref` | `str` | Sim | — | Branch alvo (ex: `"main"`) |
| `head_ref` | `str` | Sim | — | Branch de origem (ex: `"feature/test"`) |
| `github_token` | `str` | Sim | — | Token do GitHub (`pull-requests: write` + `contents: write`) |
| `commit_sha` | `str` | Sim | — | Hash do commit |
| `create_pr` | `bool` | Não | `false` | Se `true`, cria PR automaticamente |
| `pr_title` | `str` | Não | `"ResolveAI Auto-Review"` | Título do PR criado |
| `pr_body` | `str` | Não | _mensagem padrão_ | Corpo/descrição do PR criado |

**Response:**

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `status` | `str` | Status da operação (`success` ou `error`) |
| `review_id` | `str \| null` | Identificador único da review |
| `pr_number` | `int \| null` | Número do PR (criado ou informado) |
| `pr_url` | `str \| null` | URL HTML do PR criado |
| `comments_count` | `int` | Número de comentários inline no PR |
| `summary` | `str` | Resumo da análise da IA |
| `report_file_path` | `str \| null` | Caminho do relatório markdown no repo (ex: `review-report.md`) |

**Relatório Markdown (`review-report.md`):**

Quando um PR é criado automaticamente, o sistema gera um arquivo `review-report.md` na branch de origem contendo:
- Resumo executivo da análise
- Contagem por severidade (🔴 Critical, 🟡 Warning, 💡 Suggestion)
- Lista detalhada de cada problema com arquivo, linhas, descrição e sugestão de correção

### 5.3 GET `/api/v1/patterns/{owner}/{repo}` — Obter Padrões de Código

**Descrição:** Retorna o arquivo de padrões de codificação do repositório (equivalente a um `CLAUDE.md`), usado para guiar a IA em cada revisão.

**Request:**

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `owner` | `str` | Organização ou usuário dono do repositório |
| `repo` | `str` | Nome do repositório |

**Response:**

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | `str` | Identificador do padrão |
| `repository` | `str` | Nome do repositório |
| `name` | `str` | Nome da organização/usuário |
| `content` | `str` | Conteúdo dos padrões de codificação |
| `created_at` | `datetime` | Data de criação |
| `updated_at` | `datetime` | Data da última alteração |

### 5.4 PUT `/api/v1/patterns/{owner}/{repo}` — Criar/Atualizar Padrões

**Descrição:** Cria ou atualiza o arquivo de padrões de codificação para um repositório. Permite definir convenções como "usar snake_case", "adicionar type hints", regras de segurança, etc.

**Autenticação:** Header `X-API-Key` obrigatório.

### 5.5 DELETE `/api/v1/patterns/{owner}/{repo}` — Remover Padrões

**Descrição:** Remove o arquivo de padrões de codificação associado a um repositório.

**Autenticação:** Header `X-API-Key` obrigatório.

### 5.6 GET `/health` — Health Check

**Descrição:** Endpoint público para verificação de saúde do serviço. Não requer autenticação.

**Uso:** Utilizado por load balancers, orquestradores (Kubernetes, etc.) e monitoramento.

### 5.6 Resumo dos Endpoints

| Método | Path | Auth | Finalidade |
|--------|------|------|------------|
| `POST` | `/api/v1/review` | API Key | Recebe diff, executa revisão IA, publica no PR existente |
| `POST` | `/api/v1/auto-review` | API Key | Recebe diff, cria PR se necessário, publica review + relatório `.md` |
| `GET` | `/api/v1/patterns/{owner}/{repo}` | API Key | Obtém arquivo de padrões |
| `PUT` | `/api/v1/patterns/{owner}/{repo}` | API Key | Cria/atualiza arquivo de padrões |
| `DELETE` | `/api/v1/patterns/{owner}/{repo}` | API Key | Remove arquivo de padrões |
| `GET` | `/health` | Nenhuma | Health check do serviço |

## 6. Modelo de Dados

### 6.1 Banco de Dados (SQLite — MVP)

O sistema utiliza **SQLite** nesta fase de POC por ser zero ops e suficiente para validação. A migração para PostgreSQL será trivial — basta alterar a string de conexão na variável de ambiente `DATABASE_URL`.

### 6.2 Tabelas

#### `patterns`
Armazena arquivos de padrões de codificação por repositório (estilo `CLAUDE.md`).

| Coluna | Tipo | Restrição |
|--------|------|-----------|
| `id` | `str` | Primary Key |
| `repository` | `str` | Unique junto com `name` |
| `name` | `str` | Unique junto com `repository` |
| `content` | `str` | — |
| `created_at` | `datetime` | Auto-generated |
| `updated_at` | `datetime` | Auto-updated |

#### `api_keys`
Armazena chaves de API estáticas com escopo por repositório.

| Coluna | Tipo | Restrição |
|--------|------|-----------|
| `key_hash` | `str` | Primary Key (SHA-256 hash) |
| `repository` | `str` | Escopo da chave |
| `created_at` | `datetime` | Auto-generated |

## 7. Autenticação e Segurança

### 7.1 API Key

- Todas as endpoints (exceto `/health`) exigem o header `X-API-Key`
- As chaves são armazenadas como **hash SHA-256** no banco
- Cada chave tem **escopo por repositório** — uma chave só pode acessar padrões e reviews do repo ao qual pertence
- Chaves são geradas via script `scripts/create_api_key.py` e **não podem ser recuperadas** após criação

### 7.2 GitHub Token

- O `github_token` é **passado por requisição** pela GitHub Action
- **Nunca é armazenado** no nosso banco de dados
- Precisa do scope `pull-requests: write` para publicar comentários no PR

### 7.3 Repositórios Privados

O sistema foi projetado para funcionar com **repositórios privados**:
- A GitHub Action roda **dentro do contexto do repositório**
- A API **nunca clona ou acessa diretamente** o código do usuário
- O diff é extraído localmente pela Action e enviado à API

## 8. Integração com GitHub Actions

### 8.1 Como Funciona

A GitHub Action é um **composite action** que:
1. É acionada quando um PR é `opened`, `synchronize` ou `reopened`
2. Extrai o diff do PR usando `GrantBirki/git-diff-action`
3. Envia o diff + metadados para `POST /api/v1/review` com autenticação `X-API-Key`
4. A API processa e publica os comentários diretamente no PR

### 8.2 Configuração do Usuário

O usuário precisa configurar dois **secrets** no repositório:

| Secret | Descrição |
|--------|-----------|
| `RESOLVEAI_API_URL` | URL da API ResolveAI implantada |
| `RESOLVEAI_API_KEY` | Chave de API gerada para este repositório |

### 8.3 Inputs da GitHub Action

| Input | Obrigatório | Padrão | Descrição |
|-------|-------------|--------|-----------|
| `api_url` | Sim | — | URL da API ResolveAI |
| `api_key` | Sim | — | Chave de API |
| `github_token` | Não | `${{ github.token }}` | Token do GitHub |
| `create_pr` | Não | `false` | Se `true`, cria PR automaticamente quando não existe |
| `pr_title` | Não | `ResolveAI Auto-Review` | Título do PR auto-criado |
| `pr_body` | Não | _mensagem padrão_ | Corpo do PR auto-criado |

### 8.4 Exemplo de Workflow — Revisão de PR Existente

```yaml
name: ResolveAI Code Review

on:
  pull_request:
    types: [opened, synchronize, reopened]

permissions:
  contents: read
  pull-requests: write

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: YOUR_ORG/resolveai-cicd/action@main
        with:
          api_url: ${{ secrets.RESOLVEAI_API_URL }}
          api_key: ${{ secrets.RESOLVEAI_API_KEY }}
          github_token: ${{ secrets.GITHUB_TOKEN }}
```

### 8.5 Exemplo de Workflow — Auto-Criação de PR

Quando **nenhum PR existe** e você quer que a Action crie um automaticamente:

```yaml
name: ResolveAI Auto Review

on:
  push:
    branches: ['**']   # Qualquer branch

permissions:
  contents: write
  pull-requests: write

jobs:
  auto-review:
    if: ${{ !github.event.pull_request }}   # Só roda se NÃO for PR event
    runs-on: ubuntu-latest
    steps:
      - uses: YOUR_ORG/resolveai-cicd/action@main
        with:
          api_url: ${{ secrets.RESOLVEAI_API_URL }}
          api_key: ${{ secrets.RESOLVEAI_API_KEY }}
          github_token: ${{ secrets.GITHUB_TOKEN }}
          create_pr: true
          pr_title: 'ResolveAI Auto-Review — ${{ github.ref_name }}'
          pr_body: 'Review automática criada pelo ResolveAI.'
```

> **Nota:** O `github_token` precisa de permissão `contents: write` para criar o arquivo `review-report.md` na branch.

## 9. Pre-Commit Hook

Hook local que executa **linting multi-linguagem** em arquivos staged e gera um relatório em `.resolveai/review.md`.

### 9.1 Linters Suportados

Cada linter só executa se seu binário estiver disponível no `PATH`:

| Linguagem | Linter |
|-----------|--------|
| Python | ruff |
| JavaScript/TypeScript | eslint |
| Go | golangci-lint |
| Rust | cargo clippy |
| Java | checkstyle |
| Ruby | rubocop |
| C/C++ | cppcheck |

### 9.2 Instalação

Adicionar ao `.pre-commit-config.yaml` do repositório alvo:

```yaml
repos:
  - repo: https://github.com/YOUR_ORG/resolveai-cicd
    rev: main
    hooks:
      - id: resolveai-review
```

## 10. Decisões de Arquitetura

| Decisão | Justificativa |
|---------|---------------|
| **`github_token` passado por requisição** | Nunca armazenamos tokens no DB; segurança e auditoria simplificadas |
| **Review como `COMMENT` não `REQUEST_CHANGES`** | Não bloquear merges até que o sistema seja confiável |
| **httpx ao invés de PyGithub** | Async-native, leve, precisamos de apenas 2 chamadas à API |
| **Sonnet para ambas as fases no MVP** | Interface de duas fases já construída; trocar para Opus é mudar 1 linha de config |
| **SQLite para MVP** | Zero ops; migrar para PostgreSQL = alterar 1 variável de ambiente |
| **Padrões por repositório** | Cada repo pode ter convenções diferentes; flexibilidade máxima |

## 11. Configuração

Toda configuração é feita via **variáveis de ambiente** (ou arquivo `.env`):

| Variável | Obrigatória | Padrão | Descrição |
|----------|-------------|--------|-----------|
| `ANTHROPIC_API_KEY` | Sim | — | Chave da API da Anthropic |
| `DATABASE_URL` | Não | `sqlite+aiosqlite:///./resolveai.db` | String de conexão do banco |
| `PLANNER_MODEL` | Não | `claude-sonnet-4-6` | Modelo para fase de análise |
| `EXECUTOR_MODEL` | Não | `claude-sonnet-4-6` | Modelo para fase de geração de fixes |
| `DEBUG` | Não | `false` | Habilitar logging de debug |

## 12. Deploy

### 12.1 Docker

```bash
docker build -t resolveai-cicd .
docker run -p 8000:8000 --env-file .env resolveai-cicd
```

### 12.2 Desenvolvimento Local

```bash
cp .env.example .env   # preencher ANTHROPIC_API_KEY
uv venv .venv && uv pip install --python .venv -e ".[dev]"
.venv/bin/uvicorn app.main:app --reload
```

API disponível em `http://localhost:8000` com docs interativos em `http://localhost:8000/docs`.

## 13. Testes

```bash
ANTHROPIC_API_KEY=test .venv/bin/pytest tests/ -v
```

Atualmente **15 testes**, todos passando (9 originais + 6 do auto-review).

## 14. Roadmap

### V2 — Prontidão para Produção

- [x] **Auto-criação de PR com relatório markdown** — endpoint `POST /api/v1/auto-review` cria PR, posta comentários inline e gera `review-report.md`
- [ ] Trocar modelo de planejamento para **Claude Opus 4-6** para análise mais profunda
- [ ] **Pre-commit com revisão IA opcional** (flag `--ai` chama API remota)
- [ ] **Autenticação via GitHub App** ao invés de PATs (permissões mais granulares, melhor auditoria)
- [ ] **PostgreSQL** para deployments em produção
- [ ] **Rate limiting e tracking de uso** por API key
- [ ] **CLI de gerenciamento de API keys** (`create_api_key.py`)
- [ ] **Isolamento multi-tenant** (validar que API key corresponde ao repo solicitado)
- [ ] **Migrações Alembic** para evolução do schema

### V3 — Features de Plataforma

- [ ] **Página dedicada de reviews** (UI web para visualizar reviews fora do GitHub)
- [ ] **Auto-fix em PRs** (bot cria commits com correções sugeridas)
- [ ] **Loop de feedback** (aprender com sugestões aceitas/rejeitadas)
- [ ] **Padrões em nível de time** (compartilhados entre repos de uma org)
- [ ] **UI web para gerenciamento de padrões** (CRUD sem chamadas à API)
- [ ] **Billing e metering de uso**

### V4 — Inteligência

- [ ] **Reviews cientes de contexto** (buscar conteúdo completo do arquivo, não apenas diff)
- [ ] **Geração de resumo de PR** (auto-gerar descrições de PR)
- [ ] **Aprendizado cross-PR** (detectar padrões recorrentes entre reviews)
- [ ] **Regras de linter customizadas** geradas a partir dos padrões

## 15. Funcionalidades Principais

| Feature | Descrição |
|---------|-----------|
| **Reviews baseadas em padrões** | Defina padrões de código por repositório (como um `CLAUDE.md`) e a IA os aplica |
| **Comentários inline no PR** | Problemas aparecem diretamente nas linhas relevantes do PR |
| **Auto-criação de PR** | Quando não há PR, a API cria um automaticamente com comentários inline + relatório `.md` |
| **Relatório de review em markdown** | Arquivo `review-report.md` gerado na branch com resumo completo da análise |
| **Pre-commit multi-linguagem** | Linting local para Python, JS/TS, Go, Rust, Java, Ruby, C/C++ |
| **Funciona com repos privados** | A Action roda no contexto do repo; a API nunca acessa o código diretamente |
| **Auth por API Key** | Chaves com hash SHA-256, com escopo por repositório |

## 16. Glossário

| Termo | Significado |
|-------|-------------|
| **Diff** | Diferença entre dois commits, gerada por `git diff` |
| **Pattern** | Arquivo de padrões de codificação do repositório (estilo `CLAUDE.md`) |
| **Review** | Revisão de código gerada pela IA com comentários inline |
| **Auto-Review** | Endpoint híbrido que cria PR automaticamente + review + relatório `.md` |
| **Planning Phase** | Fase 1 — análise do diff e identificação de problemas |
| **Execution Phase** | Fase 2 — geração de correções concretas para cada problema |
| **PAT** | Personal Access Token do GitHub |
| **Composite Action** | Tipo de GitHub Action composta por múltiplos passos |
| **review-report.md** | Arquivo markdown gerado automaticamente com o resumo completo da review |

---

*Documento criado com base no ADR original, README.md e CLAUDE.md para documentação completa do projeto ResolveAI CICD.*
