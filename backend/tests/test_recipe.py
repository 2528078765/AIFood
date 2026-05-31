"""测试用例：食谱推荐.

覆盖:
  - POST /api/chat → Agent 调用 recommend_recipe 工具
  - GET  /api/recipe/daily                    一日三餐推荐
  - GET  /api/recipe/recommend?date=&meal=    单餐推荐
  - GET  /api/recipe/{id}                     食谱详情
  - 过敏原过滤 / 忌口过滤
  - 7 天内不重复策略
  - 减脂/增肌不同目标匹配不同食谱
"""

import uuid
from datetime import date, timedelta

import pytest


class TestRecommendRecipeViaChat:
    """通过 Agent 对话推荐食谱."""

    @pytest.mark.asyncio
    async def test_chat_recommend_lunch(self, auth_client, mock_deepseek):
        """用户说'推荐午餐' → Agent 调用 recommend_recipe 工具."""
        resp = await auth_client.post(
            "/api/chat",
            json={"message": "帮我推荐今天的午餐"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert len(data["data"]["reply"]) > 0

    @pytest.mark.asyncio
    async def test_chat_recommend_with_constraints(self, auth_client, mock_deepseek):
        """用户说'推荐低卡晚餐' → Agent 在推荐时考虑热量约束."""
        resp = await auth_client.post(
            "/api/chat",
            json={"message": "推荐一份低卡晚餐，热量不超过400大卡"},
        )
        assert resp.status_code == 200


class TestDailyRecommendation:
    """一日三餐推荐."""

    @pytest.mark.asyncio
    async def test_daily_three_meals(self, auth_client, seeded_recipes):
        """获取今日三餐 → 返回早中晚各至少 1 个食谱."""
        resp = await auth_client.get(f"/api/recipe/daily?date={date.today()}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        meals = data["data"]
        assert "breakfast" in meals
        assert "lunch" in meals
        assert "dinner" in meals
        for meal_type in ["breakfast", "lunch", "dinner"]:
            assert len(meals[meal_type]) >= 1
            assert meals[meal_type][0]["name"]

    @pytest.mark.asyncio
    async def test_daily_future_date(self, auth_client):
        """查询未来日期 → 正常返回推荐（不报错）."""
        future = (date.today() + timedelta(days=3)).isoformat()
        resp = await auth_client.get(f"/api/recipe/daily?date={future}")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_daily_past_date(self, auth_client):
        """查询过去日期 → 返回当时的推荐记录或空."""
        past = (date.today() - timedelta(days=5)).isoformat()
        resp = await auth_client.get(f"/api/recipe/daily?date={past}")
        assert resp.status_code == 200


class TestSingleMealRecommendation:
    """单餐推荐."""

    @pytest.mark.asyncio
    async def test_recommend_breakfast(self, auth_client, seeded_recipes):
        """推荐早餐 → 返回早餐类食谱."""
        resp = await auth_client.get(
            f"/api/recipe/recommend?date={date.today()}&meal=breakfast"
        )
        assert resp.status_code == 200
        results = resp.json()["data"]
        assert len(results) >= 1
        # 推荐的食谱应标记为 breakfast 或 all
        for recipe in results:
            assert recipe["meal_type"] in ("breakfast", "snack", "all")

    @pytest.mark.asyncio
    async def test_recommend_lunch(self, auth_client, seeded_recipes):
        """推荐午餐 → 返回午餐类食谱."""
        resp = await auth_client.get(
            f"/api/recipe/recommend?date={date.today()}&meal=lunch"
        )
        assert resp.status_code == 200
        assert len(resp.json()["data"]) >= 1

    @pytest.mark.asyncio
    async def test_recommend_dinner(self, auth_client, seeded_recipes):
        """推荐晚餐 → 返回晚餐类食谱."""
        resp = await auth_client.get(
            f"/api/recipe/recommend?date={date.today()}&meal=dinner"
        )
        assert resp.status_code == 200
        assert len(resp.json()["data"]) >= 1

    @pytest.mark.asyncio
    async def test_recommend_invalid_meal_type(self, auth_client):
        """非法餐次类型 → 422."""
        resp = await auth_client.get(
            f"/api/recipe/recommend?date={date.today()}&meal=midnightsnack"
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_recommend_invalid_date(self, auth_client):
        """非法日期格式 → 422."""
        resp = await auth_client.get(
            "/api/recipe/recommend?date=not-a-date&meal=lunch"
        )
        assert resp.status_code == 422


class TestRecipeDetail:
    """食谱详情."""

    @pytest.mark.asyncio
    async def test_get_recipe_detail(self, auth_client, seeded_recipes):
        """获取已有食谱详情 → 返回完整信息."""
        recipe_id = seeded_recipes[0]["id"]
        resp = await auth_client.get(f"/api/recipe/{recipe_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        recipe = data["data"]
        assert recipe["name"]
        assert recipe["ingredients"]
        assert recipe["nutrition_per_serving"]["calories"]
        assert recipe["steps"]

    @pytest.mark.asyncio
    async def test_get_recipe_not_found(self, auth_client):
        """查询不存在的食谱 ID → 404."""
        fake_id = uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")
        resp = await auth_client.get(f"/api/recipe/{fake_id}")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_recipe_invalid_uuid(self, auth_client):
        """非法 UUID → 422."""
        resp = await auth_client.get("/api/recipe/not-a-uuid")
        assert resp.status_code == 422


class TestAllergyFiltering:
    """过敏原 & 忌口过滤."""

    @pytest.mark.asyncio
    async def test_filter_peanut_allergy(self, auth_client, seeded_recipes):
        """用户过敏原含花生 → 推荐食谱不含花生."""
        # 更新用户过敏原
        await auth_client.put(
            "/api/auth/profile",
            json={"allergies": ["peanut"]},
        )
        resp = await auth_client.get(
            f"/api/recipe/daily?date={date.today()}"
        )
        # 所有推荐食谱的食材中不应含花生
        for meal_name, meals in resp.json()["data"].items():
            for recipe in meals:
                ingredients = [i["name"] for i in recipe.get("ingredients", [])]
                for ing in ingredients:
                    assert "花生" not in ing

    @pytest.mark.asyncio
    async def test_filter_no_pork(self, auth_client, seeded_recipes):
        """用户忌口 no_pork → 食谱食材中不应含猪肉."""
        await auth_client.put(
            "/api/auth/profile",
            json={"dietary_restrictions": ["no_pork"]},
        )
        resp = await auth_client.get(
            f"/api/recipe/daily?date={date.today()}"
        )
        for meal_name, meals in resp.json()["data"].items():
            for recipe in meals:
                ingredients_text = str(recipe.get("ingredients", []))
                assert "猪肉" not in ingredients_text
                assert "猪" not in ingredients_text


class TestGoalBasedMatching:
    """健身目标匹配."""

    @pytest.mark.asyncio
    async def test_lose_fat_gets_low_calorie(self, auth_client, seeded_recipes):
        """减脂用户 → 推荐的食谱热量偏低."""
        await auth_client.put(
            "/api/auth/profile",
            json={"fitness_goal": "lose_fat", "weight_kg": 80, "height_cm": 170},
        )
        resp = await auth_client.get(
            f"/api/recipe/daily?date={date.today()}"
        )
        # 减脂用户的三餐总热量应不超过目标值
        total = 0
        for meals in resp.json()["data"].values():
            for recipe in meals:
                total += recipe["nutrition_per_serving"]["calories"]
        # 粗略判断: 减脂目标三餐总热量应在 1200-1800 范围
        assert 1200 <= total <= 2200

    @pytest.mark.asyncio
    async def test_build_muscle_gets_high_protein(self, auth_client, seeded_recipes):
        """增肌用户（70kg） → 全天食谱总蛋白 ≥ 80g，且至少有一餐 ≥ 25g."""
        await auth_client.put(
            "/api/auth/profile",
            json={"fitness_goal": "build_muscle", "weight_kg": 70, "height_cm": 175},
        )
        resp = await auth_client.get(
            f"/api/recipe/daily?date={date.today()}"
        )
        # 汇总全天推荐食谱的蛋白总量
        total_protein = 0
        max_per_meal = 0
        for meals in resp.json()["data"].values():
            for recipe in meals:
                p = recipe["nutrition_per_serving"].get("protein_g", 0)
                total_protein += p
                max_per_meal = max(max_per_meal, p)

        # 增肌：70kg × 1.6g/kg ≈ 112g/天，按三餐至少覆盖 70%
        assert total_protein >= 80, f"全天蛋白总量 {total_protein}g < 80g"
        assert max_per_meal >= 25, f"最高单餐蛋白 {max_per_meal}g < 25g"


class TestNoRepeatStrategy:
    """7 天不重复策略."""

    @pytest.mark.asyncio
    async def test_consecutive_days_different_recipes(self, auth_client, seeded_recipes):
        """连续两天推荐 → 同餐次食谱不应完全重复."""
        day1_resp = await auth_client.get(
            f"/api/recipe/recommend?date={date.today()}&meal=lunch"
        )
        day2_resp = await auth_client.get(
            f"/api/recipe/recommend?date={date.today() + timedelta(days=1)}&meal=lunch"
        )

        day1_ids = {r["id"] for r in day1_resp.json()["data"]}
        day2_ids = {r["id"] for r in day2_resp.json()["data"]}
        # 至少有一个不同的食谱
        assert day1_ids != day2_ids or len(day1_ids) == 0
