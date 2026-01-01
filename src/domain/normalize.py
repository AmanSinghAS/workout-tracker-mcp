from __future__ import annotations

import re
from typing import Literal, TypedDict


class WeightInput(TypedDict):
    value: float
    unit: Literal["lb", "kg"]


def normalize_canonical_name(name: str) -> str:
    collapsed = re.sub(r"\s+", " ", name.strip().lower())
    return collapsed


def weight_to_kg(weight: WeightInput | None) -> float | None:
    if weight is None:
        return None
    value = weight["value"]
    if weight["unit"] == "kg":
        return value
    return value * 0.45359237
