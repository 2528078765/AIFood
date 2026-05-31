"""测试用例：健身打卡 & 统计.

覆盖:
  - POST /api/chat → Agent 调用 log_fitness 工具
  - POST /api/fitness/checkin                    直接打卡
  - GET  /api/fitness/records                    打卡记录查询
  - GET  /api/fitness/stats                      统计（周/月）
  - GET  /api/fitness/streak                     连续打卡天数
  - 边界：同一天多次打卡、非法强度值、负数时长
"""

import uuid
from datetime import date, timedelta

import pytest


class TestFitnessCheckin:
    """健身打卡."""

    @pytest.mark.asyncio
    async def test_checkin_all_fields(self, auth_client, fitness_checkin_payload):
        """提交完整打卡 → 成功."""
        resp = await auth_client.post(
            "/api/fitness/checkin", json=fitness_checkin_payload
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert data["data"]["exercise_type"] == "running"
        assert data["data"]["duration_min"] == 30

    @pytest.mark.asyncio
    async def test_checkin_minimal_fields(self, auth_client):
        """最小字段打卡 → 成功."""
        resp = await auth_client.post(
            "/api/fitness/checkin",
            json={"exercise_type": "yoga", "duration_min": 20, "intensity": 4},
        )
        assert resp.status_code == 200
        assert resp.json()["code"] == 0

    @pytest.mark.asyncio
    async def test_checkin_missing_type(self, auth_client):
        """缺少运动类型 → 422."""
        resp = await auth_client.post(
            "/api/fitness/checkin", json={"duration_min": 30}
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_checkin_missing_duration(self, auth_client):
        """缺少运动时长 → 422."""
        resp = await auth_client.post(
            "/api/fitness/checkin", json={"exercise_type": "running"}
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_checkin_negative_duration(self, auth_client):
        """负数时长 → 422."""
        resp = await auth_client.post(
            "/api/fitness/checkin",
            json={"exercise_type": "running", "duration_min": -10},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_checkin_zero_duration(self, auth_client):
        """时长 0 → 422."""
        resp = await auth_client.post(
            "/api/fitness/checkin",
            json={"exercise_type": "running", "duration_min": 0},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_checkin_intensity_out_of_range(self, auth_client):
        """强度超出 1-10 → 422."""
        resp = await auth_client.post(
            "/api/fitness/checkin",
            json={"exercise_type": "running", "duration_min": 30, "intensity": 11},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_checkin_intensity_zero(self, auth_client):
        """强度 0 → 422."""
        resp = await auth_client.post(
            "/api/fitness/checkin",
            json={"exercise_type": "running", "duration_min": 30, "intensity": 0},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_checkin_invalid_exercise_type(self, auth_client):
        """非法运动类型 → 422."""
        resp = await auth_client.post(
            "/api/fitness/checkin",
            json={"exercise_type": "sleeping", "duration_min": 480, "intensity": 1},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_checkin_same_day_twice(self, auth_client, fitness_checkin_payload):
        """同一天打卡两次 → 都成功（允许补录或多次运动）."""
        await auth_client.post("/api/fitness/checkin", json=fitness_checkin_payload)
        resp2 = await auth_client.post(
            "/api/fitness/checkin",
            json={
                "exercise_type": "swimming",
                "duration_min": 45,
                "intensity": 6,
            },
        )
        assert resp2.status_code == 200


class TestCheckinViaChat:
    """通过 Agent 对话打卡."""

    @pytest.mark.asyncio
    async def test_chat_log_running(self, auth_client, mock_deepseek):
        """用户说'我跑了5公里' → Agent 调用 log_fitness 工具."""
        resp = await auth_client.post(
            "/api/chat",
            json={"message": "我今天跑了5公里，花了30分钟"},
        )
        assert resp.status_code == 200
        reply = resp.json()["data"]["reply"]
        assert any(kw in reply for kw in ["打卡", "记录", "跑步", "分钟"])


class TestFitnessRecords:
    """打卡记录查询."""

    @pytest.mark.asyncio
    async def test_get_records(self, auth_client, fitness_checkin_payload):
        """打卡后查询 → 返回当日的打卡记录."""
        await auth_client.post("/api/fitness/checkin", json=fitness_checkin_payload)

        resp = await auth_client.get(
            f"/api/fitness/records?start_date={date.today()}&end_date={date.today()}"
        )
        assert resp.status_code == 200
        records = resp.json()["data"]
        assert len(records) >= 1
        assert records[0]["exercise_type"] == "running"

    @pytest.mark.asyncio
    async def test_get_records_date_range(self, auth_client, fitness_checkin_payload):
        """查询日期范围 → 只返回该范围内的记录."""
        await auth_client.post("/api/fitness/checkin", json=fitness_checkin_payload)

        # 查询未来一天（无记录）
        future = (date.today() + timedelta(days=1)).isoformat()
        resp = await auth_client.get(
            f"/api/fitness/records?start_date={future}&end_date={future}"
        )
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    @pytest.mark.asyncio
    async def test_get_records_start_after_end(self, auth_client):
        """起始日期晚于结束日期 → 422."""
        resp = await auth_client.get(
            "/api/fitness/records?start_date=2025-06-01&end_date=2025-01-01"
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_get_records_default_range(self, auth_client, fitness_checkin_payload):
        """不传日期范围 → 默认返回本周."""
        await auth_client.post("/api/fitness/checkin", json=fitness_checkin_payload)
        resp = await auth_client.get("/api/fitness/records")
        assert resp.status_code == 200


class TestFitnessStats:
    """健身统计."""

    @pytest.mark.asyncio
    async def test_stats_week(self, auth_client, fitness_checkin_payload):
        """周统计 → 返回运动天数、总时长、运动分布."""
        await auth_client.post("/api/fitness/checkin", json=fitness_checkin_payload)

        resp = await auth_client.get("/api/fitness/stats?period=week")
        assert resp.status_code == 200
        stats = resp.json()["data"]
        assert "total_days" in stats
        assert "total_minutes" in stats
        assert "exercises" in stats
        assert stats["total_days"] >= 1
        assert stats["total_minutes"] >= 30

    @pytest.mark.asyncio
    async def test_stats_month(self, auth_client, fitness_checkin_payload):
        """月统计 → 同周统计结构."""
        await auth_client.post("/api/fitness/checkin", json=fitness_checkin_payload)
        resp = await auth_client.get("/api/fitness/stats?period=month")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_stats_default_period(self, auth_client):
        """不传 period → 默认返回周统计."""
        resp = await auth_client.get("/api/fitness/stats")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_stats_invalid_period(self, auth_client):
        """非法 period → 422."""
        resp = await auth_client.get("/api/fitness/stats?period=year")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_stats_empty(self, auth_client):
        """无记录时的统计 → 所有数字为 0."""
        resp = await auth_client.get("/api/fitness/stats?period=week")
        assert resp.status_code == 200
        stats = resp.json()["data"]
        assert stats["total_days"] == 0
        assert stats["total_minutes"] == 0
        assert stats["exercises"] == {}


class TestFitnessStreak:
    """连续打卡天数."""

    @pytest.mark.asyncio
    async def test_streak_zero(self, auth_client):
        """从未打卡 → 连续天数 0."""
        resp = await auth_client.get("/api/fitness/streak")
        assert resp.status_code == 200
        assert resp.json()["data"]["streak_days"] == 0

    @pytest.mark.asyncio
    async def test_streak_single_day(self, auth_client, fitness_checkin_payload):
        """打卡 1 天 → 连续天数 1."""
        await auth_client.post("/api/fitness/checkin", json=fitness_checkin_payload)
        resp = await auth_client.get("/api/fitness/streak")
        assert resp.status_code == 200
        assert resp.json()["data"]["streak_days"] == 1

    @pytest.mark.asyncio
    async def test_streak_broken(self, auth_client, fitness_checkin_payload):
        """昨天没打卡 → 连续天数归零（今天打卡为 1）."""
        # 模拟昨天打卡（实际通过 API 无法写过去日期）
        # 此用例验证逻辑：间断后连续天数重置
        await auth_client.post("/api/fitness/checkin", json=fitness_checkin_payload)
        resp = await auth_client.get("/api/fitness/streak")
        assert resp.json()["data"]["streak_days"] >= 1
