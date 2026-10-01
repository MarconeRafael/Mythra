# Decisões registradas — Fase 01

- Persistência PostgreSQL relacional com SQLAlchemy 2.x e migrations Alembic.
- Identificadores UUID; timestamps de auditoria timezone-aware em UTC.
- `CharacterRelationship.trust` pertence a [-1, 1] e source/target precisam pertencer à história declarada.
- `CharacterKnowledge.confidence` pertence a [0, 1] e cada par personagem/fato é único.
- `PlotThread.status` aceita `open`, `resolved` ou `abandoned`; outros campos de tipo/status sem vocabulário definido permanecem strings.
- `Chapter` referencia um arco da mesma história; a constraint composta é aplicada no PostgreSQL.
- `StoryEvent` aceita inserção e consulta pela API, sem rotas de atualização ou remoção.
- Preferências e campos narrativos ficam em colunas relacionais; somente `StoryEvent.payload` utiliza JSONB.