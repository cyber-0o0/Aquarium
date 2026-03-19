from typing import Any, Dict, List, Optional
from pydantic import BaseModel, field_validator, Field
from datetime import datetime
import json

MAX_MANIFEST_DEPTH = 10
MAX_MANIFEST_BYTES = 64_000


def _check_depth(obj: Any, current: int = 0) -> int:
    """Recursively find the maximum nesting depth of a dict/list."""
    if current > MAX_MANIFEST_DEPTH:
        raise ValueError(f"Manifest nesting exceeds maximum depth of {MAX_MANIFEST_DEPTH}")
    if isinstance(obj, dict):
        for v in obj.values():
            _check_depth(v, current + 1)
    elif isinstance(obj, list):
        for item in obj:
            _check_depth(item, current + 1)


def _check_manifest_safe(manifest: Dict[str, Any]) -> None:
    """Reject manifests that are too deep, too large, or non-serializable."""
    # 1. Check depth first (fast, catches deeply nested before serialization)
    _check_depth(manifest)

    # 2. Check serializability and size
    try:
        serialized = json.dumps(manifest)
    except (ValueError, TypeError) as e:
        raise ValueError(f"Manifest contains non-serializable data: {e}")

    if len(serialized) > MAX_MANIFEST_BYTES:
        raise ValueError(f"Manifest too large (max {MAX_MANIFEST_BYTES // 1000}KB)")


# ── Skill schemas ──────────────────────────────────────────────────────────────

class SkillBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    slug: str = Field(..., min_length=1, max_length=128)
    description: str = Field(..., min_length=1, max_length=2048)
    category: str
    version: str = "1.0.0"
    price_ton: str = "0"
    icon_url: Optional[str] = None
    color: str = "#6366F1"
    manifest: Dict[str, Any]

    @field_validator("manifest")
    @classmethod
    def manifest_must_be_safe(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        _check_manifest_safe(v)
        return v


class SkillCreate(SkillBase):
    pass


class SkillUpdate(BaseModel):
    description: Optional[str] = Field(None, max_length=2048)
    version: Optional[str] = None
    price_ton: Optional[str] = None
    icon_url: Optional[str] = None
    color: Optional[str] = None
    manifest: Optional[Dict[str, Any]] = None

    @field_validator("manifest")
    @classmethod
    def manifest_must_be_safe(cls, v: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if v is not None:
            _check_manifest_safe(v)
        return v


class Skill(SkillBase):
    id: str
    rating: float
    installs: int
    review_status: str
    author_id: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── SkillReview schemas ────────────────────────────────────────────────────────

class SkillReviewCreate(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = Field(None, max_length=1024)

    @field_validator("rating")
    @classmethod
    def rating_range(cls, v: int) -> int:
        if not (1 <= v <= 5):
            raise ValueError("Rating must be between 1 and 5")
        return v


class SkillReview(BaseModel):
    id: str
    skill_id: str
    user_id: str
    rating: int
    comment: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Install / uninstall ────────────────────────────────────────────────────────

class SkillInstallRequest(BaseModel):
    agent_id: str
    skill_id: str
