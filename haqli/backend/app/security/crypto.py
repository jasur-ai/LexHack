"""Field-level Fernet encryption (with key-id prefix rotation), Ed25519 seals, SHA-256 chaining, and PII masking."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
from functools import lru_cache
from typing import Any

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from app.config import Settings, get_settings

_PASSPORT_RE = re.compile(r"\b[A-Z]{2}\s?\d{7}\b")
_PINFL_RE = re.compile(r"\b\d{14}\b")
_CARD_RE = re.compile(r"\b(?:\d{4}[\s-]?){3}\d{4}\b")
_PHONE_RE = re.compile(r"(?:\+?998[\s\-()]*)?\b\d{2}[\s\-()]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}\b")


class CryptoService:
    """Provides Fernet field encryption, Ed25519 document signing/verification, and canonical SHA-256 chaining."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.key_id = self.settings.fernet_key_id or "k1"

        if self.settings.fernet_key:
            f_key = self.settings.fernet_key.encode("utf-8")
        else:
            digest = hashlib.sha256(f"haqli-fernet:{self.settings.jwt_secret}".encode("utf-8")).digest()
            f_key = base64.urlsafe_b64encode(digest)
        self._fernet = Fernet(f_key)

        if self.settings.ed25519_private_key_b64:
            raw_priv = base64.b64decode(self.settings.ed25519_private_key_b64)
            self._ed_priv = Ed25519PrivateKey.from_private_bytes(raw_priv)
        else:
            seed = hashlib.sha256(f"haqli-ed25519:{self.settings.jwt_secret}".encode("utf-8")).digest()
            self._ed_priv = Ed25519PrivateKey.from_private_bytes(seed)
        self._ed_pub: Ed25519PublicKey = self._ed_priv.public_key()

    @property
    def public_key_b64(self) -> str:
        raw = self._ed_pub.public_bytes(Encoding.Raw, PublicFormat.Raw)
        return base64.b64encode(raw).decode("ascii")

    def encrypt_field(self, plaintext: str | None) -> str | None:
        if plaintext is None or plaintext == "":
            return None
        token = self._fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")
        return f"{self.key_id}:{token}"

    def decrypt_field(self, ciphertext: str | None) -> str | None:
        if not ciphertext:
            return None
        raw_token = ciphertext.split(":", 1)[1] if ":" in ciphertext else ciphertext
        return self._fernet.decrypt(raw_token.encode("utf-8")).decode("utf-8")

    @staticmethod
    def mask_passport(passport: str | None) -> str | None:
        if not passport:
            return None
        clean = re.sub(r"\s+", "", passport.upper())
        if len(clean) < 5:
            return "••••"
        return f"{clean[:2]}***{clean[-4:]}"

    @staticmethod
    def mask_pii_text(text: str, party_names: list[str] | None = None) -> tuple[str, dict[str, str]]:
        """Replace passports, PINFLs, cards, phones, and flagged names with stable placeholders (§11)."""
        mapping: dict[str, str] = {}
        out = text

        def _replace(pattern: re.Pattern[str], label: str, s: str) -> str:
            idx = 0

            def _sub(match: re.Match[str]) -> str:
                nonlocal idx
                idx += 1
                tok = f"<{label}_{idx}>"
                mapping[tok] = match.group(0)
                return tok

            return pattern.sub(_sub, s)

        out = _replace(_CARD_RE, "CARD", out)
        out = _replace(_PINFL_RE, "PINFL", out)
        out = _replace(_PASSPORT_RE, "PASSPORT", out)
        out = _replace(_PHONE_RE, "PHONE", out)

        if party_names:
            for i, name in enumerate(party_names, start=1):
                cleaned = name.strip()
                if len(cleaned) >= 3 and cleaned in out:
                    tok = f"<PARTY_{i}>"
                    mapping[tok] = cleaned
                    out = out.replace(cleaned, tok)
        return out, mapping

    @staticmethod
    def canonical_json(payload: dict[str, Any]) -> bytes:
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")

    @staticmethod
    def sha256_hex(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def sha256_canonical(self, payload: dict[str, Any]) -> str:
        return hashlib.sha256(self.canonical_json(payload)).hexdigest()

    def chain_hash(self, prev_hash: str, payload: dict[str, Any]) -> str:
        """H_n = SHA256(H_{n-1} || canonical_json)."""
        return hashlib.sha256(prev_hash.encode("ascii") + self.canonical_json(payload)).hexdigest()

    def seal(self, payload: bytes) -> str:
        sig = self._ed_priv.sign(payload)
        return base64.b64encode(sig).decode("ascii")

    def verify_seal_bytes(self, payload: bytes, signature_b64: str) -> bool:
        try:
            sig = base64.b64decode(signature_b64)
            self._ed_pub.verify(sig, payload)
            return True
        except Exception:
            return False

    def sign_seal(self, doc_hash: str) -> str:
        return self.seal(doc_hash.encode("ascii"))

    def verify_seal(self, doc_hash: str, signature_b64: str) -> bool:
        return self.verify_seal_bytes(doc_hash.encode("ascii"), signature_b64)

    @staticmethod
    def constant_time_eq(a: str, b: str) -> bool:
        return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))

    @staticmethod
    def hash_ip(ip: str) -> str:
        return hashlib.sha256(f"haqli-ip:{ip}".encode("utf-8")).hexdigest()[:24]


@lru_cache(maxsize=1)
def get_crypto() -> CryptoService:
    return CryptoService()


def encrypt_field(plaintext: str | None) -> str | None:
    return get_crypto().encrypt_field(plaintext)


def decrypt_field(ciphertext: str | None) -> str | None:
    return get_crypto().decrypt_field(ciphertext)


def sha256_hex(data: bytes) -> str:
    return CryptoService.sha256_hex(data)


def seal(data: bytes) -> str:
    return get_crypto().seal(data)


def verify_seal(data: bytes, sig: str) -> bool:
    return get_crypto().verify_seal_bytes(data, sig)
