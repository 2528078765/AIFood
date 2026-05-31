"""AI recipe generator — calls DeepSeek to create personalized recipes."""

import json
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.api_key_service import get_user_llm_config
from app.services.body_fat import estimate_body_fat
from app.services.calorie_service import calculate_user_daily_target, distribute_meals

logger = logging.getLogger(__name__)

MEAL_LABELS = {"breakfast": "早餐", "lunch": "午餐", "dinner": "晚餐"}

SYSTEM_PROMPT = """你是一个专业营养师和健身教练。根据用户的身体数据、体脂率、运动能力和健身目标，设计科学健康的餐食。

只返回一个 JSON 对象，格式如下，不要任何其他文字：
{
  "recipes": [
    {
      "name": "菜名",
      "description": "一句话介绍这道菜",
      "ingredients": [
        {"name": "食材名", "amount": "用量"},
        {"name": "食材名", "amount": "用量"}
      ],
      "steps": ["步骤1", "步骤2", "步骤3"],
      "nutrition_per_serving": {"calories": 400, "protein_g": 30, "fat_g": 12, "carbs_g": 45},
      "cooking_method": "stir_fry/boil/steam/bake/raw",
      "prep_time_min": 15,
      "cook_time_min": 20,
      "difficulty": "easy/medium/hard",
      "tips": "烹饪小贴士"
    }
  ]
}
生成 3 道菜。体脂率偏高时优先低脂高蛋白；增肌目标时适当提高碳水和蛋白质；减脂目标时控制总热量、提高蛋白质占比。"""


def _build_user_prompt(user: User, meal_type: str, meal_budget: int,
                       body_fat_info: dict | None = None,
                       exercise_details: str | None = None) -> str:
    label = MEAL_LABELS.get(meal_type, meal_type)
    parts = [f"请为以下用户设计 3 道{label}食谱："]
    parts.append(f"- 健身目标：{user.fitness_goal or '保持健康'}")
    parts.append(f"- 身高：{user.height_cm or '未设置'}cm，体重：{user.weight_kg or '未设置'}kg")

    # Body fat info
    if body_fat_info and body_fat_info.get("body_fat_pct"):
        bf = body_fat_info["body_fat_pct"]
        bmi = body_fat_info.get("bmi", "?")
        ffmi = body_fat_info.get("ffmi", "?")
        level = body_fat_info.get("strength_level", "unknown")
        parts.append(f"- 估算体脂率：{bf}%（BMI {bmi}，FFMI {ffmi}，力量水平：{level}）")
        if level in ("beginner", "novice"):
            parts.append("- 力量水平偏低，建议适当增加蛋白质摄入")
        elif level in ("advanced", "elite"):
            parts.append("- 力量水平较高，训练强度大，需要充足的碳水和蛋白质")

    # Exercise details
    if exercise_details:
        parts.append(f"- 运动详情：{exercise_details.strip()}")

    if user.allergies:
        parts.append(f"- 过敏：{', '.join(user.allergies)}")
    if user.dietary_restrictions:
        parts.append(f"- 饮食限制：{', '.join(user.dietary_restrictions)}")
    parts.append(f"- 本餐热量预算：约 {meal_budget} 千卡")
    parts.append("- 食材要常见易买，步骤简单明了")
    return "\n".join(parts)


async def generate_recipes(
    user_id: str,
    meal_type: str,
    db: AsyncSession,
    exercise_details: str | None = None,
) -> dict:
    uid = uuid.UUID(user_id)
    result = await db.execute(select(User).where(User.id == uid))
    user = result.scalar_one_or_none()
    if not user:
        return {"recipes": [], "warning": "用户不存在"}

    # Estimate body fat from profile + exercise details
    body_fat_info = estimate_body_fat(
        height_cm=user.height_cm,
        weight_kg=user.weight_kg,
        gender=user.gender,
        birthday=user.birthday,
        exercise_details=exercise_details or user.exercise_details,
    )

    # Calculate meal budget
    if user.daily_calorie_target:
        daily = user.daily_calorie_target
    elif user.gender and user.weight_kg and user.height_cm and user.birthday:
        daily = calculate_user_daily_target(
            gender=user.gender, weight_kg=user.weight_kg,
            height_cm=user.height_cm, birthday=user.birthday,
            goal=user.fitness_goal or "maintain",
        )
    else:
        daily = 2000
    budgets = distribute_meals(daily_target=daily)
    meal_budget = budgets.get(meal_type, daily // 3)

    # Call DeepSeek
    llm_config = await get_user_llm_config(user_id, db)

    if not llm_config.deepseek_api_key:
        return {
            "recipes": [],
            "meal_budget": meal_budget,
            "daily_target": daily,
            "body_fat": body_fat_info,
            "warning": "请先在「我的」→「API 密钥设置」中配置 DeepSeek API Key",
        }

    user_prompt = _build_user_prompt(
        user, meal_type, meal_budget,
        body_fat_info=body_fat_info,
        exercise_details=exercise_details or user.exercise_details,
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    try:
        from langchain_deepseek import ChatDeepSeek

        llm = ChatDeepSeek(
            model="deepseek-chat",
            temperature=0.7,
            max_tokens=2048,
            api_key=llm_config.deepseek_api_key,
            api_base=llm_config.deepseek_base_url,
        )
        response = llm.invoke(messages)
        raw = response.content if hasattr(response, "content") else str(response)
    except Exception as e:
        logger.error(f"DeepSeek call failed: {e}")
        return {
            "recipes": [],
            "meal_budget": meal_budget,
            "daily_target": daily,
            "body_fat": body_fat_info,
            "warning": f"AI 服务调用失败，请检查 API Key 是否正确",
        }

    # Parse JSON
    try:
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.startswith("```")]
            text = "\n".join(lines)
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"AI recipe parse failed: {e}\nRaw: {raw[:500]}")
        return {"recipes": [], "warning": f"AI 生成失败，请重试", "raw": raw[:500]}

    recipes = data.get("recipes", [])
    # Add unique IDs
    for r in recipes:
        r["id"] = str(uuid.uuid4())
        r["meal_type"] = meal_type
        r["ai_generated"] = True

    return {
        "recipes": recipes,
        "meal_budget": meal_budget,
        "daily_target": daily,
        "body_fat": body_fat_info,
    }
