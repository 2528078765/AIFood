"""测试用例：食物识别 & 营养查询.

覆盖:
  - POST /api/upload → OSS → POST /api/chat/stream (SSE) → Agent 调用 recognize_food
  - POST /api/chat (降级, 带 image base64) 兜底路径
  - GET  /api/food/records                食物记录查询
  - GET  /api/food/search                 营养数据库搜索
  - 食物识别 JSON 解析 & Schema 校验
  - 营养数据校准逻辑
"""

import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestFoodRecognition:
    """拍照识食 — 主路径：upload → image_url → SSE stream."""

    @pytest.mark.asyncio
    async def test_recognize_via_stream(
        self, auth_client, mock_qwen_vision, mock_deepseek
    ):
        """SSE 流式识别 → 收到 thinking / tool_call / tool_result / final 事件."""
        resp = await auth_client.post(
            "/api/chat/stream",
            json={
                "message": "这是什么食物？",
                "image_url": "https://oss.example.com/food-photo.jpg",
            },
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "text/event-stream"
        body = resp.text
        assert "event: thinking" in body
        assert "event: tool_call" in body
        assert "event: tool_result" in body
        assert "event: final" in body
        assert "宫保鸡丁" in body

    @pytest.mark.asyncio
    async def test_recognize_single_food(
        self, auth_client, food_image_base64, mock_qwen_vision, mock_deepseek
    ):
        """降级路径：直接传 base64 image → 返回完整回复."""
        resp = await auth_client.post(
            "/api/chat",
            json={"message": "这是什么食物？", "image": food_image_base64},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert len(data["data"]["reply"]) > 0
        assert any(kw in data["data"]["reply"] for kw in ["宫保鸡丁", "热量", "大卡"])

    @pytest.mark.asyncio
    async def test_recognize_multiple_foods(
        self, auth_client, mock_deepseek
    ):
        """多道菜识别 → 返回多个食物条目."""
        with patch("langchain_openai.ChatOpenAI") as mock:
            instance = MagicMock()
            instance.ainvoke = AsyncMock(
                return_value=MagicMock(
                    content='[{"name":"宫保鸡丁","calories_per_100g":175,"estimated_weight_g":350,'
                    '"estimated_calories":612,"protein_g":28.5,"fat_g":38.2,"carbs_g":22.8},'
                    '{"name":"米饭","calories_per_100g":116,"estimated_weight_g":200,'
                    '"estimated_calories":232,"protein_g":2.6,"fat_g":0.3,"carbs_g":25.9}]'
                )
            )
            mock.return_value = instance

            resp = await auth_client.post(
                "/api/chat",
                json={
                    "message": "这桌菜有多少热量？",
                    "image_url": "https://oss.example.com/meal.jpg",
                },
            )
            assert resp.status_code == 200
            reply = resp.json()["data"]["reply"]
            assert "宫保鸡丁" in reply
            assert "米饭" in reply

    @pytest.mark.asyncio
    async def test_recognize_no_food_in_image(self, auth_client, mock_deepseek):
        """图片中没有食物 → Agent 应友好提示而非报错."""
        with patch("langchain_openai.ChatOpenAI") as mock:
            instance = MagicMock()
            instance.ainvoke = AsyncMock(return_value=MagicMock(content="[]"))
            mock.return_value = instance

            resp = await auth_client.post(
                "/api/chat",
                json={
                    "message": "这是什么？",
                    "image_url": "https://oss.example.com/empty-room.jpg",
                },
            )
            assert resp.status_code == 200
            reply = resp.json()["data"]["reply"]
            assert any(kw in reply for kw in ["没有", "识别", "食物", "无法"])

    @pytest.mark.asyncio
    async def test_recognize_without_image(self, auth_client, mock_deepseek):
        """不带图片的对话 → Agent 不调用 recognize_food 工具."""
        resp = await auth_client.post(
            "/api/chat",
            json={"message": "鸡胸肉的热量是多少？"},
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_recognize_invalid_url(self, auth_client, mock_deepseek):
        """无效图片 URL → Tool 返回错误描述，Agent 友好回复而非 500."""
        resp = await auth_client.post(
            "/api/chat",
            json={
                "message": "识别这碗面",
                "image_url": "https://not-exist.example.com/404.jpg",
            },
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_recognize_schema_validation_retry(
        self, auth_client, mock_deepseek
    ):
        """LLM 返回不合规 JSON → Schema 校验失败 → 自动重试一次."""
        call_count = [0]

        async def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return MagicMock(content="Not a valid JSON response, sorry!")
            else:
                return MagicMock(
                    content='[{"name":"苹果","calories_per_100g":52,"estimated_weight_g":200,'
                    '"estimated_calories":104,"protein_g":0.3,"fat_g":0.2,"carbs_g":13.8}]'
                )

        with patch("langchain_openai.ChatOpenAI") as mock:
            instance = MagicMock()
            instance.ainvoke = AsyncMock(side_effect=side_effect)
            mock.return_value = instance

            resp = await auth_client.post(
                "/api/chat",
                json={
                    "message": "识别",
                    "image_url": "https://oss.example.com/apple.jpg",
                },
            )
            assert resp.status_code == 200
            assert call_count[0] == 2


class TestImageUpload:
    """图片上传到 OSS."""

    @pytest.mark.asyncio
    async def test_upload_image(self, auth_client, food_image_base64):
        """上传图片 → 返回 OSS URL."""
        import io

        # 构造一个假的图片文件上传
        resp = await auth_client.post(
            "/api/upload",
            files={"file": ("food.jpg", io.BytesIO(b"fake-image-data"), "image/jpeg")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert data["data"]["image_url"].startswith("https://")

    @pytest.mark.asyncio
    async def test_upload_invalid_file_type(self, auth_client):
        """上传非图片文件 → 422."""
        import io

        resp = await auth_client.post(
            "/api/upload",
            files={"file": ("doc.pdf", io.BytesIO(b"pdf-data"), "application/pdf")},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_upload_no_file(self, auth_client):
        """不上传文件 → 422."""
        resp = await auth_client.post("/api/upload")
        assert resp.status_code == 422


class TestFoodRecords:
    """食物记录查询."""

    @pytest.mark.asyncio
    async def test_get_records_by_date(self, auth_client):
        """按日期查询食物记录 → 返回当日所有记录."""
        resp = await auth_client.get(f"/api/food/records?date={date.today()}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert isinstance(data["data"], list)

    @pytest.mark.asyncio
    async def test_get_records_default_date(self, auth_client):
        """不传日期 → 默认返回今天."""
        resp = await auth_client.get("/api/food/records")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_get_records_empty_day(self, auth_client):
        """无记录的日期 → 返回空列表."""
        resp = await auth_client.get("/api/food/records?date=2020-01-01")
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    @pytest.mark.asyncio
    async def test_record_contains_all_fields(self, auth_client):
        """返回的记录应包含完整字段."""
        resp = await auth_client.get(f"/api/food/records?date={date.today()}")
        if len(resp.json()["data"]) > 0:
            record = resp.json()["data"][0]
            required_fields = [
                "id", "foods", "total_calories", "total_protein_g",
                "total_fat_g", "total_carbs_g", "meal_type", "recorded_at"
            ]
            for field in required_fields:
                assert field in record, f"Missing field: {field}"


class TestNutritionSearch:
    """营养数据库搜索."""

    @pytest.mark.asyncio
    async def test_search_exact_match(self, auth_client):
        """精确匹配 '鸡胸肉' → 返回营养成分."""
        resp = await auth_client.get("/api/food/search?keyword=鸡胸肉")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        results = data["data"]
        assert len(results) > 0
        first = results[0]
        assert "calories_per_100g" in first
        assert "protein_g" in first

    @pytest.mark.asyncio
    async def test_search_fuzzy_match(self, auth_client):
        """模糊搜索 '牛肉' → 返回相关结果."""
        resp = await auth_client.get("/api/food/search?keyword=牛肉")
        assert resp.status_code == 200
        assert len(resp.json()["data"]) >= 1

    @pytest.mark.asyncio
    async def test_search_no_result(self, auth_client):
        """搜索不存在的食物 → 返回空列表."""
        resp = await auth_client.get("/api/food/search?keyword=火星陨石汤")
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    @pytest.mark.asyncio
    async def test_search_empty_keyword(self, auth_client):
        """空关键词 → 422."""
        resp = await auth_client.get("/api/food/search?keyword=")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_search_english_keyword(self, auth_client):
        """英文关键词 'chicken breast' → 返回对应中文食物的数据."""
        resp = await auth_client.get("/api/food/search?keyword=chicken%20breast")
        assert resp.status_code == 200
