"""Bounded enterprise plans; native Skyvern remains the only browser executor."""

import asyncio
import json

STEPS = ("execute_native", "persist_quote")


async def call_quote_planner(prompt: str) -> dict:
    from skyvern.forge.sdk.api.llm.api_handler_factory import LLMAPIHandlerFactory
    from skyvern.forge.sdk.api.llm.config_registry import LLMConfigRegistry

    key = "GEMINI_2.5_FLASH"
    if key not in LLMConfigRegistry.get_model_names():
        raise ValueError("Quote planner model unavailable")
    return await LLMAPIHandlerFactory.get_llm_api_handler(key, strict_response=True)(
        prompt=prompt, prompt_name="procurement-quote-plan",
        parameters={"max_completion_tokens": 2048, "temperature": 0, "timeout": 12},
    )


async def plan_quote(*, native_completed: bool, previous: dict | None = None) -> dict:
    return await plan_steps(STEPS, completed=list(STEPS[:1] if native_completed else ()), previous=previous)


async def plan_steps(steps: tuple[str, ...], *, completed: list[str], previous: dict | None = None) -> dict:
    """Plan only the authoritative suffix of a server-owned native sequence."""
    if not steps or len(set(steps)) != len(steps) or list(steps[:len(completed)]) != completed:
        raise ValueError("Invalid native completion sequence")
    remaining = list(steps[len(completed):])
    if not remaining:
        return {"steps": [], "completed": completed, "source": "deterministic_fallback"}
    if previous is not None and previous.get("steps") == remaining and previous.get("completed") == completed:
        if previous.get("source") in ("llm", "deterministic_fallback"):
            return {"steps": remaining, "completed": completed, "source": previous["source"]}
    prompt = (
        'Return exactly a JSON object with one key "steps", containing the remaining steps in order. '
        'Do not repeat completed steps. Do not add actions or explanations.\n'
        + json.dumps({"remaining": remaining, "completed": completed})
    )
    source = "deterministic_fallback"
    try:
        async with asyncio.timeout(15):
            result = await call_quote_planner(prompt)
        if type(result) is dict and set(result) == {"steps"} and result["steps"] == remaining:
            source = "llm"
    except Exception:
        pass
    return {"steps": remaining, "completed": completed, "source": source}
