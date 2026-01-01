import json

from sqlalchemy.orm import Session

from src.db.session import engine
from src.mcp_server import handle_add_workout_entry


if __name__ == "__main__":
    with open("examples/sample_workout.json") as f:
        payload = json.load(f)

    with Session(engine) as session:
        result = handle_add_workout_entry(payload, session)
        print(result)
