from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet

from app.core.config import get_settings


class SchedulingCryptoService:
    def __init__(self) -> None:
        settings = get_settings()
        seed = settings.resolved_integration_encryption_secret().encode("utf-8")
        key = base64.urlsafe_b64encode(hashlib.sha256(seed).digest())
        self.fernet = Fernet(key)

    def encrypt(self, value: str | None) -> str | None:
        if not value:
            return None
        return self.fernet.encrypt(value.encode("utf-8")).decode("utf-8")

    def decrypt(self, value: str | None) -> str | None:
        if not value:
            return None
        return self.fernet.decrypt(value.encode("utf-8")).decode("utf-8")
