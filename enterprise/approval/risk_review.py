"""Bounded, text-free risk review through an existing native Skyvern model."""

RISK_MODEL_KEY = "GEMINI_2.5_FLASH"


async def review_risk(prompt: str) -> dict:
    from skyvern.forge.sdk.api.llm.api_handler_factory import LLMAPIHandlerFactory
    from skyvern.forge.sdk.api.llm.config_registry import LLMConfigRegistry

    if RISK_MODEL_KEY not in LLMConfigRegistry.get_model_names():
        raise ValueError("Risk review model is unavailable")
    handler = LLMAPIHandlerFactory.get_llm_api_handler(RISK_MODEL_KEY, strict_response=True)
    return await handler(
        prompt=prompt, prompt_name="procurement-risk-review",
        parameters={"max_completion_tokens": 2048, "temperature": 0, "timeout": 12},
    )
