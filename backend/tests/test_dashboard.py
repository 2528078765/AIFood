"""测试用例：首页仪表盘.

覆盖:
  - GET  /api/dashboard                    聚合数据查询
  - POST /api/chat → Agent 调用 get_dashboard 工具
  - 热量摄入 vs 目标对比
  - 今日健身状态
  - 连续打卡天数
"""

from datetime import date

import pytest


class TestDashboardAPI:
    """仪表盘 API."""

    @pytest.mark.asyncio
    async def test_dashboard_structure(self, auth_client):
        """返回完整仪表盘结构."""
        resp = await auth_client.get("/api/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        dashboard = data["data"]
        assert "date" in dashboard
        assert "calories" in dashboard
        assert "meals" in dashboard
        assert "fitness" in dashboard

    @pytest.mark.asyncio
    async def test_dashboard_calories_structure(self, auth_client):
        """热量字段结构：consumed / target / percentage."""
        resp = await auth_client.get("/api/dashboard")
        dashboard = resp.json()["data"]
        cal = dashboard["calories"]
        assert "consumed" in cal
        assert "target" in cal
        assert "percentage" in cal
        assert isinstance(cal["consumed"], (int, float))
        assert isinstance(cal["target"], (int, float))

    @pytest.mark.asyncio
    async def test_dashboard_meals_structure(self, auth_client):
        """三餐字段结构：breakfast / lunch / dinner."""
        resp = await auth_client.get("/api/dashboard")
        meals = resp.json()["data"]["meals"]
        for meal_key in ["breakfast", "lunch", "dinner"]:
            assert meal_key in meals

    @pytest.mark.asyncio
    async def test_dashboard_fitness_structure(self, auth_client):
        """健身字段结构：checked_in_today / streak_days / week_stats."""
        resp = await auth_client.get("/api/dashboard")
        fitness = resp.json()["data"]["fitness"]
        assert "checked_in_today" in fitness
        assert "streak_days" in fitness
        assert "week_stats" in fitness

    @pytest.mark.asyncio
    async def test_dashboard_no_data(self, auth_client):
        """新用户无任何数据 → 数字为 0/default."""
        resp = await auth_client.get("/api/dashboard")
        dashboard = resp.json()["data"]
        assert dashboard["calories"]["consumed"] == 0
        assert dashboard["fitness"]["checked_in_today"] is False
        assert dashboard["fitness"]["streak_days"] == 0

    @pytest.mark.asyncio
    async def test_dashboard_after_checkin(self, auth_client, fitness_checkin_payload):
        """打卡后 → checked_in_today 为 True."""
        await auth_client.post("/api/fitness/checkin", json=fitness_checkin_payload)
        resp = await auth_client.get("/api/dashboard")
        dashboard = resp.json()["data"]
        assert dashboard["fitness"]["checked_in_today"] is True

    @pytest.mark.asyncio
    async def test_dashboard_calorie_percentage_range(self, auth_client):
        """热量百分比应在 0-100+ 范围（可能超过 100%）."""
        resp = await auth_client.get("/api/dashboard")
        pct = resp.json()["data"]["calories"]["percentage"]
        assert pct >= 0

    @pytest.mark.asyncio
    async def test_dashboard_date_is_today(self, auth_client):
        """返回的日期应为今天."""
        resp = await auth_client.get("/api/dashboard")
        assert resp.json()["data"]["date"] == str(date.today())


class TestDashboardViaChat:
    """通过 Agent 对话查看仪表盘."""

    @pytest.mark.asyncio
    async def test_chat_ask_dashboard(self, auth_client, mock_deepseek):
        """用户问'今天进展' → Agent 返回仪表盘摘要."""
        resp = await auth_client.post(
            "/api/chat",
            json={"message": "我今天进展怎么样？"},
        )
        assert resp.status_code == 200
        reply = resp.json()["data"]["reply"]
        assert len(reply) > 0

    @pytest.mark.asyncio
    async def test_chat_ask_streak(self, auth_client, mock_deepseek):
        """用户问'连续打卡' → Agent 返回连续天数."""
        resp = await auth_client.post(
            "/api/chat",
            json={"message": "我连续打卡多少天了？"},
        )
        assert resp.status_code == 200
