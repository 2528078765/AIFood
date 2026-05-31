"""共享 Fixtures —— SQLite 内存数据库 + Mock LLM."""

import uuid
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# ============================================================
# SQLite 内存测试数据库
# ============================================================

TEST_DATABASE_URL = "sqlite+aiosqlite:///file:testdb?mode=memory&cache=shared&uri=true"


@pytest_asyncio.fixture
async def test_engine():
    """每个测试函数独立的内存引擎（避免 SQLite 共享内存并发问题）."""
    from app.models.base import Base

    engine = create_async_engine("sqlite+aiosqlite://", echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine):
    """每个测试独立的 DB session（自动回滚）."""
    test_session_factory = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_db():
        async with test_session_factory() as session:
            try:
                yield session
            finally:
                await session.close()

    from app.database import get_db
    from app.main import app

    app.dependency_overrides[get_db] = override_get_db

    async with test_session_factory() as session:
        yield session
        await session.rollback()


# ============================================================
# 常量 & 测试数据
# ============================================================

TEST_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
TEST_OPENID = "test_openid_abc123"


@pytest.fixture
def user_payload():
    return {
        "wechat_code": "test_wechat_code_xxx",
        "nickname": "测试用户",
        "gender": "male",
        "birthday": "1995-06-15",
        "height_cm": 175.0,
        "weight_kg": 70.0,
        "fitness_goal": "lose_fat",
        "allergies": ["peanut"],
        "dietary_restrictions": ["no_pork"],
    }


@pytest.fixture
def profile_payload():
    return {
        "height_cm": 178.0,
        "weight_kg": 68.0,
        "fitness_goal": "build_muscle",
        "allergies": ["milk", "seafood"],
        "dietary_restrictions": [],
    }


@pytest.fixture
def food_image_base64():
    return (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
        "+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )


@pytest.fixture
def sample_recipes():
    return [
        {
            "id": uuid.UUID("10000000-0000-0000-0000-000000000001"),
            "name": "鸡胸肉沙拉",
            "meal_type": "lunch",
            "category": "salad",
            "nutrition_per_serving": {"calories": 350, "protein_g": 38, "fat_g": 12, "carbs_g": 18},
            "suitable_goal": "lose_fat",
            "ingredients": [{"name": "鸡胸肉", "amount_g": 200}, {"name": "生菜", "amount_g": 100}],
        },
        {
            "id": uuid.UUID("10000000-0000-0000-0000-000000000002"),
            "name": "红烧牛肉面",
            "meal_type": "lunch",
            "category": "chinese",
            "nutrition_per_serving": {"calories": 650, "protein_g": 35, "fat_g": 22, "carbs_g": 70},
            "suitable_goal": "build_muscle",
            "ingredients": [{"name": "牛肉", "amount_g": 150}, {"name": "面条", "amount_g": 200}],
        },
        {
            "id": uuid.UUID("10000000-0000-0000-0000-000000000003"),
            "name": "燕麦粥",
            "meal_type": "breakfast",
            "category": "chinese",
            "nutrition_per_serving": {"calories": 280, "protein_g": 8, "fat_g": 5, "carbs_g": 50},
            "suitable_goal": "all",
            "ingredients": [{"name": "燕麦", "amount_g": 60}, {"name": "牛奶", "amount_g": 200}],
        },
    ]


@pytest.fixture
def fitness_checkin_payload():
    return {
        "exercise_type": "running",
        "duration_min": 30,
        "intensity": 7,
        "calories_burned": 320,
        "notes": "慢跑 5 公里",
    }


@pytest.fixture
def api_key_payload():
    return {
        "deepseek_api_key": "sk-test-deepseek-key-12345",
        "deepseek_base_url": "https://api.deepseek.com",
        "qwen_api_key": "sk-test-qwen-key-67890",
        "qwen_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "tavily_api_key": "tvly-test-tavily-key-abcde",
    }


# ============================================================
# FastAPI TestClient
# ============================================================


@pytest_asyncio.fixture
async def client(db_session):
    """FastAPI 测试客户端（已注入 SQLite override）."""
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def auth_client(client, user_payload):
    """已认证的 HTTP 客户端（自动登录拿 JWT）."""
    resp = await client.post("/api/auth/login", json=user_payload)
    if resp.status_code == 200:
        token = resp.json()["data"]["access_token"]
        client.headers["Authorization"] = f"Bearer {token}"
    return client


# ============================================================
# Seed helpers — 在测试前插入预置数据
# ============================================================


@pytest_asyncio.fixture
async def seeded_recipes(db_session, sample_recipes):
    """将测试食谱插入数据库."""
    from app.models.recipe import Recipe

    for r in sample_recipes:
        recipe = Recipe(
            id=r["id"],
            name=r["name"],
            category=r["category"],
            meal_type=r["meal_type"],
            cooking_method="stir_fry",
            prep_time_min=10,
            cook_time_min=15,
            difficulty="easy",
            image_url=f"https://example.com/{r['name']}.jpg",
            ingredients=r["ingredients"],
            steps=["步骤1", "步骤2"],
            nutrition_per_serving=r["nutrition_per_serving"],
            serving_size="1人份",
            tags=["test"],
            suitable_goal=r["suitable_goal"],
        )
        db_session.add(recipe)
    await db_session.commit()
    return sample_recipes


# ============================================================
# Mock 外部服务
# ============================================================


@pytest.fixture
def mock_deepseek():
    """Mock DeepSeek Chat API —— patch 在 agent.py 的导入位置.

    Agent 使用 astream_events，需要 mock 支持迭代流式输出。
    """
    with patch("app.agent.agent.ChatDeepSeek") as mock:
        instance = MagicMock()
        instance.ainvoke = AsyncMock(
            return_value=MagicMock(content="这是Agent的回复内容。")
        )
        # astream_events 需要 model 能创建 agent + executor 并 stream
        # 我们保持 ainvoke 作为 fallback，但实际 Agent 流程更复杂
        instance.bind_tools = MagicMock(return_value=instance)
        mock.return_value = instance
        yield instance


@pytest.fixture
def mock_wechat():
    """Mock 微信登录 API."""
    with patch("wechatpy.WeChatClient") as mock:
        instance = MagicMock()
        instance.oauth.get_user_info = MagicMock(
            return_value={
                "openid": "test_openid_abc123",
                "nickname": "测试用户",
                "headimgurl": "https://example.com/avatar.jpg",
            }
        )
        mock.return_value = instance
        yield instance


@pytest.fixture
def mock_qwen_vision():
    """Mock Qwen-VL —— patch 在 food_recognition tool 导入位置."""
    with patch("app.agent.tools.food_recognition.ChatOpenAI") as mock:
        instance = MagicMock()
        instance.ainvoke = AsyncMock(
            return_value=MagicMock(
                content='[{"name":"宫保鸡丁","calories_per_100g":175,'
                '"estimated_weight_g":350,"estimated_calories":612,'
                '"protein_g":28.5,"fat_g":38.2,"carbs_g":22.8}]'
            )
        )
        mock.return_value = instance
        yield instance
