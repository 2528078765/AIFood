"""Per-request agent context — injected params that tools need but the LLM shouldn't see."""

_ctx: dict = {}


def set_agent_context(user_id: str, db) -> None:
    _ctx["user_id"] = user_id
    _ctx["db"] = db


def get_agent_context() -> dict:
    return _ctx
