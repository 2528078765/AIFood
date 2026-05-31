"""
Recipe recommendation tool: suggest meals based on user profile.
Delegates to recipe_service for all filtering/scoring logic.
"""
import json as json_lib
from datetime import date

from langchain.tools import tool


from app.database import async_session
from app.services import recipe_service

VALID_MEAL_TYPES = frozenset({"breakfast", "lunch", "dinner"})


@tool
async def recommend_recipe(
    date_str: str,
    meal_type: str,
) -> str:
    """根据用户档案推荐餐食食谱。

    参数:
    - date_str: 日期字符串，格式 YYYY-MM-DD（必填）
    - meal_type: 餐食类型（必填），可选值: breakfast, lunch, dinner

    返回: JSON 格式的推荐食谱列表（最多3条），包含食谱详情，或错误/提示信息。
    """
    from app.agent.context import get_agent_context
    ctx = get_agent_context()
    user_id = ctx.get("user_id", "")
    db = ctx.get("db")
    session = db if db is not None else async_session()
    close_session = db is None

    try:
        mt = meal_type.strip().lower()
        if mt not in VALID_MEAL_TYPES:
            return f"[错误] 无效的餐食类型 '{meal_type}'。可选值: breakfast, lunch, dinner"

        try:
            target_date = date.fromisoformat(date_str)
        except (ValueError, TypeError):
            return f"[错误] 无效的日期格式 '{date_str}'，请使用 YYYY-MM-DD 格式。"

        recipes = await recipe_service.get_meal_recommendation(
            user_id=user_id,
            target_date=target_date,
            meal_type=mt,
            db=session,
            top_n=3,
        )

        if not recipes:
            return f"[提示] 未找到符合您条件的 {mt} 食谱，请尝试调整偏好或过段时间再来。"

        return json_lib.dumps(recipes, ensure_ascii=False, indent=2)

    except Exception as exc:
        return f"[错误] 食谱推荐失败: {exc}"
    finally:
        if close_session:
            await session.close()
