# Mythra

Persistent narrative engine for interactive story generation, character memory, world state, and narrative consistency.

## Objetivo

Mythra mantém o estado narrativo canônico em dados relacionais persistidos. A Fase 01 implementa a fundação backend para usuários, histórias, personagens, fatos, conhecimento, relacionamentos e estruturas narrativas. O banco — e não uma saída de modelo generativo — é a autoridade do estado.

## Arquitetura atual

Monólito modular com dependências organizadas em camadas:

- `domain`: conceitos e invariantes sem dependência de HTTP ou persistência.
- `application`: casos de uso e interfaces de persistência.
- `infrastructure`: SQLAlchemy 2.x, repositories, sessão e PostgreSQL.
- `api`: FastAPI, schemas Pydantic e mapeamento de erros HTTP.
- `core`: configuração e logging transversais.

O estado corrente reside em tabelas relacionais. `story_events` mantém histórico append-only e não substitui as entidades de estado. JSONB é utilizado somente no payload de `StoryEvent`.

## Stack

Python 3.12+, FastAPI, Pydantic, SQLAlchemy 2.x, PostgreSQL, Alembic, pytest, Ruff, mypy e Docker Compose.

## Executar localmente

Crie e ative um ambiente virtual, instale dependências de desenvolvimento e configure o ambiente:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env
```

Edite `MYTHRA_DATABASE_URL` em `.env` para apontar para um PostgreSQL disponível. Depois aplique as migrations e inicie a API:

```powershell
alembic upgrade head
uvicorn mythra.main:app --reload --app-dir src
```

A documentação OpenAPI fica disponível em `/docs`; a verificação HTTP básica fica em `/health`.

## Executar com Docker

Copie `.env.example` para `.env`, escolha uma senha local para `POSTGRES_PASSWORD` e execute:

```powershell
docker compose up --build
```

O Compose inicia PostgreSQL e API; a API executa `alembic upgrade head` antes de iniciar o servidor. Credenciais de desenvolvimento não devem ser commitadas.

## Migrations

Alembic é a única ferramenta de alteração estrutural do banco. O esquema (revisões `0001` a `0010`) e o fluxo de propostas de transição estão descritos em [docs/architecture/data-model.md](docs/architecture/data-model.md). Com `MYTHRA_DATABASE_URL` configurada:

```powershell
alembic upgrade head
alembic downgrade -1
```

## Testes e qualidade

Testes unitários não necessitam de banco. Os testes de integração executam migrations e necessitam de um banco PostgreSQL descartável definido por `MYTHRA_TEST_DATABASE_URL`; a suíte reverte as migrations no encerramento. Não aponte essa variável para dados de produção. As migrations da suíte sempre usam `MYTHRA_TEST_DATABASE_URL`, e o pytest usa `--tb=short` para não imprimir parâmetros de conexão (que incluem a senha) em falhas.

```powershell
pytest
ruff check .
mypy src tests
```

## Estrutura

```text
src/mythra/
	api/                 # routers, schemas e dependências HTTP
	core/                # configurações, logging e erros compartilhados
	domain/              # regras e conceitos de negócio
	application/         # casos de uso e portas
	infrastructure/db/   # modelos, repositories, engine e sessão
migrations/            # histórico versionado do PostgreSQL
tests/unit/            # regras puras do domínio
tests/integration/     # API e persistência PostgreSQL reais
docs/                  # arquitetura e decisões da Fase 01
```

## Escopo da Fase 01

Inclui criação e consulta de usuários e entidades narrativas, configuração de preferências, atualização de Story, conhecimento individual, persistência PostgreSQL, constraints relacionais e log append-only de eventos.

Ainda não implementa geração por LLM, autenticação/autorização, engines narrativos, inferência automática de conhecimento, RAG, pgvector, ML, ETL, workers, microserviços, AWS ou frontend.

## Fase 02 — Narrative Core (parcial)

Implementado:

- **Story State**: snapshot tipado e imutável do estado canônico atual (`MythraUseCases.get_story_state`), montado na camada de aplicação a partir das tabelas normalizadas. Não há tabela, JSON, cache ou endpoint HTTP de estado agregado, e o snapshot não contém histórico; `StoryEvent` continua sendo consultado separadamente (`list_story_events`).
- **Transições de estado** com rotas `PATCH` estreitas para Character, CharacterRelationship (`trust`, `status`), CharacterKnowledge (`known_at`, `confidence`, `visibility`), StoryFact, TimelineEvent, PlotThread, StoryArc e Chapter. A criação canônica de fatos continua em `POST /stories/{story_id}/facts`. Identidade e vínculos de história não são editáveis.
- **Eventos**: cada criação ou transição canônica efetiva grava exatamente um `StoryEvent` na mesma transação da mudança de estado e do incremento de `state_version`. O evento registra `sequence`, `source` (`user`, `system` ou `generation`), `operation` e o payload `{"changes": {"campo": {"before": ..., "after": ...}}}`, apenas com campos realmente alterados; na criação, `before` é `null` e campos nulos são omitidos. O log é imutável no banco (triggers rejeitam `UPDATE`, `DELETE` e `TRUNCATE`; só a exclusão em cascata da própria história é permitida). Há casos de uso de consulta de histórico e reconstrução estrita de relações, sem rotas HTTP; detalhes, limitações e o procedimento administrativo em [docs/architecture/data-model.md](docs/architecture/data-model.md), seção 15.
- **PATCH idempotente**: sem mudança efetiva, retorna o recurso atual sem escrita nem evento. Transições rejeitadas não alteram estado nem geram evento.
- **Transação**: a fronteira de caso de uso (`application/transactions.py`) é a única que faz commit/rollback; repositories apenas adicionam e fazem flush.

Lacuna: **Location** e **Faction** não existem no baseline da Fase 01 e foram explicitamente adiados — nenhum schema, API ou código foi inventado para eles. Por isso a Fase 02 não está completa.

Para a visão arquitetural completa (incluindo componentes futuros como Narrative Orchestrator, Story Engine, Memory Engine, Consistency Engine, pipeline de geração e o roadmap de fases), consulte [docs/architecture/phase-01.md](docs/architecture/phase-01.md).
