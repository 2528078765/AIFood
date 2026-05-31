"""Recipe recommendation engine — daily meal curation for fitness goals."""

import logging
import uuid
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.recipe import Recipe, RecipeRecommendation
from app.models.user import User
from app.services.calorie_service import calculate_user_daily_target, distribute_meals

logger = logging.getLogger(__name__)

DEFAULT_DAILY_TARGET = 2000
DEFAULT_GOAL = "maintain"
MEAL_BUDGET_RATIO = {"breakfast": 0.3, "lunch": 0.4, "dinner": 0.3}

# 膳食限制 → 匹配词列表（用于食材名/菜名过滤）
RESTRICTION_KEYWORDS: dict[str, list[str]] = {
    "no_pork": ["猪肉", "猪", "排骨", "猪蹄", "五花", "腊肉", "火腿", "猪肝", "猪肚", "猪血"],
    "no_beef": ["牛肉", "牛腩", "牛", "肥牛", "牛肚", "牛舌", "牛排"],
    "no_lamb": ["羊肉", "羊", "羊排", "羊腿", "羊杂"],
    "no_seafood": ["虾", "蟹", "鱼", "贝", "鱿", "海参", "蛤", "蛏", "蚝", "扇贝", "三文鱼", "金枪鱼", "鳕鱼", "鲈鱼", "鲫鱼"],
    "no_egg": ["鸡蛋", "蛋", "蛋黄", "蛋白", "鸭蛋", "鹌鹑蛋", "蛋液", "蛋花"],
    "no_dairy": ["牛奶", "奶", "奶酪", "黄油", "奶油", "芝士", "酸奶", "炼乳", "淡奶"],
    "no_soy": ["豆腐", "豆浆", "豆奶", "腐竹", "豆皮", "千张"],
    "no_cilantro": ["香菜", "芫荽"],
    "no_spicy": ["辣椒", "辣", "花椒", "麻", "红油", "辣油", "豆瓣酱", "剁椒", "泡椒", "干辣椒"],
    "no_garlic": ["蒜", "大蒜", "葱", "洋葱", "蒜苗", "蒜薹", "韭菜", "蒜泥"],
    "no_organ": ["猪肝", "猪肚", "猪心", "猪肺", "鸡心", "鸡肝", "鸭血", "猪血", "牛肚", "肥肠", "腰花", "脑花", "内脏"],
    "vegetarian": ["猪肉", "牛肉", "鸡肉", "羊肉", "鸭肉", "鹅肉", "鱼", "虾", "蟹", "猪", "牛", "鸡", "羊", "鸭", "肉", "排骨", "火腿", "培根", "腊肉", "牛腩", "肥牛", "鸡胸", "鸡腿", "鸡翅", "猪肝", "猪肚", "肥肠", "内脏"],
    "vegan": ["猪肉", "牛肉", "鸡肉", "羊肉", "鸭肉", "鹅肉", "鱼", "虾", "蟹", "猪", "牛", "鸡", "羊", "鸭", "肉", "排骨", "火腿", "培根", "腊肉", "牛腩", "肥牛", "鸡胸", "鸡腿", "鸡翅", "猪肝", "猪肚", "肥肠", "内脏", "牛奶", "鸡蛋", "奶", "蛋", "奶酪", "黄油", "奶油", "芝士", "蜂蜜"],
}

# 过敏原中英文映射（前端传英文 key，需匹配中文食材名）
ALLERGEN_CHINESE: dict[str, list[str]] = {
    "peanut": ["花生", "花生酱", "花生油"],
    "milk": ["牛奶", "奶", "奶酪", "黄油", "奶油", "芝士", "酸奶", "炼乳", "淡奶", "乳清"],
    "seafood": ["虾", "蟹", "鱼", "贝", "鱿", "海参", "蛤", "蛏", "蚝", "扇贝", "三文鱼", "金枪鱼", "鳕鱼", "鲈鱼", "鲫鱼", "虾仁", "虾皮", "鱼露"],
    "egg": ["鸡蛋", "蛋", "蛋黄", "蛋白", "鸭蛋", "鹌鹑蛋", "蛋液", "蛋花", "蛋糕"],
    "gluten": ["面粉", "面条", "面包", "馒头", "小麦", "麸质", "面筋", "大麦", "黑麦", "全麦", "饼干"],
    "soy": ["豆腐", "豆浆", "豆奶", "腐竹", "豆皮", "千张", "黄豆", "酱油", "豆豉", "味噌", "毛豆", "豆芽"],
    "nut": ["核桃", "杏仁", "腰果", "开心果", "榛子", "松子", "夏威夷果", "花生", "花生酱", "芝麻", "芝麻酱", "芝麻油", "瓜子", "南瓜子"],
    "sesame": ["芝麻", "芝麻酱", "芝麻油", "白芝麻", "黑芝麻", "香油"],
}


