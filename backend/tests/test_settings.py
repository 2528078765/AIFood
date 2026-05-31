"""测试用例：用户 API Key 配置.

覆盖:
  - GET    /api/settings/apikeys                    查看已配置 Key（脱敏）
  - PUT    /api/settings/apikeys                    保存/更新 Key（加密存储）
  - DELETE /api/settings/apikeys?provider=deepseek   删除 Key
  - POST   /api/settings/test-connection             测试 Key 连接
  - Agent 运行时动态加载用户 Key
  - 未配置 Key → Agent 友好提示引导设置
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestGetAPIKeys:
    """查看 API Key 配置."""

    @pytest.mark.asyncio
    async def test_get_keys_empty(self, auth_client):
        """新用户未配置任何 Key → 返回空配置."""
        resp = await auth_client.get("/api/settings/apikeys")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        keys = data["data"]
        assert keys["deepseek"]["configured"] is False
        assert keys["qwen"]["configured"] is False
        assert keys["tavily"]["configured"] is False

    @pytest.mark.asyncio
    async def test_keys_are_masked(self, auth_client, api_key_payload):
        """已配置 Key → 返回脱敏后的值."""
        await auth_client.put("/api/settings/apikeys", json=api_key_payload)

        resp = await auth_client.get("/api/settings/apikeys")
        keys = resp.json()["data"]

        # deepseek key 应脱敏：显示 sk-te***2345
        masked = keys["deepseek"]["key_preview"]
        assert masked != api_key_payload["deepseek_api_key"]
        assert masked.startswith("sk-te")
        assert "***" in masked
        # 完整 Key 不应出现在响应中
        assert api_key_payload["deepseek_api_key"] not in str(resp.json())


class TestUpdateAPIKeys:
    """更新 API Key."""

    @pytest.mark.asyncio
    async def test_save_keys_success(self, auth_client, api_key_payload):
        """保存三个 Key → 成功."""
        resp = await auth_client.put("/api/settings/apikeys", json=api_key_payload)
        assert resp.status_code == 200
        assert resp.json()["code"] == 0

    @pytest.mark.asyncio
    async def test_save_partial_keys(self, auth_client):
        """只保存 deepseek → qwen 和 tavily 不受影响."""
        await auth_client.put(
            "/api/settings/apikeys",
            json={"deepseek_api_key": "sk-deepseek-only"},
        )
        resp = await auth_client.get("/api/settings/apikeys")
        keys = resp.json()["data"]
        assert keys["deepseek"]["configured"] is True

    @pytest.mark.asyncio
    async def test_update_existing_key(self, auth_client, api_key_payload):
        """覆盖更新已有 Key."""
        await auth_client.put("/api/settings/apikeys", json=api_key_payload)

        new_payload = {
            "deepseek_api_key": "sk-new-deepseek-key-99999",
            "deepseek_base_url": "https://custom.deepseek.com/v1",
        }
        resp = await auth_client.put("/api/settings/apikeys", json=new_payload)
        assert resp.status_code == 200

        # 确认已更新（检查脱敏值变化）
        get_resp = await auth_client.get("/api/settings/apikeys")
        preview = get_resp.json()["data"]["deepseek"]["key_preview"]
        # 脱敏格式：首4位 + *** + 尾4位 → "sk-n***9999"
        assert preview.startswith("sk-n")
        assert preview.endswith("9999")
        assert "*" in preview
        # 完整 Key 不应出现
        assert "new-deepseek-key" not in preview

    @pytest.mark.asyncio
    async def test_save_with_custom_base_url(self, auth_client):
        """自定义 base_url → 保存成功."""
        resp = await auth_client.put(
            "/api/settings/apikeys",
            json={
                "deepseek_api_key": "sk-test",
                "deepseek_base_url": "https://my-proxy.deepseek.com",
            },
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_save_empty_key(self, auth_client):
        """Key 为空字符串 → 视为删除该 Key."""
        # 先配置
        resp = await auth_client.put(
            "/api/settings/apikeys",
            json={"deepseek_api_key": "sk-test-key-to-delete"},
        )
        assert resp.status_code == 200

        # 再清空
        resp = await auth_client.put(
            "/api/settings/apikeys",
            json={"deepseek_api_key": ""},
        )
        assert resp.status_code == 200
        get_resp = await auth_client.get("/api/settings/apikeys")
        assert get_resp.json()["data"]["deepseek"]["configured"] is False


class TestDeleteAPIKeys:
    """删除 API Key."""

    @pytest.mark.asyncio
    async def test_delete_existing_key(self, auth_client, api_key_payload):
        """删除已配置的 Key → 成功."""
        await auth_client.put("/api/settings/apikeys", json=api_key_payload)

        resp = await auth_client.delete(
            "/api/settings/apikeys?provider=deepseek"
        )
        assert resp.status_code == 200

        # 确认已删除
        get_resp = await auth_client.get("/api/settings/apikeys")
        assert get_resp.json()["data"]["deepseek"]["configured"] is False

    @pytest.mark.asyncio
    async def test_delete_nonexistent_key(self, auth_client):
        """删除未配置的 Key → 成功（幂等）."""
        resp = await auth_client.delete(
            "/api/settings/apikeys?provider=tavily"
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_delete_invalid_provider(self, auth_client):
        """非法 provider → 422."""
        resp = await auth_client.delete(
            "/api/settings/apikeys?provider=openai"
        )
        assert resp.status_code == 422


class TestTestConnection:
    """测试 API Key 连接."""

    @pytest.mark.asyncio
    async def test_test_connection_success(self, auth_client, api_key_payload):
        """有效 Key → 测试连接成功."""
        await auth_client.put("/api/settings/apikeys", json=api_key_payload)

        with patch("langchain_deepseek.ChatDeepSeek") as mock:
            instance = MagicMock()
            instance.ainvoke = AsyncMock(
                return_value=MagicMock(content="ok")
            )
            mock.return_value = instance

            resp = await auth_client.post(
                "/api/settings/test-connection?provider=deepseek"
            )
            assert resp.status_code == 200
            assert resp.json()["data"]["connected"] is True

    @pytest.mark.asyncio
    async def test_test_connection_no_key(self, auth_client):
        """未配置 Key → 测试连接失败."""
        resp = await auth_client.post(
            "/api/settings/test-connection?provider=deepseek"
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["connected"] is False
        assert "未配置" in resp.json()["data"]["error"]

    @pytest.mark.asyncio
    async def test_test_connection_wrong_key(self, auth_client):
        """错误的 Key → 测试连接失败."""
        await auth_client.put(
            "/api/settings/apikeys",
            json={"deepseek_api_key": "sk-invalid-key"},
        )

        with patch("langchain_deepseek.ChatDeepSeek") as mock:
            instance = MagicMock()
            instance.ainvoke = AsyncMock(
                side_effect=Exception("401 Unauthorized")
            )
            mock.return_value = instance

            resp = await auth_client.post(
                "/api/settings/test-connection?provider=deepseek"
            )
            assert resp.status_code == 200
            assert resp.json()["data"]["connected"] is False

    @pytest.mark.asyncio
    async def test_test_connection_qwen(self, auth_client, api_key_payload):
        """测试 Qwen 连接."""
        await auth_client.put("/api/settings/apikeys", json=api_key_payload)

        with patch("langchain_openai.ChatOpenAI") as mock:
            instance = MagicMock()
            instance.ainvoke = AsyncMock(return_value=MagicMock(content="ok"))
            mock.return_value = instance

            resp = await auth_client.post(
                "/api/settings/test-connection?provider=qwen"
            )
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_test_connection_invalid_provider(self, auth_client):
        """非法 provider → 422."""
        resp = await auth_client.post(
            "/api/settings/test-connection?provider=openai"
        )
        assert resp.status_code == 422


class TestAgentWithoutKey:
    """用户未配置 Key 时 Agent 行为."""

    @pytest.mark.asyncio
    async def test_agent_redirects_to_settings_when_no_key(self, auth_client):
        """未配置 Key → Agent 回复引导用户去设置页配置."""
        # 确保 Key 已清空
        await auth_client.delete("/api/settings/apikeys?provider=deepseek")

        resp = await auth_client.post(
            "/api/chat",
            json={"message": "帮我识别这碗面"},
        )
        assert resp.status_code == 200
        reply = resp.json()["data"]["reply"]
        # 引导语应提到配置
        assert any(kw in reply for kw in ["配置", "设置", "API", "Key", "密钥"])
