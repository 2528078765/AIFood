"""Estimate body fat percentage from height, weight, and strength stats."""

import re
from datetime import date


def estimate_body_fat(
    *,
    height_cm: float | None = None,
    weight_kg: float | None = None,
    gender: str | None = None,
    birthday: date | None = None,
    exercise_details: str | None = None,
) -> dict:
    """Estimate body fat % from body metrics and exercise details.

    Uses BMI + age + gender as baseline, then adjusts based on
    strength-to-weight ratios extracted from exercise_details.
    """
    result: dict = {"body_fat_pct": None, "bmi": None, "ffmi": None, "strength_level": None}

    # 1. BMI
    if height_cm and weight_kg and height_cm > 0:
        height_m = height_cm / 100
        bmi = weight_kg / (height_m ** 2)
        result["bmi"] = round(bmi, 1)
    else:
        return result

    # 2. Age
    age = 25  # default
    if birthday:
        today = date.today()
        age = today.year - birthday.year - (
            (today.month, today.day) < (birthday.month, birthday.day)
        )
        age = max(age, 15)

    bmi = result["bmi"]
    is_male = gender == "male"
    gender_factor = 1 if is_male else 0

    # 3. Base body fat % — Deurenberg equation
    base_bf = 1.2 * bmi + 0.23 * age - 10.8 * gender_factor - 5.4
    base_bf = max(3.0, min(base_bf, 50.0))  # clamp

    # 4. Parse exercise details for strength stats
    strength_adj = 0.0
    strength_level = "unknown"

    if exercise_details and weight_kg:
        lifts = _parse_lifts(exercise_details)
        if lifts:
            ratios = {k: v / weight_kg for k, v in lifts.items()}
            strength_level, strength_adj = _strength_adjustment(ratios, is_male)

    body_fat = round(base_bf + strength_adj, 1)
    body_fat = max(3.0, min(body_fat, 50.0))

    result["body_fat_pct"] = body_fat
    result["strength_level"] = strength_level

    # 5. FFMI (Fat-Free Mass Index)
    if body_fat and bmi:
        lean_mass = weight_kg * (1 - body_fat / 100)
        ffmi = lean_mass / ((height_cm / 100) ** 2)
        result["ffmi"] = round(ffmi, 1)

    return result


def _parse_lifts(text: str) -> dict[str, float]:
    """Extract lifts in kg from free-text exercise details.

    Supports: 卧推 90kg, 深蹲 100kg, 硬拉 120kg, bench/squat/deadlift.
    """
    lifts: dict[str, float] = {}
    patterns = [
        (r"(?:卧推|bench\s?press?)[^\d]*(\d+(?:\.\d+)?)\s*(?:kg|公斤)", "bench"),
        (r"(?:深蹲|squat)[^\d]*(\d+(?:\.\d+)?)\s*(?:kg|公斤)", "squat"),
        (r"(?:硬拉|deadlift|dead\s?lift)[^\d]*(\d+(?:\.\d+)?)\s*(?:kg|公斤)", "deadlift"),
        (r"(?:推举|overhead\s?press|ohp)[^\d]*(\d+(?:\.\d+)?)\s*(?:kg|公斤)", "ohp"),
    ]
    for pat, key in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            lifts[key] = float(m.group(1))
    return lifts


def _strength_adjustment(ratios: dict[str, float], is_male: bool) -> tuple[str, float]:
    """Estimate strength level and body fat adjustment from strength-to-weight ratios.

    Reference: Intermediate/Advanced/Elite standards (approximate).
    Returns (strength_level, body_fat_adjustment).
    """
    # Use bench + squat if available, otherwise whatever we have
    bench_ratio = ratios.get("bench", 0)
    squat_ratio = ratios.get("squat", 0)
    dl_ratio = ratios.get("deadlift", 0)

    # Composite score: average of available ratios, weighted
    available = [v for v in [bench_ratio, squat_ratio, dl_ratio] if v > 0]
    if not available:
        return "unknown", 0.0

    avg_ratio = sum(available) / len(available)

    # Strength classification (male standards, slightly lower for female)
    if is_male:
        if avg_ratio >= 2.0:
            level = "elite"
            adj = -6.0
        elif avg_ratio >= 1.6:
            level = "advanced"
            adj = -4.0
        elif avg_ratio >= 1.2:
            level = "intermediate"
            adj = -2.0
        elif avg_ratio >= 0.8:
            level = "novice"
            adj = 0.0
        else:
            level = "beginner"
            adj = 1.0
    else:
        if avg_ratio >= 1.6:
            level = "elite"
            adj = -5.0
        elif avg_ratio >= 1.3:
            level = "advanced"
            adj = -3.0
        elif avg_ratio >= 1.0:
            level = "intermediate"
            adj = -1.5
        elif avg_ratio >= 0.6:
            level = "novice"
            adj = 0.0
        else:
            level = "beginner"
            adj = 1.0

    return level, adj
