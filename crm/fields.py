"""Encrypted Django model fields for PBX credentials.

Uses ``cryptography.fernet.Fernet`` directly (available as a transitive
dependency; no extra package) so we can store DB + AMI passwords for each
tenant's ``PbxServer`` without exposing plaintext in the DB.

Key management:
- ``settings.FERNET_KEY`` is the active key used for new writes.
- ``settings.FERNET_KEYS_FALLBACK`` is an optional list of retired keys;
  when decryption with the active key fails we try each fallback so key
  rotation doesn't require a mass re-encrypt.

Raises on misconfiguration at first use (lazy import of settings).
"""
from __future__ import annotations

from typing import Iterable

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import models


def _load_fernets() -> MultiFernet:
    key = getattr(settings, "FERNET_KEY", None)
    if not key:
        raise ImproperlyConfigured(
            "FERNET_KEY setting is required to use EncryptedCharField. "
            "Generate one with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
        )
    fallbacks: Iterable[str] = getattr(settings, "FERNET_KEYS_FALLBACK", []) or []
    keys = [key] + [k for k in fallbacks if k]
    return MultiFernet([Fernet(k.encode() if isinstance(k, str) else k) for k in keys])


class EncryptedCharField(models.TextField):
    """Stores a string encrypted at rest with Fernet.

    Python-side value is a regular string. DB-side column is TEXT (cipher
    text is longer than plaintext + varies per write thanks to Fernet's IV).
    """

    description = "String field encrypted at rest (Fernet)"

    def from_db_value(self, value, expression, connection):  # noqa: D401
        if value is None or value == "":
            return value
        try:
            return _load_fernets().decrypt(value.encode()).decode()
        except InvalidToken:
            # Row predates this key or key was rotated without a fallback
            # configured. Surface as empty so forms don't crash; admins
            # should re-enter the credential.
            return ""

    def to_python(self, value):
        return value

    def get_prep_value(self, value):
        if value is None or value == "":
            return value
        return _load_fernets().encrypt(value.encode()).decode()
