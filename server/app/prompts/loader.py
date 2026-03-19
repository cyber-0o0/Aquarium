"""
Loader for agent prompt templates.

Usage:
    from app.prompts.loader import load_prompt
    prompt = load_prompt("ton_analyst")
"""
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent


def load_prompt(name: str) -> str:
    """Load a prompt template by name (without .md extension)."""
    path = PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt template '{name}' not found at {path}")
    return path.read_text(encoding="utf-8")


def list_prompts() -> list[str]:
    """Return all available prompt template names."""
    return [p.stem for p in PROMPTS_DIR.glob("*.md")]
