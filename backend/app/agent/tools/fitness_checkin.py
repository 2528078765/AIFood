"""
Fitness check-in tool: log a user's exercise activity.
"""
import uuid
from datetime import date
from typing import Optional

from langchain.tools import tool


from app.database import async_session
from app.models.fitness import FitnessCheckin

# ---------------------------------------------------------------------------
# Valid exercise types
# ---------------------------------------------------------------------------

VALID_EXERCISE_TYPES = frozenset({
    "running",
    "swimming",
    "weightlifting",
    "yoga",
    "cycling",
    "hiit",
    "other",
})


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------

@tool
async def log_fitness(
    exercise_type: str,
    duration_min: int,
    intensity: Optional[int] = None,
    notes: Optional[str] = None,
) -> str:
    """记录一次健身打卡活动。

    参数:
    - exercise_type: 运动类型（必填），可选值: running, swimming, weightlifting, yoga, cycling, hiit, other
    - duration_min: 运动时长（分钟，必填）
    - intensity: 运动强度 1-10（选填）
    - notes: 备注说明（选填）

    返回: 打卡确认信息和记录详情，或错误信息。
    该工具将打卡记录写入 fitness_checkins 表。
    """
    from app.agent.context import get_agent_context
    ctx = get_agent_context()
    user_id = ctx.get("user_id", "")
    db = ctx.get("db")
    session = db if db is not None else async_session()
    close_session = db is None

    try:
        # Validate exercise_type
        ex_type = exercise_type.strip().lower()
        if ex_type not in VALID_EXERCISE_TYPES:
            valid_list = ", ".join(sorted(VALID_EXERCISE_TYPES))
            return (
                f"[错误] 无效的运动类型 '{exercise_type}'。"
                f"可选值: {valid_list}"
            )

        # Validate duration
        if duration_min <= 0:
            return "[错误] 运动时长必须为正整数（分钟）。"

        # Validate intensity range
        if intensity is not None and not (1 <= intensity <= 10):
            return "[错误] 运动强度必须在 1-10 之间。"

        # Build record
        record = FitnessCheckin(
            id=uuid.uuid4(),
            user_id=uuid.UUID(user_id),
            exercise_type=ex_type,
            duration_min=duration_min,
            intensity=intensity,
            notes=notes.strip() if notes else None,
            checkin_date=date.today(),
        )

        session.add(record)
        await session.commit()
        await session.refresh(record)

        return (
            f"[打卡成功] 已记录 {ex_type} 运动 {duration_min} 分钟"
            + (f"，强度 {intensity}/10" if intensity else "")
            + (f"，备注: {notes}" if notes else "")
            + f"。打卡日期: {record.checkin_date}，记录ID: {record.id}。"
        )

    except Exception as exc:
        if close_session:
            await session.rollback()
        return f"[错误] 健身打卡记录失败: {exc}"
    finally:
        if close_session:
            await session.close()
