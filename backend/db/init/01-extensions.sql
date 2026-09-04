-- Several tables declare `server_default=func.uuid_generate_v4()`, which needs
-- this extension present before SQLAlchemy creates them.
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
