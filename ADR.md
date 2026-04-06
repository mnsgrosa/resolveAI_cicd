---
projeto:Resolve AI API POC
descrição:POC da API do agente revisor de código em repositórios git gerando uma PR com diff de código e raciocínio por trás das alterações
Autor:Matheus Rosa
---

# 1. Objetivo:

Julio havia criado a ideia de um issue solver com os modelos anthropic para geração de plano com o opus 4.6 e execução com sonnet 4.6
inicialmente foi implementado com n8n para uma primeira versão. Essa versão apresentada visa mostrar uma versão que resolve o problema
de repositórios privados e seja mais escalavel, aqui é utilizado python para criação da API em FastAPI a ideia é fazer em GO futuramente
para uma API mais robusta por volume de requests. Por fim na POC utiliza SQLite e tenho intenção de colocar em PSQL

# 2. Estrutura dos endpoints:

## 2.1 Post de review das diffs - {/api/v1/review}

Recebe as diffs com o seguinte body:

```python
{
    repository:str, # Rota: "owner/repo"
    pr_number:int, # Numero da pr
    diff_raw:str, # Texto do git diff
    base_ref:str, # Commit referencia base
    head_ref:str, # Commit em que a HEAD se localiza
    github_token:str, # Token de autenticação github
    commit_sha:str # Hash do novo commit
}
```

e retorna:

```python
{
    status:str, # Status sucess ou failed
    review_id:str, # Id de review
    comments_count:int, # Números de comentários feitos 
    summary:str # Retorna resumo das alterações
}
```

## 2.2 Get de padrão código LLM - {/api/v1/patterns/{owner}/{repo}}

Endpoint destinado a retornar o padrão de código destinado ao repositório para guiar o Claude estilo claude.md mas 
passado a cada chamada de review

corpo do request:

```python
{
    owner:str, #Org ou usuário dono do repositório
    repo:str #Repositório destinado
}
```

corpo do response:

```python
{
    id:str,
    repository:str, #Nome do repositório
    name:str, #Nome da organização/usuário
    content:str, #Conteudo dos padrões
    created_at:datetime, #Quando foi criado
    updated_at:datetime #Qunado foi alterado
}
```

## 2.3 Put de padrão de código LLM - {/api/v1/patterns/{owner}/{repo}}

Explicacao do endpoint put

## 2.4 Delete de padrao de codigo LLM - {/api/v1/patterns/{owner}/{repo}}

Explicacao do endpoint DELETE

## 2.5 Health do servico - {/health}

Explicacao do endpoint health

# 3. Integracao github actions:

Explicacao da integracao com github actions
