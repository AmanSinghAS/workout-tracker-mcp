from __future__ import annotations

import uuid
from typing import Dict

from sqlalchemy import insert, select, text
from sqlalchemy.orm import Session

from src.db.models import AppUser, Exercise, Workout, WorkoutExercise, WorkoutSet
from src.domain.payloads import ExerciseInput, WorkoutIngestPayload, validate_payload


def _ensure_user(session: Session, user_id: uuid.UUID) -> AppUser:
    user = session.get(AppUser, user_id)
    if user:
        return user
    user = AppUser(id=user_id)
    session.add(user)
    session.flush()
    return user


def _resolve_exercise_id(session: Session, user_id: uuid.UUID, exercise: ExerciseInput) -> uuid.UUID:
    canonical_name = exercise.normalized_canonical_name()
    if exercise.exercise_id:
        existing = session.get(Exercise, exercise.exercise_id)
        if existing:
            return existing.id
        new_exercise = Exercise(
            id=exercise.exercise_id,
            owner_user_id=user_id,
            canonical_name=canonical_name,
            display_name=exercise.display_name,
        )
        session.add(new_exercise)
        session.flush()
        return new_exercise.id

    stmt = select(Exercise.id).where(
        Exercise.owner_user_id == user_id, Exercise.canonical_name == canonical_name
    )
    existing_id = session.execute(stmt).scalar_one_or_none()
    if existing_id:
        return existing_id

    new_exercise = Exercise(
        owner_user_id=user_id,
        canonical_name=canonical_name,
        display_name=exercise.display_name,
    )
    session.add(new_exercise)
    session.flush()
    return new_exercise.id


def ingest_workout(session: Session, payload: Dict | WorkoutIngestPayload) -> Dict:
    if isinstance(payload, WorkoutIngestPayload):
        data = payload
    else:
        data = validate_payload(payload)

    written_workout_exercises = 0
    written_sets = 0

    with session.begin():
        _ensure_user(session, data.user_id)

        workout_data = {
            "id": uuid.uuid4(),
            "user_id": data.user_id,
            "started_at": data.workout.started_at,
            "ended_at": data.workout.ended_at,
            "timezone": data.workout.timezone,
            "title": data.workout.title,
            "source": data.workout.source,
            "notes": data.workout.notes,
            "idempotency_key": data.idempotency_key,
        }

        idempotent_replay = False
        if data.idempotency_key:
            insert_stmt = insert(Workout).values(**workout_data)
            upsert_stmt = (
                insert_stmt.on_conflict_do_update(
                    index_elements=[Workout.user_id, Workout.idempotency_key],
                    set_={"idempotency_key": insert_stmt.excluded.idempotency_key},
                )
                .returning(Workout.id, text("xmax = 0").label("inserted"))
            )
            result = session.execute(upsert_stmt).one()
            workout_id = result.id
            inserted = result.inserted
            if not inserted:
                idempotent_replay = True
        else:
            insert_stmt = insert(Workout).values(**workout_data).returning(Workout.id)
            workout_id = session.execute(insert_stmt).scalar_one()

        if idempotent_replay:
            return {
                "workout_id": str(workout_id),
                "written_workout_exercises": 0,
                "written_sets": 0,
                "idempotent_replay": True,
            }

        for ordinal, exercise in enumerate(data.exercises):
            exercise_id = _resolve_exercise_id(session, data.user_id, exercise)
            workout_exercise = WorkoutExercise(
                workout_id=workout_id,
                exercise_id=exercise_id,
                ordinal=ordinal,
                notes=exercise.notes,
            )
            session.add(workout_exercise)
            session.flush()
            written_workout_exercises += 1

            for set_index, set_data in enumerate(exercise.sets):
                weight_kg, weight_original_value, weight_original_unit = set_data.weight_values()
                workout_set = WorkoutSet(
                    workout_exercise_id=workout_exercise.id,
                    set_index=set_index,
                    reps=set_data.reps,
                    weight_kg=weight_kg,
                    weight_original_value=weight_original_value,
                    weight_original_unit=weight_original_unit,
                    rpe=set_data.rpe,
                    rir=set_data.rir,
                    is_warmup=set_data.is_warmup,
                    tempo=set_data.tempo,
                    rest_seconds=set_data.rest_seconds,
                    notes=set_data.notes,
                )
                session.add(workout_set)
                written_sets += 1

    return {
        "workout_id": str(workout_id),
        "written_workout_exercises": written_workout_exercises,
        "written_sets": written_sets,
        "idempotent_replay": False,
    }
