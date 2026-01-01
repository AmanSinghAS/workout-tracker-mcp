import uuid
from datetime import datetime, timedelta, timezone

import pytest

from src.domain.payloads import validate_payload


def base_payload():
    return {
        "user_id": str(uuid.uuid4()),
        "workout": {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "ended_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        },
        "exercises": [
            {
                "display_name": "Squat",
                "sets": [{"reps": 5}],
            }
        ],
    }


def test_ended_before_started():
    payload = base_payload()
    payload["workout"]["ended_at"] = (
        datetime.now(timezone.utc) - timedelta(minutes=10)
    ).isoformat()
    with pytest.raises(ValueError):
        validate_payload(payload)


def test_reps_must_be_positive():
    payload = base_payload()
    payload["exercises"][0]["sets"][0]["reps"] = 0
    with pytest.raises(ValueError):
        validate_payload(payload)


def test_exercises_cannot_be_empty():
    payload = base_payload()
    payload["exercises"] = []
    with pytest.raises(ValueError):
        validate_payload(payload)
