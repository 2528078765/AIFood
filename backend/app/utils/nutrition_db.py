"""常见食材营养数据库查询工具。

数据来源参考：
- 中国食物成分表（第 6 版）
- USDA FoodData Central

每 100g 可食部的营养素含量。
"""

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 模块级缓存：启动时加载一次
# ---------------------------------------------------------------------------
_MEMORY_CACHE: list[dict[str, Any]] = []


def _load() -> list[dict[str, Any]]:
    """加载 nutrition_db.json 到内存缓存中。"""
    json_path = os.path.join(os.path.dirname(__file__), "..", "data", "nutrition_db.json")
    try:
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            logger.info("nutrition_db loaded %d foods from %s", len(data), json_path)
            return data
        logger.warning("nutrition_db.json is not a list; returning empty cache")
        return []
    except FileNotFoundError:
        logger.warning("nutrition_db.json not found at %s; nutrition search will return empty", json_path)
        return []
    except json.JSONDecodeError as e:
        logger.error("Failed to parse nutrition_db.json: %s", e)
        return []


# 模块初始化
_MEMORY_CACHE = _load()


def search_food(keyword: str, limit: int = 10) -> list[dict[str, Any]]:
    """按关键词搜索食材（大小写不敏感子串匹配 name / name_en）。

    Args:
        keyword: 搜索词。
        limit:  返回条数上限，默认 10。

    Returns:
        匹配的食材列表（字典形式）。
    """
    if not _MEMORY_CACHE or not keyword:
        return []
    kw = keyword.lower().strip()
    results: list[dict[str, Any]] = []
    for entry in _MEMORY_CACHE:
        name = (entry.get("name") or "").lower()
        name_en = (entry.get("name_en") or "").lower()
        if kw in name or kw in name_en:
            results.append(entry)
            if len(results) >= limit:
                break
    return results


def get_food_by_name(name: str) -> dict[str, Any] | None:
    """按名称精确匹配食材。

    Args:
        name: 食材中文名（大小写不敏感精确匹配）。

    Returns:
        匹配的食材字典，若未找到返回 None。
    """
    if not _MEMORY_CACHE or not name:
        return None
    target = name.lower().strip()
    for entry in _MEMORY_CACHE:
        if (entry.get("name") or "").lower().strip() == target:
            return entry
    return None
