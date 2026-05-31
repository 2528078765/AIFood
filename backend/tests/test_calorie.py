"""测试用例：BMR / TDEE / 热量目标计算.

纯逻辑层测试，不依赖 HTTP 层。
"""

import pytest


class TestBMRCalculation:
    """基础代谢率计算 — Mifflin-St Jeor 公式."""

    def test_male_bmr(self):
        """男性 BMR 计算: 10×W + 6.25×H - 5×A + 5."""
        from app.services.calorie_service import calculate_bmr

        bmr = calculate_bmr(gender="male", weight_kg=70, height_cm=175, age=28)
        expected = 10 * 70 + 6.25 * 175 - 5 * 28 + 5
        assert bmr == pytest.approx(expected, abs=1)

    def test_female_bmr(self):
        """女性 BMR 计算: 10×W + 6.25×H - 5×A - 161."""
        from app.services.calorie_service import calculate_bmr

        bmr = calculate_bmr(gender="female", weight_kg=55, height_cm=160, age=25)
        expected = 10 * 55 + 6.25 * 160 - 5 * 25 - 161
        assert bmr == pytest.approx(expected, abs=1)

    def test_bmr_edge_weight_zero(self):
        """体重 0 → 报错."""
        from app.services.calorie_service import calculate_bmr

        with pytest.raises(ValueError):
            calculate_bmr(gender="male", weight_kg=0, height_cm=175, age=28)

    def test_bmr_edge_age_zero(self):
        """年龄 0 → 报错."""
        from app.services.calorie_service import calculate_bmr

        with pytest.raises(ValueError):
            calculate_bmr(gender="male", weight_kg=70, height_cm=175, age=0)

    def test_bmr_invalid_gender(self):
        """非法性别 → 报错."""
        from app.services.calorie_service import calculate_bmr

        with pytest.raises(ValueError):
            calculate_bmr(gender="unknown", weight_kg=70, height_cm=175, age=28)


class TestTDEECalculation:
    """每日总消耗计算."""

    def test_tdee_sedentary(self):
        """久坐人群 → BMR × 1.2."""
        from app.services.calorie_service import calculate_tdee

        tdee = calculate_tdee(bmr=1700, activity_level="sedentary")
        assert tdee == pytest.approx(1700 * 1.2, abs=1)

    def test_tdee_moderate(self):
        """中等活跃 → BMR × 1.55."""
        from app.services.calorie_service import calculate_tdee

        tdee = calculate_tdee(bmr=1700, activity_level="moderate")
        assert tdee == pytest.approx(1700 * 1.55, abs=1)

    def test_tdee_default_level(self):
        """不传活动等级 → 默认 1.375（轻度活跃）."""
        from app.services.calorie_service import calculate_tdee

        tdee = calculate_tdee(bmr=1700)
        assert tdee == pytest.approx(1700 * 1.375, abs=1)

    def test_tdee_invalid_level(self):
        """非法活动等级 → 报错."""
        from app.services.calorie_service import calculate_tdee

        with pytest.raises(ValueError):
            calculate_tdee(bmr=1700, activity_level="superman")


class TestCalorieTarget:
    """热量目标计算."""

    def test_lose_fat_target(self):
        """减脂目标 → TDEE × 0.85."""
        from app.services.calorie_service import calculate_daily_target

        target = calculate_daily_target(tdee=2200, goal="lose_fat")
        assert target == pytest.approx(2200 * 0.85, abs=5)

    def test_build_muscle_target(self):
        """增肌目标 → TDEE × 1.1."""
        from app.services.calorie_service import calculate_daily_target

        target = calculate_daily_target(tdee=2200, goal="build_muscle")
        assert target == pytest.approx(2200 * 1.1, abs=5)

    def test_maintain_target(self):
        """维持目标 → TDEE × 1.0."""
        from app.services.calorie_service import calculate_daily_target

        target = calculate_daily_target(tdee=2200, goal="maintain")
        assert target == pytest.approx(2200, abs=5)

    def test_target_invalid_goal(self):
        """非法目标 → 报错."""
        from app.services.calorie_service import calculate_daily_target

        with pytest.raises(ValueError):
            calculate_daily_target(tdee=2200, goal="unknown")


class TestMealDistribution:
    """三餐热量分配."""

    def test_three_meals_sum_equals_target(self):
        """三餐热量之和 ≈ 每日总目标."""
        from app.services.calorie_service import distribute_meals

        meals = distribute_meals(daily_target=2000)
        total = meals["breakfast"] + meals["lunch"] + meals["dinner"]
        assert total == pytest.approx(2000, abs=10)

    def test_distribution_ratio(self):
        """早餐30% 午餐40% 晚餐30%."""
        from app.services.calorie_service import distribute_meals

        meals = distribute_meals(daily_target=2000)
        assert meals["breakfast"] == pytest.approx(600, abs=10)
        assert meals["lunch"] == pytest.approx(800, abs=10)
        assert meals["dinner"] == pytest.approx(600, abs=10)
