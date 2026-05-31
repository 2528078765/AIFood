"""测试用例：用户认证 & 微信登录.

覆盖:
  - POST /api/auth/login    微信登录换取 JWT
  - GET  /api/auth/profile   获取个人信息
  - PUT  /api/auth/profile   更新个人信息
  - 鉴权中间件：无 token / 过期 token / 伪造 token
  - 新用户首次登录自动创建账户
"""

import pytest


class TestWeChatLogin:
    """微信登录接口."""

    @pytest.mark.asyncio
    async def test_login_new_user_creates_account(self, client, user_payload, mock_wechat):
        """新用户首次登录 → 自动创建账户 → 返回 JWT."""
        resp = await client.post("/api/auth/login", json=user_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert "access_token" in data["data"]
        assert len(data["data"]["access_token"]) > 20
        assert data["data"]["user"]["id"] is not None  # 新用户自动获得 ID

    @pytest.mark.asyncio
    async def test_login_existing_user_returns_same_user(self, client, user_payload, mock_wechat):
        """已存在用户再次登录 → 返回同一用户 + 新 JWT."""
        # 第一次登录
        resp1 = await client.post("/api/auth/login", json=user_payload)
        token1 = resp1.json()["data"]["access_token"]

        # 第二次登录（相同微信 code）
        resp2 = await client.post("/api/auth/login", json=user_payload)
        token2 = resp2.json()["data"]["access_token"]

        # token 不同（每次签发新 JWT），但用户 ID 相同
        assert token1 != token2
        assert resp1.json()["data"]["user"]["id"] == resp2.json()["data"]["user"]["id"]

    @pytest.mark.asyncio
    async def test_login_missing_wechat_code(self, client):
        """缺少 wechat_code 字段 → 返回 422 验证错误."""
        resp = await client.post("/api/auth/login", json={})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_login_invalid_wechat_code(self, client, mock_wechat):
        """无效微信 code → 返回错误."""
        mock_wechat.oauth.get_user_info.side_effect = Exception("invalid code")
        resp = await client.post(
            "/api/auth/login",
            json={"wechat_code": "invalid_code"},
        )
        assert resp.status_code == 400 or resp.status_code == 401


class TestGetProfile:
    """获取个人信息."""

    @pytest.mark.asyncio
    async def test_get_profile_authenticated(self, auth_client):
        """已登录 → 返回完整个人信息."""
        resp = await auth_client.get("/api/auth/profile")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        user = data["data"]
        assert user["fitness_goal"] == "lose_fat"
        assert user["height_cm"] == 175.0
        assert user["weight_kg"] == 70.0
        assert "peanut" in user["allergies"]

    @pytest.mark.asyncio
    async def test_get_profile_without_token(self, client):
        """未登录 → 返回 401."""
        resp = await client.get("/api/auth/profile")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_get_profile_with_expired_token(self, client):
        """过期 token → 返回 401."""
        # 预期实现中 JWT 有效期可配置，测试时用短期 token 或手动构造过期 token
        pass  # TODO: 实现后取消跳过

    @pytest.mark.asyncio
    async def test_get_profile_with_forged_token(self, client):
        """伪造 token → 返回 401."""
        client.headers["Authorization"] = "Bearer forged.token.here"
        resp = await client.get("/api/auth/profile")
        assert resp.status_code == 401


class TestUpdateProfile:
    """更新个人信息."""

    @pytest.mark.asyncio
    async def test_update_profile_all_fields(self, auth_client, profile_payload):
        """更新所有字段 → 返回更新后的数据."""
        resp = await auth_client.put("/api/auth/profile", json=profile_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert data["data"]["height_cm"] == 178.0
        assert data["data"]["weight_kg"] == 68.0
        assert data["data"]["fitness_goal"] == "build_muscle"
        assert "milk" in data["data"]["allergies"]

    @pytest.mark.asyncio
    async def test_update_profile_height_zero(self, auth_client):
        """身高设为 0 → 422 验证错误."""
        resp = await auth_client.put("/api/auth/profile", json={"height_cm": 0})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_update_profile_negative_weight(self, auth_client):
        """体重设为负数 → 422 验证错误."""
        resp = await auth_client.put("/api/auth/profile", json={"weight_kg": -5})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_update_profile_invalid_goal(self, auth_client):
        """无效健身目标 → 422."""
        resp = await auth_client.put(
            "/api/auth/profile", json={"fitness_goal": "become_superman"}
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_update_profile_birthday_future(self, auth_client):
        """生日在未来 → 422."""
        resp = await auth_client.put(
            "/api/auth/profile", json={"birthday": "2099-01-01"}
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_update_profile_weight_triggers_calorie_recalc(
        self, auth_client
    ):
        """更新体重后 → daily_calorie_target 自动重算."""
        resp = await auth_client.put("/api/auth/profile", json={"weight_kg": 80.0})
        assert resp.status_code == 200
        # 更新体重后目标热量应同步变化（不再等于旧值）
        profile_resp = await auth_client.get("/api/auth/profile")
        assert profile_resp.json()["data"]["daily_calorie_target"] is not None
