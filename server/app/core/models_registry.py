"""
Central registry of all supported AI models.

Providers:
  openai            — OpenAI API
  anthropic         — Anthropic API
  google            — Google Gemini
  mistral           — Mistral AI
  openai_compatible — Any OpenAI-compatible endpoint (Groq, DeepSeek, Cocoon, custom)
"""

from typing import Dict, Any, Optional

SUPPORTED_MODELS: Dict[str, Dict[str, Any]] = {

    # ── OpenAI ──────────────────────────────────────────────────────────────
    "gpt-4o": {
        "label": "GPT-4o",
        "provider": "openai",
        "api_key_env": "OPENAI_API_KEY",
        "context_window": 128_000,
        "supports_tools": True,
        "tier": "premium",
        "description": "OpenAI flagship multimodal model - High quality",
    },
    "gpt-4o-mini": {
        "label": "GPT-4o mini",
        "provider": "openai",
        "api_key_env": "OPENAI_API_KEY",
        "context_window": 128_000,
        "supports_tools": True,
        "tier": "free",
        "description": "Best price/quality for small tasks. Very affordable.",
    },
    "gpt-5-nano": {
        "label": "GPT-5 nano",
        "provider": "openai",
        "api_key_env": "OPENAI_API_KEY",
        "context_window": 128_000,
        "supports_tools": True,
        "tier": "free",
        "description": "Next-gen nano model - Extremely fast, smart and cheap",
    },


    # ── Anthropic ────────────────────────────────────────────────────────────
    "claude-3-7-sonnet-20250219": {
        "label": "Claude 3.7 Sonnet",
        "provider": "anthropic",
        "api_key_env": "ANTHROPIC_API_KEY",
        "context_window": 200_000,
        "supports_tools": True,
        "tier": "premium",
        "description": "Most capable model for coding and complex logic.",
    },
    "claude-3-5-haiku-20241022": {
        "label": "Claude 3.5 Haiku",
        "provider": "anthropic",
        "api_key_env": "ANTHROPIC_API_KEY",
        "context_window": 200_000,
        "supports_tools": True,
        "tier": "free",
        "description": "Fast and intelligent Haiku version.",
    },

    # ── Google Gemini ────────────────────────────────────────────────────────
    "gemini-2.0-flash": {
        "label": "Gemini 2.0 Flash",
        "provider": "google",
        "api_key_env": "GOOGLE_API_KEY",
        "context_window": 1_000_000,
        "supports_tools": True,
        "tier": "free",
        "description": "Google's ultra-fast multimodal model with 1M context.",
    },

    # ── Groq (OpenAI-compatible) ─────────────────────────────────────────────
    "llama-3.3-70b-versatile": {
        "label": "Llama 3.3 70B (Groq)",
        "provider": "openai_compatible",
        "api_key_env": "GROQ_API_KEY",
        "base_url": "https://api.groq.com/openai/v1",
        "context_window": 128_000,
        "supports_tools": True,
        "tier": "free",
        "description": "Llama 3.3 via Groq — extremely fast and efficient.",
    },

    # ── DeepSeek (OpenAI-compatible) ─────────────────────────────────────────
    "deepseek-chat": {
        "label": "DeepSeek Chat (V3)",
        "provider": "openai_compatible",
        "api_key_env": "DEEPSEEK_API_KEY",
        "base_url": "https://api.deepseek.com/v1",
        "context_window": 64_000,
        "supports_tools": True,
        "tier": "free",
        "description": "Powerful cheap alternative to GPT-4o.",
    },
    "deepseek-reasoner": {
        "label": "DeepSeek R1",
        "provider": "openai_compatible",
        "api_key_env": "DEEPSEEK_API_KEY",
        "base_url": "https://api.deepseek.com/v1",
        "context_window": 64_000,
        "supports_tools": False,
        "tier": "free",
        "description": "Best reasoning model per dollar.",
    },

    # ── Cocoon (TON decentralized AI network, OpenAI-compatible) ─────────────
    "cocoon/deepseek-r1-qwen-7b": {
        "label": "DeepSeek R1 Qwen 7B (Cocoon)",
        "provider": "openai_compatible",
        "api_key_env": "COCOON_API_KEY",
        "base_url": "https://cocoon.ton.org/v1",
        "context_window": 32_000,
        "supports_tools": False,
        "tier": "free",
        "description": "DeepSeek R1 via Cocoon (TON decentralized AI, privacy-first)",
        "badge": "TON",
    },
    "cocoon/qwen2.5-72b": {
        "label": "Qwen 2.5 72B (Cocoon)",
        "provider": "openai_compatible",
        "api_key_env": "COCOON_API_KEY",
        "base_url": "https://cocoon.ton.org/v1",
        "context_window": 128_000,
        "supports_tools": True,
        "tier": "free",
        "description": "Qwen 2.5 72B via Cocoon — decentralized, pays GPU owners in TON",
        "badge": "TON",
    },
}


def get_model_info(model_id: str) -> Optional[Dict[str, Any]]:
    return SUPPORTED_MODELS.get(model_id)


def is_valid_model(model_id: str) -> bool:
    return model_id in SUPPORTED_MODELS


def models_for_plan(plan: str) -> Dict[str, Dict[str, Any]]:
    if plan in ("premium", "enterprise"):
        return SUPPORTED_MODELS
    return {k: v for k, v in SUPPORTED_MODELS.items() if v["tier"] == "free"}


def get_providers() -> list:
    return list({v["provider"] for v in SUPPORTED_MODELS.values()})


def cocoon_models() -> Dict[str, Dict[str, Any]]:
    """Return only Cocoon models."""
    return {k: v for k, v in SUPPORTED_MODELS.items() if k.startswith("cocoon/")}
