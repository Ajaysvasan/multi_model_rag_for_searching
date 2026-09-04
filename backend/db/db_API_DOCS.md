# db — API reference

[← Back to BACKEND.md](../BACKEND.md) · [Design notes](db.md)

## `Base`

```python
from db.base import Base
```

The SQLAlchemy declarative base. Every ORM model in `data_models/` inherits it.

## Declaring a model

```python
import uuid
from sqlalchemy import Column, ForeignKey, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from db.base import Base

class Annotation(Base):
    __tablename__ = "annotations"

    id = Column(UUID(as_uuid=True), primary_key=True,
                server_default=func.uuid_generate_v4())
    # Carry user_id on anything user-owned: it is the isolation boundary.
    user_id = Column(UUID(as_uuid=True),
                     ForeignKey("users.id", ondelete="CASCADE"),
                     nullable=False, index=True)
    chunk_id = Column(Text, ForeignKey("chunks.id", ondelete="CASCADE"),
                      nullable=False, index=True)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
```

## Creating the schema

```python
from db.base import Base
from data_models.session import engine

# Import every model module first: create_all only creates what is registered.
import data_models.users
import data_models.chunks
import data_models.cache
import data_models.history

Base.metadata.create_all(bind=engine)
```

`uuid-ossp` must exist before this runs, because the UUID columns default to
`uuid_generate_v4()`:

```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
```

Under Docker this is applied automatically from `db/init/01-extensions.sql`.

## Inspecting the registry

```python
from db.base import Base

list(Base.metadata.tables)                      # every registered table name
Base.metadata.tables["chunks"].columns.keys()   # column names
Base.metadata.sorted_tables                     # FK-safe creation order
```

## Dropping everything

Destructive; development only:

```python
Base.metadata.drop_all(bind=engine)
```

## Note

There is no migration tooling. `create_all` creates missing tables but never
alters existing ones — adding a column to a model does not change a live
database. Apply such changes by hand, or introduce Alembic:

```bash
pip install alembic
alembic init migrations   # point target_metadata at db.base:Base
```