def _extract_ingredient_names(recipe: Recipe) -> list[str]:
    """从 recipe.ingredients (JSONB list-of-dicts) 中提取原料名称列表。"""
    ings = recipe.ingredients
    if not ings:
        return []
    if isinstance(ings, list):
        return [item["name"] for item in ings if isinstance(item, dict) and "name" in item]
    if isinstance(ings, dict):
        # 兼容旧格式 {name: amount}
        return list(ings.keys())
    return []


def _has_allergen(recipe: Recipe, allergies: list[str]) -> bool:
    """检查食谱原料是否含有过敏原（支持中文映射）。"""
    if not allergies:
        return False
    ingredient_names = _extract_ingredient_names(recipe)
    ingredient_text = " ".join(ingredient_names)
    for allergen in allergies:
        # 检查中英文关键词
        keywords = ALLERGEN_CHINESE.get(allergen, [allergen])
        for kw in keywords:
            if kw in ingredient_text:
                return True
    return False


def _has_restricted_ingredient(recipe: Recipe, restrictions: list[str]) -> bool:
    """检查食谱原料/名称是否涉及用户饮食限制。"""
    if not restrictions:
        return False
    ingredient_names = _extract_ingredient_names(recipe)
    # 也检查菜名自身
    combined = " ".join([recipe.name] + ingredient_names)
    for restriction in restrictions:
        keywords = RESTRICTION_KEYWORDS.get(restriction, [])
        for kw in keywords:
            if kw in combined:
                return True
    return False


def _matches_goal(recipe: Recipe, goal: str) -> bool:
    """食谱的 suitable_goal 是否匹配用户目标（"all" 通配所有）。"""
    if not recipe.suitable_goal:
        return True
    if recipe.suitable_goal == "all":
        return True
    return recipe.suitable_goal == goal


def _calorie_score(recipe: Recipe, budget: int) -> float:
    """基于热量与预算接近程度的评分（越近分越高，满分 100）。"""
    if not recipe.nutrition_per_serving:
        return 0.0
    cals = recipe.nutrition_per_serving.get("calories", 0)
    if budget <= 0:
        return 0.0
    diff = abs(cals - budget)
    return max(0.0, 100.0 - (diff / budget) * 100.0)


async def _get_user_profile(user_id: str, db: AsyncSession) -> User | None:
    try:
        uid = uuid.UUID(user_id)
    except (ValueError, TypeError):
        return None
    result = await db.execute(select(User).where(User.id == uid))
    return result.scalar_one_or_none()


async def _get_recent_recommended_ids(
    user_id: uuid.UUID,
    meal_type: str,
    lookback_days: int,
    db: AsyncSession,
) -> set[uuid.UUID]:
    since = date.today() - timedelta(days=lookback_days)
    stmt = select(RecipeRecommendation.recipe_id).where(
        RecipeRecommendation.user_id == user_id,
        RecipeRecommendation.meal_type == meal_type,
        RecipeRecommendation.date >= since,
    )
    result = await db.execute(stmt)
    return {row[0] for row in result.fetchall()}


