"""
Dashboard tool: aggregate today's food, fitness, and streak data for a user.
Delegates streak & stats to fitness_service to avoid code duplication.
"""
import json as json_lib
import uuid
from datetime import date

from langchain.tools import tool
from sqlalchemy import func, select


from app.database import async_session
from app.models.fitness import FitnessCheckin
from app.models.food_record import FoodRecord
from app.models.user import User
from app.services import fitness_service


@tool
async def get_dashboard() -> str:
    """获取用户今日仪表盘数据，包含饮食、运动和连续打卡情况。

    返回: JSON 格式的仪表盘聚合数据，包含:
    - date: 当前日期
    - calories: 今日已摄入热量、目标热量、完成百分比
    - meals: 各餐次热量摄入明细 (breakfast/lunch/dinner)
    - fitness: 今日是否打卡、连续打卡天数、本周运动统计
    """
    from app.agent.context import get_agent_context
    ctx = get_agent_context()
    user_id = ctx.get("user_id", "")
    db = ctx.get("db")
    session = db if db is not None else async_session()
    close_session = db is None

    try:
        user_uuid = uuid.UUID(user_id)
        today = date.today()

        # --- Load user ---
        user_result = await session.execute(
            select(User).where(User.id == user_uuid)
        )
        user = user_result.scalar_one_or_none()
        if user is None:
            return f"[错误] 未找到用户 {user_id}。"

        daily_target = user.daily_calorie_target or 2000

        # --- Today's food calories (total) ---
        food_result = await session.execute(
            select(func.coalesce(func.sum(FoodRecord.total_calories), 0)).where(
                FoodRecord.user_id == user_uuid,
                FoodRecord.recorded_at == today,
            )
        )
        consumed = food_result.scalar() or 0

        # --- Per-meal breakdown ---
        meal_calories: dict[str, int] = {"breakfast": 0, "lunch": 0, "dinner": 0}
        meal_result = await session.execute(
            select(FoodRecord.meal_type, func.sum(FoodRecord.total_calories)).where(
                FoodRecord.user_id == user_uuid,
                FoodRecord.recorded_at == today,
            ).group_by(FoodRecord.meal_type)
        )
        for row in meal_result.all():
            mt = row[0] or "other"
            cal = int(row[1] or 0)
            if mt in meal_calories:
                meal_calories[mt] += cal

        # --- Today's check-in status ---
        checkin_result = await session.execute(
            select(FitnessCheckin).where(
                FitnessCheckin.user_id == user_uuid,
                FitnessCheckin.checkin_date == today,
            )
        )
        checked_in_today = checkin_result.scalar_one_or_none() is not None

        # --- Streak & week stats (delegated to fitness_service) ---
        streak = await fitness_service.get_streak(str(user_uuid), session)
        week_stats = await fitness_service.get_stats(str(user_uuid), "week", session)

        # --- Build dashboard ---
        percentage = round(consumed / max(daily_target, 1) * 100, 1)
        dashboard_data = {
            "date": str(today),
            "calories": {
                "consumed": consumed,
                "target": daily_target,
                "percentage": percentage,
            },
            "meals": meal_calories,
            "fitness": {
                "checked_in_today": checked_in_today,
                "streak_days": streak,
                "week_stats": week_stats,
            },
        }
        return json_lib.dumps(dashboard_data, ensure_ascii=False, indent=2)

    except ValueError:
        return f"[错误] 无效的用户 ID 格式: {user_id}"
    except Exception as exc:
        return f"[错误] 仪表盘数据获取失败: {exc}"
    finally:
        if close_session:
            await session.close()
