"""
Endpoints for managing user-provided API keys.

Users can store their own OpenAI / Anthropic / etc. keys.
Keys are encrypted at rest; responses never expose raw values.
"""
from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.api import deps
from app.core.db import get_db
from app.core.encryption import encrypt_key, decrypt_key
from app.models.user import User as UserModel
from app.models.user_api_key import UserApiKey
from app.schemas.user_api_key import UserApiKeyCreate, UserApiKeyUpdate, UserApiKeyOut

router = APIRouter()


def _to_out(row: UserApiKey) -> UserApiKeyOut:
    """Build safe response — key_hint shows last 4 chars only."""
    raw = decrypt_key(row.encrypted_key) or ""
    hint = ("*" * max(0, len(raw) - 4)) + raw[-4:] if len(raw) >= 4 else "****"
    return UserApiKeyOut(
        id=row.id,
        provider=row.provider,
        label=row.label,
        base_url=row.base_url,
        model_name=row.model_name,
        key_hint=hint,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("", response_model=List[UserApiKeyOut])
async def list_api_keys(
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """List all stored API keys for the current user (hints only)."""
    result = await db.execute(
        select(UserApiKey)
        .where(UserApiKey.user_id == current_user.id)
        .order_by(UserApiKey.provider, UserApiKey.created_at)
    )
    return [_to_out(row) for row in result.scalars().all()]


@router.post("", response_model=UserApiKeyOut, status_code=201)
async def add_api_key(
    key_in: UserApiKeyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Store a new API key for a provider.
    If a key for this provider+label already exists, it is replaced.
    """
    label = key_in.label or key_in.provider

    # Check for existing key with same provider + label
    existing = await db.execute(
        select(UserApiKey).where(
            UserApiKey.user_id == current_user.id,
            UserApiKey.provider == key_in.provider,
            UserApiKey.label == label,
        )
    )
    row = existing.scalars().first()

    encrypted = encrypt_key(key_in.api_key)

    if row:
        # Update in place
        row.encrypted_key = encrypted
        row.base_url = key_in.base_url
        row.model_name = key_in.model_name
    else:
        row = UserApiKey(
            user_id=current_user.id,
            provider=key_in.provider,
            label=label,
            encrypted_key=encrypted,
            base_url=key_in.base_url,
            model_name=key_in.model_name,
        )
        db.add(row)

    await db.commit()
    await db.refresh(row)
    return _to_out(row)


@router.patch("/{key_id}", response_model=UserApiKeyOut)
async def update_api_key(
    key_id: str,
    key_in: UserApiKeyUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """Update an existing API key entry."""
    result = await db.execute(
        select(UserApiKey).where(
            UserApiKey.id == key_id,
            UserApiKey.user_id == current_user.id,
        )
    )
    row = result.scalars().first()
    if not row:
        raise HTTPException(status_code=404, detail="API key not found")

    if key_in.api_key:
        row.encrypted_key = encrypt_key(key_in.api_key)
    if key_in.label is not None:
        row.label = key_in.label
    if key_in.base_url is not None:
        row.base_url = key_in.base_url
    if key_in.model_name is not None:
        row.model_name = key_in.model_name

    await db.commit()
    await db.refresh(row)
    return _to_out(row)


@router.delete("/{key_id}", status_code=204)
async def delete_api_key(
    key_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> None:
    """Delete an API key."""
    result = await db.execute(
        select(UserApiKey).where(
            UserApiKey.id == key_id,
            UserApiKey.user_id == current_user.id,
        )
    )
    row = result.scalars().first()
    if not row:
        raise HTTPException(status_code=404, detail="API key not found")
    await db.delete(row)
    await db.commit()


@router.post("/{key_id}/verify", status_code=200)
async def verify_api_key(
    key_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Do a lightweight ping to confirm the stored key is valid.
    Returns {"valid": true/false, "error": "..."}.
    """
    result = await db.execute(
        select(UserApiKey).where(
            UserApiKey.id == key_id,
            UserApiKey.user_id == current_user.id,
        )
    )
    row = result.scalars().first()
    if not row:
        raise HTTPException(status_code=404, detail="API key not found")

    raw_key = decrypt_key(row.encrypted_key)
    if not raw_key:
        return {"valid": False, "error": "Decryption failed"}

    return await _ping_provider(row.provider, raw_key, row.base_url)


async def _ping_provider(provider: str, api_key: str, base_url: str | None) -> dict:
    """Quick probe to verify an API key is valid."""
    import httpx

    try:
        if provider == "openai" or provider == "openai_compatible":
            url = (base_url or "https://api.openai.com/v1").rstrip("/") + "/models"
            async with httpx.AsyncClient(timeout=8) as c:
                r = await c.get(url, headers={"Authorization": f"Bearer {api_key}"})
            return {"valid": r.status_code == 200, "error": None if r.status_code == 200 else r.text[:200]}

        if provider == "anthropic":
            async with httpx.AsyncClient(timeout=8) as c:
                r = await c.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                    json={"model": "claude-haiku-4-5", "max_tokens": 1, "messages": [{"role": "user", "content": "hi"}]},
                )
            return {"valid": r.status_code in (200, 400), "error": None if r.status_code in (200, 400) else r.text[:200]}

        if provider == "google":
            url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
            async with httpx.AsyncClient(timeout=8) as c:
                r = await c.get(url)
            return {"valid": r.status_code == 200, "error": None if r.status_code == 200 else r.text[:200]}

        if provider == "mistral":
            async with httpx.AsyncClient(timeout=8) as c:
                r = await c.get("https://api.mistral.ai/v1/models", headers={"Authorization": f"Bearer {api_key}"})
            return {"valid": r.status_code == 200, "error": None if r.status_code == 200 else r.text[:200]}

    except Exception as e:
        return {"valid": False, "error": str(e)}

    return {"valid": False, "error": f"No ping available for provider: {provider}"}
