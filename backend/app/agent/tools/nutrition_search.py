"""
Nutrition search tool: fuzzy-search the local nutrition database for foods.

The database is a JSON file at app/data/nutrition_db.json containing common
Chinese foods with per-100g nutrition data.
"""
import json as json_lib
import os
from pathlib import Path
from typing import Optional

from langchain.tools import tool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NUTRITION_DB: Optional[list[dict]] = None


def _get_db_path() -> Path:
    """Resolve the nutrition_db.json path relative to this file."""
    return Path(__file__).resolve().parent.parent.parent / "data" / "nutrition_db.json"


def _load_nutrition_db() -> list[dict]:
    """Load (and cache) the nutrition database from disk."""
    global _NUTRITION_DB
    if _NUTRITION_DB is not None:
        return _NUTRITION_DB

    db_path = _get_db_path()
    if not db_path.exists():
        raise FileNotFoundError(
            f"营养数据库文件不存在: {db_path}。"
            f"请联系管理员创建 backend/app/data/nutrition_db.json 文件。"
        )

    with open(db_path, "r", encoding="utf-8") as fh:
        _NUTRITION_DB = json_lib.load(fh)

    return _NUTRITION_DB


def _fuzzy_match(keyword: str, db: list[dict], limit: int = 5) -> list[dict]:
    """Search *db* for foods whose `name` or `name_en` contains *keyword* (case-insensitive)."""
    kw_lower = keyword.strip().lower()
    if not kw_lower:
        return []

    matches = []
    for food in db:
        name = (food.get("name") or "").lower()
        name_en = (food.get("name_en") or "").lower()
        if kw_lower in name or kw_lower in name_en:
            matches.append(food)

    return matches[:limit]


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------

@tool
def search_nutrition(keyword: str) -> str:
    """搜索本地食物营养数据库，根据食物名称查找营养信息。

    参数:
    - keyword: 食物名称关键词（必填），支持中文或英文。

    返回: JSON 格式的搜索结果列表（最多5条匹配），或错误/提示信息。

    使用场景:
    - 用户询问某食物的营养信息时调用
    - 支持模糊匹配（如搜索"鸡"会匹配"鸡胸肉""鸡蛋"等）
    """
    try:
        db = _load_nutrition_db()
    except FileNotFoundError as e:
        return f"[错误] {e}"
    except json_lib.JSONDecodeError as e:
        return f"[错误] 营养数据库格式错误，无法解析: {e}"
    except Exception as e:
        return f"[错误] 加载营养数据库失败: {e}"

    matches = _fuzzy_match(keyword, db)

    if not matches:
        return (
            f"[提示] 未找到与 '{keyword}' 相关的食物营养数据。"
            f"请尝试使用更通用的食物名称搜索（如'鸡肉'而非'红烧鸡块'）。"
        )

    return json_lib.dumps(matches, ensure_ascii=False, indent=2)
