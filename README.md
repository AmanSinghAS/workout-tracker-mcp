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


## Run MCP server
Start the MCP server (streamable HTTP transport):
```
python3 server.py
```

### Authentication
The server requires Google OIDC ID tokens (any Google client ID is accepted, as long as the token is signed by Google and the email is verified and allowlisted). Configure:
```
# Optional: path to the allowlist file (defaults to ./allowed_emails.txt)
export ALLOWED_EMAILS_FILE="allowed_emails.txt"
```

The allowlist file contains one email per line (commas also allowed on a line). A default `allowed_emails.txt` is included with `amansinghdallas.03@gmail.com`.

To obtain an ID token for local testing, use either a browser-based login or `gcloud`:
```
gcloud auth application-default login
gcloud auth print-identity-token --audiences "<any Google OAuth client ID you control>"
```

Send the token in the `Authorization` header for all MCP requests, for example:
```
curl -H "Authorization: Bearer $(gcloud auth print-identity-token --audiences \"<any Google OAuth client ID you control>\")" \
     http://localhost:8000/mcp
```

## MCP tool payload example
Payload for `add_workout_entry`:
```json
{
  "user_id": "b8d932e9-26ef-4f2d-8b7f-cc1e0a3e3b2c",
  "idempotency_key": "workout-2024-09-01-1",
  "workout": {
    "started_at": "2024-09-01T10:00:00Z",
    "ended_at": "2024-09-01T11:00:00Z",
    "timezone": "America/Los_Angeles",
    "title": "Upper Body",
    "source": "manual",
    "notes": "Felt strong"
  },
  "exercises": [
    {
      "display_name": "Bench Press",
      "canonical_name": "bench press",
      "notes": "Working sets",
      "sets": [
        {"reps": 8, "weight": {"value": 135, "unit": "lb"}, "rpe": 7.5},
        {"reps": 6, "weight": {"value": 62.5, "unit": "kg"}, "rpe": 8.0}
      ]
    }
  ]
}
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


## Cloud Run deployment (CI/CD)
The GitHub Actions workflow deploys to Cloud Run on pushes to `main`.

### Required GitHub secrets
- `GCP_WORKLOAD_IDENTITY_PROVIDER`
- `GCP_SERVICE_ACCOUNT_EMAIL`
- `DB_PASSWORD`

### GCP setup checklist
1. Create an Artifact Registry repo named `workout-tracker-mcp` in `us-central1`.
2. Create a Cloud SQL Postgres instance named `workout-tracker-postgres` in `us-central1`.
3. Create database `workout_tracker` and user `postgres` (or update the workflow vars).
4. Configure Workload Identity Federation for GitHub Actions and grant the service account:
   - `roles/run.admin`
   - `roles/iam.serviceAccountUser`
   - `roles/artifactregistry.writer`
   - `roles/cloudsql.client`

The workflow file is `/.github/workflows/deploy-cloudrun.yml`.
