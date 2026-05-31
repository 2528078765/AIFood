"""LangChain tools for the AIFood fitness meal planning agent."""

from app.agent.tools.dashboard import get_dashboard
from app.agent.tools.fitness_checkin import log_fitness
from app.agent.tools.food_recognition import recognize_food
from app.agent.tools.nutrition_search import search_nutrition
from app.agent.tools.recipe_recommend import recommend_recipe
from app.agent.tools.web_search import search_web

__all__ = [
    "get_dashboard",
    "log_fitness",
    "recognize_food",
    "recommend_recipe",
    "search_nutrition",
    "search_web",
]

# Convenience list for passing to an agent executor
ALL_TOOLS = [
    recognize_food,
    search_nutrition,
    recommend_recipe,
    log_fitness,
    get_dashboard,
    search_web,
]
