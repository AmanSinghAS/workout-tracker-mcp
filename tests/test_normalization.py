import uuid

from src.domain.payloads import validate_payload


def test_canonical_name_normalization():
    payload = {
        "user_id": str(uuid.uuid4()),
        "workout": {"started_at": "2024-09-01T10:00:00Z"},
        "exercises": [
            {
                "display_name": " Bench   Press ",
                "canonical_name": None,
                "sets": [{"reps": 8}],
            }
        ],
    }

    parsed = validate_payload(payload)
    assert parsed.exercises[0].normalized_canonical_name() == "bench press"
