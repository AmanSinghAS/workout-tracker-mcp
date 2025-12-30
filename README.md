# Workout Tracker SoR (Postgres)

Implements the database schema, ingestion payload validation, and transactional write path for the Workout Tracker MCP tool.

## Prerequisites
- Python 3.11+
- PostgreSQL (local or container)
- `DATABASE_URL` environment variable pointing to your database, e.g.
  ```
  export DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/workout_tracker
  ```

## Setup
1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
2. Configure your database URL via `DATABASE_URL`.

## Migrations
Run Alembic migrations to create the schema:
```
alembic upgrade head
```

## Demo ingestion
A small helper script can be run from a Python shell:
```python
from sqlalchemy.orm import Session
from src.db.session import engine
from src.service.ingest_workout import ingest_workout
import json

with open("examples/sample_workout.json") as f:
    payload = json.load(f)

with Session(engine) as session:
    result = ingest_workout(session, payload)
    print(result)
```

## Tests
Tests expect a live PostgreSQL database available via `DATABASE_URL`. They will skip if the variable is not set.
```
pytest
```

## JSON schema
To export the JSON schema for the ingestion payload:
```python
from src.domain.payloads import workout_payload_schema
import json

print(json.dumps(workout_payload_schema(), indent=2))
```
