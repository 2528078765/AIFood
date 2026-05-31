"""AES-256-GCM 加解密 —— 用于保护用户 API Key."""

import os
from base64 import b64decode, b64encode

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import settings


def _get_key() -> bytes:
    raw = settings.encryption_key
    if len(raw) != 64:
        raise ValueError("ENCRYPTION_KEY must be 64 hex chars (32 bytes)")
    return bytes.fromhex(raw)


def encrypt_api_key(plaintext: str) -> str:
    if not plaintext:
        return ""
    key = _get_key()
    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return b64encode(nonce + ciphertext).decode("utf-8")


def decrypt_api_key(ciphertext_b64: str) -> str:
    if not ciphertext_b64:
        return ""
    key = _get_key()
    raw = b64decode(ciphertext_b64)
    nonce, ciphertext = raw[:12], raw[12:]
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext.decode("utf-8")


def mask_api_key(key: str) -> str:
    """脱敏：保留首4位 + *** + 尾4位."""
    if len(key) <= 8:
        return key[:2] + "****" + key[-2:]
    return key[:4] + "****" + key[-4:]
