"""
Encryption helpers for user-provided API keys.

Keys are encrypted at rest with Fernet (AES-128-CBC + HMAC-SHA256).
The encryption key is derived from SECRET_KEY in settings so rotating
the app secret automatically invalidates all stored keys.

Usage:
    from app.core.encryption import encrypt_key, decrypt_key

    stored = encrypt_key("sk-...")          # store in DB
    original = decrypt_key(stored)          # retrieve
"""

import base64
import hashlib
from typing import Optional
from cryptography.fernet import Fernet, InvalidToken


def _get_fernet() -> Fernet:
    # Import here to avoid circular dependency with config
    from app.core.config import settings

    # Derive a 32-byte key from SECRET_KEY using SHA-256
    raw = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    fernet_key = base64.urlsafe_b64encode(raw)
    return Fernet(fernet_key)


def encrypt_key(plaintext: str) -> str:
    """Encrypt an API key for storage in the database."""
    f = _get_fernet()
    token = f.encrypt(plaintext.encode())
    return token.decode()


def decrypt_key(ciphertext: str) -> Optional[str]:
    """Decrypt a stored API key. Returns None if decryption fails."""
    try:
        f = _get_fernet()
        plaintext = f.decrypt(ciphertext.encode())
        return plaintext.decode()
    except (InvalidToken, Exception):
        return None
