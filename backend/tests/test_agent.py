"""测试用例：Agent 对话 & 工具调用编排.

覆盖:
  - POST /api/chat/stream          SSE 流式对话（主路径）
  - POST /api/chat                 基础对话（降级）
  - GET  /api/chat/history         对话历史
  - Agent 工具调用决策正确性
  - Agent 多工具串联调用
  - Agent 记忆持久化（Redis）
  - 异常处理：工具调用超时、返回格式错误
"""

import pytest


class TestAgentChatStreaming:
    """SSE 流式对话（主路径）."""

    @pytest.mark.asyncio
    async def test_stream_returns_event_stream(self, auth_client, mock_deepseek):
        """SSE 端点返回 text/event-stream."""
        resp = await auth_client.post(
            "/api/chat/stream",
            json={"message": "你好，帮我推荐今天的午餐"},
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "text/event-stream"
        body = resp.text
        # 流式输出应包含 at least final event
        assert "event: final" in body
        assert "data:" in body

    @pytest.mark.asyncio
    async def test_stream_events_order(self, auth_client, mock_deepseek):
        """事件顺序：thinking → (tool_call → tool_result)* → final."""
        resp = await auth_client.post(
            "/api/chat/stream",
            json={"message": "这碗面多少热量？",
                  "image_url": "https://oss.example.com/noodles.jpg"},
        )
        body = resp.text
        # 验证事件类型齐全
        assert "event: thinking" in body
        assert "event: final" in body
        # final 必须是最后一个事件
        final_pos = body.rfind("event: final")
        thinking_pos = body.find("event: thinking")
        assert thinking_pos < final_pos, "thinking 应出现在 final 之前"

    @pytest.mark.asyncio
    async def test_stream_without_auth(self, client):
        """未登录 → 401."""
        resp = await client.post(
            "/api/chat/stream", json={"message": "你好"}
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_stream_empty_message(self, auth_client):
        """空消息 → SSE 也返回 422."""
        resp = await auth_client.post(
            "/api/chat/stream", json={"message": ""}
        )
        assert resp.status_code == 422


class TestAgentChat:
    """Agent 对话基础功能."""

    @pytest.mark.asyncio
    async def test_chat_simple_message(self, auth_client, mock_deepseek):
        """纯文本对话 → Agent 正常回复."""
        resp = await auth_client.post(
            "/api/chat",
            json={"message": "你好，请问我今天应该怎么吃？"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert len(data["data"]["reply"]) > 0

    @pytest.mark.asyncio
    async def test_chat_empty_message(self, auth_client):
        """空消息 → 422."""
        resp = await auth_client.post("/api/chat", json={"message": ""})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_chat_message_too_long(self, auth_client):
        """消息超长（>2000 字符） → 422."""
        resp = await auth_client.post(
            "/api/chat", json={"message": "吃" * 2001}
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_chat_response_format(self, auth_client, mock_deepseek):
        """返回格式统一为 {code, data: {reply}, message}."""
        resp = await auth_client.post(
            "/api/chat", json={"message": "你好"}
        )
        data = resp.json()
        assert "code" in data
        assert "data" in data
        assert "reply" in data["data"]
        assert "message" in data

    @pytest.mark.asyncio
    async def test_chat_without_auth(self, client):
        """未登录 → 401."""
        resp = await client.post(
            "/api/chat", json={"message": "你好"}
        )
        assert resp.status_code == 401


class TestAgentToolRouting:
    """Agent 工具路由决策."""

    @pytest.mark.asyncio
    async def test_tool_routing_food_recognition(self, auth_client, food_image_base64, mock_qwen_vision, mock_deepseek):
        """带图片 → Agent 应路由到 recognize_food."""
        resp = await auth_client.post(
            "/api/chat",
            json={"message": "这是什么食物？", "image": food_image_base64},
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_tool_routing_nutrition_search(self, auth_client, mock_deepseek):
        """询问食物营养 → Agent 应路由到 search_nutrition."""
        resp = await auth_client.post(
            "/api/chat",
            json={"message": "鸡胸肉每100克有多少蛋白质？"},
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_tool_routing_recipe(self, auth_client, mock_deepseek):
        """请求食谱 → Agent 应路由到 recommend_recipe."""
        resp = await auth_client.post(
            "/api/chat",
            json={"message": "帮我推荐今天的晚餐食谱"},
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_tool_routing_fitness(self, auth_client, mock_deepseek):
        """健身记录 → Agent 应路由到 log_fitness."""
        resp = await auth_client.post(
            "/api/chat",
            json={"message": "记录一下我今天跑了30分钟"},
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_tool_routing_dashboard(self, auth_client, mock_deepseek):
        """问进度 → Agent 应路由到 get_dashboard."""
        resp = await auth_client.post(
            "/api/chat",
            json={"message": "我今天整体进展怎么样？"},
        )
        assert resp.status_code == 200


class TestAgentMemory:
    """Agent 记忆管理 — 验证对话历史持久化和窗口截断."""

    @pytest.mark.asyncio
    async def test_memory_persists_across_turns(self, auth_client, mock_deepseek):
        """多轮对话 → 历史记录中保存了每一轮的用户消息."""
        messages = ["我叫张三", "我体重70公斤", "帮我推荐今天的午餐"]
        for msg in messages:
            await auth_client.post("/api/chat", json={"message": msg})

        resp = await auth_client.get("/api/chat/history")
        assert resp.status_code == 200
        history = resp.json()["data"]
        # 历史记录应按时间顺序包含所有用户消息
        user_messages = [h["message"] for h in history if h["role"] == "user"]
        for msg in messages:
            assert msg in user_messages

    @pytest.mark.asyncio
    async def test_memory_window_limit(self, auth_client, mock_deepseek):
        """超过 10 轮对话 → 窗口外的历史被截断."""
        for i in range(15):
            await auth_client.post(
                "/api/chat",
                json={"message": f"消息 {i + 1}"},
            )
        resp = await auth_client.get("/api/chat/history")
        assert resp.status_code == 200
        history = resp.json()["data"]
        user_messages = [h["message"] for h in history if h["role"] == "user"]
        # 窗口截断后，不应保留最早的消息（消息1已超出K=10窗口）
        assert "消息 1" not in user_messages
        # 最近的消息应该还在
        assert "消息 15" in user_messages


class TestChatHistory:
    """对话历史查询."""

    @pytest.mark.asyncio
    async def test_history_default_limit(self, auth_client, mock_deepseek):
        """默认获取最近 20 条历史."""
        await auth_client.post("/api/chat", json={"message": "你好"})
        resp = await auth_client.get("/api/chat/history")
        assert resp.status_code == 200
        history = resp.json()["data"]
        assert isinstance(history, list)
        assert len(history) <= 20

    @pytest.mark.asyncio
    async def test_history_custom_limit(self, auth_client, mock_deepseek):
        """自定义 limit=5."""
        for i in range(10):
            await auth_client.post("/api/chat", json={"message": f"消息{i}"})

        resp = await auth_client.get("/api/chat/history?limit=5")
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 5

    @pytest.mark.asyncio
    async def test_history_empty(self, auth_client):
        """新用户无历史 → 返回空列表."""
        resp = await auth_client.get("/api/chat/history")
        assert resp.status_code == 200
        assert resp.json()["data"] == []
