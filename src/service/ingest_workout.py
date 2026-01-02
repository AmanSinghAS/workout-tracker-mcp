from __future__ import annotations

import uuid
from datetime import date, timezone
from typing import Dict

from sqlalchemy import func, literal_column, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, selectinload

from src.db.models import AppUser, Exercise, Workout, WorkoutExercise, WorkoutSet
from src.domain.payloads import (
    ExerciseInput,
    WorkoutByDateRequest,
    WorkoutIngestPayload,
    validate_payload,
)


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


def _next_ordinal(session: Session, workout_id: uuid.UUID) -> int:
    current_max = session.execute(
        select(func.max(WorkoutExercise.ordinal)).where(WorkoutExercise.workout_id == workout_id)
    ).scalar_one_or_none()
    return (current_max or -1) + 1


def _workout_date_from_started(started_at) -> date:
    return started_at.astimezone(timezone.utc).date()


def ingest_workout(session: Session, payload: Dict | WorkoutIngestPayload) -> Dict:
    if isinstance(payload, WorkoutIngestPayload):
        data = payload
    else:
        data = validate_payload(payload)

    written_workout_exercises = 0
    written_sets = 0

    with session.begin():
        _ensure_user(session, data.user_id)

        workout_date = _workout_date_from_started(data.workout.started_at)

        if data.idempotency_key:
            idempotent_match = session.execute(
                select(Workout.id).where(
                    Workout.user_id == data.user_id, Workout.idempotency_key == data.idempotency_key
                )
            ).scalar_one_or_none()
            if idempotent_match:
                return {
                    "workout_id": str(idempotent_match),
                    "written_workout_exercises": 0,
                    "written_sets": 0,
                    "idempotent_replay": True,
                    "appended_to_existing": False,
                }

        workout_data = {
            "id": uuid.uuid4(),
            "user_id": data.user_id,
            "workout_date": workout_date,
            "started_at": data.workout.started_at,
            "ended_at": data.workout.ended_at,
            "timezone": data.workout.timezone,
            "title": data.workout.title,
            "source": data.workout.source,
            "notes": data.workout.notes,
            "idempotency_key": data.idempotency_key,
        }

        existing_workout = session.execute(
            select(Workout).where(
                Workout.user_id == data.user_id,
                Workout.workout_date == workout_date,
            )
        ).scalar_one_or_none()

        appended_to_existing = False
        if existing_workout:
            workout_id = existing_workout.id
            appended_to_existing = True
            if data.idempotency_key and existing_workout.idempotency_key is None:
                existing_workout.idempotency_key = data.idempotency_key
            ordinal_start = _next_ordinal(session, workout_id)
        else:
            insert_stmt = pg_insert(Workout).values(**workout_data).returning(
                Workout.id, literal_column("xmax = 0").label("inserted")
            )
            result = session.execute(insert_stmt).one()
            workout_id = result.id
            appended_to_existing = not result.inserted
            ordinal_start = 0
            if appended_to_existing:
                # A concurrent insert for the same day happened. Grab the persisted row.
                existing_workout = session.get(Workout, workout_id)
                if data.idempotency_key and existing_workout and existing_workout.idempotency_key is None:
                    existing_workout.idempotency_key = data.idempotency_key

        for offset, exercise in enumerate(data.exercises):
            ordinal = ordinal_start + offset
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
        "appended_to_existing": appended_to_existing,
    }


def get_workout_for_day(
    session: Session, payload: Dict | WorkoutByDateRequest
) -> Dict:
    if isinstance(payload, WorkoutByDateRequest):
        request = payload
    else:
        request = WorkoutByDateRequest.model_validate(payload)

    workout_date = request.workout_date

    with session.begin():
        workout = (
            session.execute(
                select(Workout)
                .where(
                    Workout.user_id == request.user_id,
                    Workout.workout_date == workout_date,
                )
                .options(
                    selectinload(Workout.exercises)
                    .options(
                        selectinload(WorkoutExercise.exercise),
                        selectinload(WorkoutExercise.sets),
                    )
                )
            )
            .scalars()
            .first()
        )

        if not workout:
            return {"workout": None}

        exercises = []
        for ex in sorted(workout.exercises, key=lambda e: e.ordinal):
            exercise_info = {
                "workout_exercise_id": str(ex.id),
                "exercise_id": str(ex.exercise_id),
                "display_name": ex.exercise.display_name if ex.exercise else None,
                "canonical_name": ex.exercise.canonical_name if ex.exercise else None,
                "notes": ex.notes,
                "ordinal": ex.ordinal,
                "sets": [],
            }
            for ws in sorted(ex.sets, key=lambda s: s.set_index):
                exercise_info["sets"].append(
                    {
                        "workout_set_id": str(ws.id),
                        "set_index": ws.set_index,
                        "reps": ws.reps,
                        "weight_kg": ws.weight_kg,
                        "weight_original_value": ws.weight_original_value,
                        "weight_original_unit": ws.weight_original_unit,
                        "rpe": ws.rpe,
                        "rir": ws.rir,
                        "is_warmup": ws.is_warmup,
                        "tempo": ws.tempo,
                        "rest_seconds": ws.rest_seconds,
                        "notes": ws.notes,
                        "logged_at": ws.logged_at.isoformat() if ws.logged_at else None,
                    }
                )
            exercises.append(exercise_info)

        return {
            "workout": {
                "workout_id": str(workout.id),
                "user_id": str(workout.user_id),
                "workout_date": workout.workout_date.isoformat(),
                "started_at": workout.started_at.isoformat() if workout.started_at else None,
                "ended_at": workout.ended_at.isoformat() if workout.ended_at else None,
                "timezone": workout.timezone,
                "title": workout.title,
                "source": workout.source,
                "notes": workout.notes,
                "exercises": exercises,
            }
        }
