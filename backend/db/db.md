# db — declarative base

[← Back to BACKEND.md](../BACKEND.md) · [API reference](db_API_DOCS.md)

One module, one line: the SQLAlchemy declarative base every ORM model inherits.

## Why it is its own package

It would be natural to define `Base` inside `data_models/`. Keeping it separate
breaks a circular import that otherwise appears immediately:

```
  data_models/session.py  needs  Base.metadata   (to create tables)
  data_models/users.py    needs  Base            (to declare the model)
  data_models/session.py  is imported by         users.py's consumers
```

With `Base` in its own leaf module that depends on nothing, the graph stays
acyclic: `db.base` ← `data_models.*` ← application code. Every model module can
import it without pulling in the engine, and `db.base` never imports anything of
the project's own.

The second reason is that `Base.metadata` is the single registry of every table.
Anything that wants to create, drop, or reflect the schema imports one object,
and `create_all` covers whatever has been imported.

## Design note

The package is deliberately empty of behaviour. Adding a shared mixin here —
timestamps, soft deletes, a `user_id` convention — is the natural extension
point, and would apply to every model at once:

```python
class TimestampMixin:
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
```

That has not been done; each model declares its own `created_at` today.

## Related

The `db/init/` directory holds SQL executed once by the PostgreSQL container on
first initialisation — currently just enabling `uuid-ossp`, which the UUID
primary keys require.