async def _query_candidate_recipes(
    meal_type: str,
    goal: str,
    db: AsyncSession,
) -> list[Recipe]:
    """查询匹配 meal_type 和 goal（或 "all"）的食谱。"""
    stmt = select(Recipe).where(
        Recipe.meal_type == meal_type,
        Recipe.suitable_goal.in_([goal, "all"]),
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


def _filter_and_score(
    recipes: list[Recipe],
    allergies: list[str],
    restrictions: list[str],
    budget: int,
    exclude_ids: set[uuid.UUID],
) -> list[tuple[Recipe, float]]:
    """过滤 + 评分，返回 (recipe, score) 列表，按分降序。"""
    scored: list[tuple[Recipe, float]] = []
    for recipe in recipes:
        if recipe.id in exclude_ids:
            continue
        if _has_allergen(recipe, allergies):
            continue
        if _has_restricted_ingredient(recipe, restrictions):
            continue
        scored.append((recipe, _calorie_score(recipe, budget)))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


def _recipe_to_dict(recipe: Recipe, warning: str | None = None) -> dict:
    d = {
        "id": str(recipe.id),
        "name": recipe.name,
        "category": recipe.category,
        "meal_type": recipe.meal_type,
        "cooking_method": recipe.cooking_method,
        "prep_time_min": recipe.prep_time_min,
        "cook_time_min": recipe.cook_time_min,
        "difficulty": recipe.difficulty,
        "image_url": recipe.image_url,
        "ingredients": recipe.ingredients,
        "steps": recipe.steps,
        "nutrition_per_serving": recipe.nutrition_per_serving,
        "serving_size": recipe.serving_size,
        "tags": recipe.tags,
        "suitable_goal": recipe.suitable_goal,
    }
    if warning:
        d["warning"] = warning
    return d


async def _record_recommendation(
    user_id: uuid.UUID,
    recipe_id: uuid.UUID,
    target_date: date,
    meal_type: str,
    db: AsyncSession,
) -> None:
    rec = RecipeRecommendation(
        id=uuid.uuid4(),
        user_id=user_id,
        recipe_id=recipe_id,
        date=target_date,
        meal_type=meal_type,
        is_accepted=None,
    )
    db.add(rec)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def get_meal_recommendation(
    user_id: str,
    target_date: date,
    meal_type: str,  # breakfast / lunch / dinner
    db: AsyncSession,
    top_n: int = 3,
) -> list[dict]:
    """返回单餐的推荐食谱列表（字典形式）。

    支持 5 级降级策略：
    1. 完整过滤（allergen + restriction + 7 天不重复）
    2. 放宽 7 天重复限制
    3. 放宽所有过滤，仅匹配 meal_type + goal
    4. 忽略 goal 限制（所有 meal_type 食谱）
    5. 返回空列表
    """
    if meal_type not in ("breakfast", "lunch", "dinner"):
        raise ValueError(f"未知的 meal_type: {meal_type}，仅支持 breakfast/lunch/dinner")

    user = await _get_user_profile(user_id, db)

    # 用户默认值
    if user and user.daily_calorie_target:
        daily_target = user.daily_calorie_target
    elif user and user.gender and user.weight_kg and user.height_cm and user.birthday:
        goal = user.fitness_goal or DEFAULT_GOAL
        daily_target = calculate_user_daily_target(
            gender=user.gender,
            weight_kg=user.weight_kg,
            height_cm=user.height_cm,
            birthday=user.birthday,
            goal=goal,
        )
    else:
        daily_target = DEFAULT_DAILY_TARGET

    meal_budget = distribute_meals(daily_target=daily_target).get(meal_type, daily_target // 3)

    goal = user.fitness_goal if user and user.fitness_goal else DEFAULT_GOAL
    allergies = user.allergies if user else []
    restrictions = user.dietary_restrictions if user else []

    uid = uuid.UUID(user_id) if user else uuid.uuid4()

    # 候选食谱
    candidates = await _query_candidate_recipes(meal_type, goal, db)

    # 策略 1：完整过滤
    recent_ids = await _get_recent_recommended_ids(uid, meal_type, 7, db)
    scored = _filter_and_score(candidates, allergies, restrictions, meal_budget, recent_ids)
    warning = None

    # 策略 2：放宽 7 天不重复
    if not scored and recent_ids:
        scored = _filter_and_score(candidates, allergies, restrictions, meal_budget, set())
        if scored:
            warning = "重复推荐（近 7 日已展示过该餐）"

    # 策略 3：放宽所有过滤（allergen + restriction），只保留 meal_type + goal
    if not scored:
        scored = [(r, _calorie_score(r, meal_budget)) for r in candidates if _matches_goal(r, goal)]
        scored.sort(key=lambda x: x[1], reverse=True)
        if scored:
            warning = "未能完全匹配您的饮食偏好，已展示可用食谱"

    # 策略 4：忽略 goal
    if not scored:
        all_meal = await db.execute(
            select(Recipe).where(Recipe.meal_type == meal_type)
        )
        fallback = list(all_meal.scalars().all())
        scored = [(r, _calorie_score(r, meal_budget)) for r in fallback]
        scored.sort(key=lambda x: x[1], reverse=True)
        if scored:
            warning = "暂无精准匹配，展示该餐段全部食谱"

    # 策略 5：无结果
    if not scored:
        logger.warning(f"用户 {user_id} 的 {meal_type} 推荐结果为空")
        return []

    # 取 top_n
    top_recipes = scored[:top_n]

    # 写推荐记录
    for recipe, _score in top_recipes:
        await _record_recommendation(uid, recipe.id, target_date, meal_type, db)

    return [_recipe_to_dict(r, warning) for r, _s in top_recipes]


async def get_daily_recommendations(
    user_id: str,
    target_date: date,
    db: AsyncSession,
) -> dict[str, list[dict]]:
    """返回 {"breakfast": [...], "lunch": [...], "dinner": [...]}"""
    results: dict[str, list[dict]] = {}
    for meal_type in ("breakfast", "lunch", "dinner"):
        results[meal_type] = await get_meal_recommendation(
            user_id=user_id,
            target_date=target_date,
            meal_type=meal_type,
            db=db,
        )
    return results
