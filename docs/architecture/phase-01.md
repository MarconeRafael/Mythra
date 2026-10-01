# Arquitetura — Fase 01

## Limites

O sistema é um monólito modular. A API REST FastAPI traduz HTTP para casos de uso; a aplicação coordena operações por interfaces de persistência; a infraestrutura implementa essas interfaces com SQLAlchemy 2.x e PostgreSQL. O domínio contém invariantes sem importar FastAPI ou SQLAlchemy.

## Autoridade do estado

As entidades canônicas são relacionais. O estado atual permanece em suas tabelas próprias e `StoryEvent` registra acontecimentos históricos append-only, sem Event Sourcing completo. JSONB está restrito ao payload variável do evento.

> **A LLM nunca será a autoridade final sobre o estado narrativo.** O estado canônico pertence ao sistema e é persistido no PostgreSQL — não em uma saída de modelo generativo.

## Persistência

UUID identifica entidades. Tabelas mutáveis possuem timestamps timezone-aware `created_at` e `updated_at`; o histórico imutável não possui `updated_at`. Chaves estrangeiras, unicidade e checks críticos são aplicados pelo PostgreSQL. Alembic versiona todas as mudanças estruturais.

## Current State + Immutable Event Log

O modelo de estado combina dois mecanismos complementares, sem implementar Event Sourcing completo:

```
Current State
+
Immutable Event Log
```

- **Current State**: cada entidade narrativa (`Story`, `Character`, `CharacterRelationship`, `StoryArc`, `Chapter`, `TimelineEvent`, `PlotThread`, etc.) é persistida em sua própria tabela relacional e representa o estado **atual**. Atualizações substituem o valor corrente (via `updated_at`), sem manter histórico de versões anteriores na própria tabela.
- **Immutable Event Log**: `StoryEvent` é append-only e registra o histórico de acontecimentos relevantes (`story_created`, `character_created`, `chapter_created`, `relationship_changed`, etc.). Eventos nunca são atualizados ou apagados pela API normal. `payload` usa JSONB por ser um registro histórico com dados variáveis.

Isso é implementado na Fase 01. O estado atual nunca é derivado apenas do log de eventos — ele é persistido diretamente nas entidades, e o log serve como histórico auditável, não como fonte única de verdade.

## Character Knowledge

`CharacterKnowledge` é um conceito de domínio de primeira classe, não um detalhe de implementação. Ele modela que o conhecimento sobre um fato narrativo é individual por personagem, e não uma propriedade global da história:

```
A knows fact X
B does not know fact X
C suspects fact X
D knows fact X with lower confidence
```

Cada registro de `CharacterKnowledge` vincula uma `Character` a um `StoryFact`, com `confidence` (0.0–1.0), `visibility` e o `StoryEvent` de origem (`source_event_id`) que originou esse conhecimento. Um fato (`StoryFact`) continua existindo independentemente de alguma personagem conhecê-lo. Implementado na Fase 01; a inferência automática de conhecimento (quem passa a saber o quê, automaticamente, a partir de eventos) é explicitamente adiada para fases futuras.

## Fatos canônicos vs. memória semântica (futuro)

Dois níveis de memória são distinguidos pela arquitetura alvo:

- **Fatos canônicos** (`StoryFact` + `CharacterKnowledge`): estrutura relacional, implementada nesta fase, representando fatos discretos (`subject`/`predicate`/`object`) e o conhecimento individual sobre eles.
- **Memória semântica** (futura): uma camada baseada em embeddings/busca vetorial (`pgvector` / RAG, conforme o diagrama de arquitetura original) para recuperação de contexto narrativo por similaridade semântica, a ser usada pelo Memory Engine na geração. **Não implementada nesta fase** — `pgvector` e qualquer vector database estão explicitamente fora do escopo da Fase 01.

## Arquitetura alvo (futuro, não implementado)

A arquitetura completa do Mythra, da qual a Fase 01 é a fundação, é:

```
Client / UI
      ↓
FastAPI
      ↓
Narrative Orchestrator
      ├── Story Engine
      ├── Memory Engine
      └── Consistency Engine
      ↓
PostgreSQL
      ├── canonical state
      ├── chapters
      ├── characters
      ├── events
      ├── memories
      └── evaluation
      ↓
pgvector / RAG
      ↓
LLM / ML
```

Os componentes abaixo são citados apenas como contexto arquitetural futuro. **Nenhum deles é implementado, mockado ou possui classe vazia nesta fase**:

- **Narrative Orchestrator**: componente futuro que coordenará Story Engine, Memory Engine e Consistency Engine durante a geração.
- **Story Engine**: componente futuro responsável pela geração/condução da narrativa.
- **Memory Engine**: componente futuro responsável por recuperar memória canônica e semântica relevante para a geração (inclui a camada de memória semântica descrita acima).
- **Consistency Engine**: componente futuro responsável por validar a consistência do conteúdo gerado contra o estado canônico antes da transição de estado.
- **Narrative Planner / Planning**: etapa futura do pipeline de geração (ver abaixo) responsável por planejar a geração antes da montagem de contexto. A especificação original se refere a essa etapa como "Planning" dentro do fluxo de geração.

## Pipeline de geração futuro (não implementado)

```
Canonical State
      ↓
Planning
      ↓
Context Assembly
      ↓
LLM
      ↓
Generated Draft
      ↓
Validation
      ↓
State Transition
      ↓
Canonical State atualizado
```

Não existe geração por LLM nesta fase. Este fluxo é documentado como contexto para as fases futuras de geração (Fase 03) e memória/consistência (Fase 04), e não deve ser antecipado na implementação atual.

## Human-in-the-loop

A visão de produto do Mythra inclui controle humano sobre transições de estado canônico (humano aprova/edita antes que um rascunho gerado se torne estado canônico). Esse mecanismo pertence à Fase 05 (Human-in-the-loop) e não está implementado nesta fase — não há endpoints de aprovação, rascunho ou edição assistida na Fase 01.

## Telemetria, avaliação, dados e ML (futuro)

A especificação do produto prevê, em fases futuras, telemetria e avaliação de qualidade narrativa, engenharia de dados/ETL e pipelines de ML para apoiar geração e consistência. Nenhuma dessas capacidades, dependências (ex.: Airflow, Prefect, Spark, PyTorch, TensorFlow, Hugging Face) ou infraestrutura associada (ex.: AWS, Kubernetes) está presente nesta fase.

## Roadmap de fases

```
FASE 01  Foundation                 (esta fase)
FASE 02  Narrative Core
FASE 03  Generation
FASE 04  Memory + Consistency
FASE 05  Human-in-the-loop
FASE 06  Evaluation + Telemetry
FASE 07  Data Engineering
FASE 08  ML
FASE 09  Production
FASE 10  AWS
```

## Escopo da Fase 01

Implementado: User, Story, StoryPreferences, Character, CharacterRelationship, StoryFact, CharacterKnowledge, StoryArc, Chapter, TimelineEvent, PlotThread e StoryEvent, com API REST, persistência PostgreSQL via SQLAlchemy 2.x/Alembic, constraints relacionais e testes unitários/integração reais.

## Componentes fora do escopo

Não há geração, LLM, RAG, pgvector, ML, ETL, autenticação, filas, microserviços ou integração de nuvem nesta fase. Os componentes futuros (Narrative Orchestrator, Story Engine, Memory Engine, Consistency Engine, Narrative Planner, pipeline de geração, human-in-the-loop, telemetria/avaliação/dados/ML) estão documentados acima apenas como contexto arquitetural; nenhum é implementado, mockado ou representado por classes vazias nesta fase.