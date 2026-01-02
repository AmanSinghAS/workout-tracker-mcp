import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from src.db.models import Workout
from src.mcp_server import handle_add_workout_entry, handle_get_workout_for_day


def test_mcp_tool_handler_writes_workout(db_session):
    payload = {
        "user_id": str(uuid.uuid4()),
        "idempotency_key": "handler-test",
        "workout": {"started_at": datetime.now(timezone.utc).isoformat()},
        "exercises": [
            {
                "display_name": "Pull Up",
                "sets": [{"reps": 6}],
            }
        ],
    }

    result = handle_add_workout_entry(payload, db_session)

    assert result["idempotent_replay"] is False
    assert result["written_workout_exercises"] == 1
    assert result["written_sets"] == 1

    workout_id = uuid.UUID(result["workout_id"])
    stored = db_session.execute(select(Workout).where(Workout.id == workout_id)).scalar_one()
    assert stored is not None


def test_get_workout_for_day_handler_returns_day(db_session):
    user_id = uuid.uuid4()
    workout_date = "2024-09-03"
    payload = {
        "user_id": str(user_id),
        "idempotency_key": "handler-get-test",
        "workout": {"started_at": f"{workout_date}T09:00:00Z"},
        "exercises": [
            {
                "display_name": "Squat",
                "sets": [{"reps": 5, "weight": {"value": 100, "unit": "kg"}}],
            }
        ],
    }

    handle_add_workout_entry(payload, db_session)
    response = handle_get_workout_for_day({"user_id": str(user_id), "workout_date": workout_date}, db_session)

    assert response["workout"]["workout_date"] == workout_date
    assert response["workout"]["exercises"][0]["display_name"] == "Squat"
