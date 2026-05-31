"""BMR / TDEE / 每日热量目标 / 三餐分配计算."""

from datetime import date


def calculate_age(birthday: date) -> int:
    today = date.today()
    age = today.year - birthday.year - ((today.month, today.day) < (birthday.month, birthday.day))
    return max(age, 0)


def calculate_bmr(*, gender: str, weight_kg: float, height_cm: float, age: int) -> float:
    """Mifflin-St Jeor 公式."""
    if weight_kg <= 0:
        raise ValueError("weight_kg must be positive")
    if height_cm <= 0:
        raise ValueError("height_cm must be positive")
    if age <= 0:
        age = 25  # 无法计算时使用默认年龄
    if gender == "male":
        return 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
    elif gender == "female":
        return 10 * weight_kg + 6.25 * height_cm - 5 * age - 161
    raise ValueError(f"Unknown gender: {gender}")


ACTIVITY_MULTIPLIERS = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "active": 1.725,
    "very_active": 1.9,
}


def calculate_tdee(*, bmr: float, activity_level: str = "light") -> float:
    """TDEE = BMR × 活动系数."""
    if activity_level not in ACTIVITY_MULTIPLIERS:
        raise ValueError(f"Unknown activity_level: {activity_level}")
    return bmr * ACTIVITY_MULTIPLIERS[activity_level]


GOAL_MULTIPLIERS = {
    "lose_fat": 0.85,
    "build_muscle": 1.1,
    "maintain": 1.0,
}


def calculate_daily_target(*, tdee: float, goal: str) -> int:
    """根据目标调整每日热量."""
    if goal not in GOAL_MULTIPLIERS:
        raise ValueError(f"Unknown goal: {goal}")
    return round(tdee * GOAL_MULTIPLIERS[goal])


def distribute_meals(*, daily_target: int) -> dict[str, int]:
    """早餐 30% / 午餐 40% / 晚餐 30%."""
    return {
        "breakfast": round(daily_target * 0.3),
        "lunch": round(daily_target * 0.4),
        "dinner": round(daily_target * 0.3),
    }


def calculate_user_daily_target(
    *, gender: str, weight_kg: float, height_cm: float, birthday: date, goal: str
) -> int:
    """一站式：从用户身体数据算出每日热量目标."""
    age = calculate_age(birthday)
    bmr = calculate_bmr(gender=gender, weight_kg=weight_kg, height_cm=height_cm, age=age)
    tdee = calculate_tdee(bmr=bmr)
    return calculate_daily_target(tdee=tdee, goal=goal)
