"""SGAE/CCB: motor puro de decisiones de experiencia, sin efectos secundarios.

Ninguna decisión se infiere del email, de cookies del navegador o del silencio.
No crea consentimientos, no habilita publicidad ni lee datos personales.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum


class Action(str, Enum):
    LINK_REQUIRED = "link_required"
    CONTRACT_REQUIRED = "contract_required"
    OPTIONAL_PERMISSION_REQUIRED = "optional_permission_required"
    READY = "ready"
    GENERAL_SERVICE = "general_service"


@dataclass(frozen=True)
class ConsentProof:
    purpose: str
    product: str
    allowed: bool
    notice_version: str
    captured_at: datetime
    expires_at: datetime | None = None
    revoked_at: datetime | None = None

    def valid(self, *, purpose: str, product: str, notice_version: str, now: datetime) -> bool:
        if self.purpose != purpose or self.product != product or self.notice_version != notice_version:
            return False
        if self.captured_at.tzinfo is None or now.tzinfo is None:
            return False
        if self.captured_at > now:
            return False
        if self.expires_at is not None and (self.expires_at.tzinfo is None or now >= self.expires_at):
            return False
        if self.revoked_at is not None and self.revoked_at <= now:
            return False
        return self.allowed is True


@dataclass(frozen=True)
class Resolution:
    action: Action
    personal_context_permitted: bool
    checkout_blocked_by_optional_consent: bool = False


def resolve(
    *,
    identity_verified: bool,
    required_contract_version: str,
    accepted_contract_version: str | None,
    optional_purpose: str | None,
    product: str,
    notice_version: str,
    proof: ConsentProof | None,
    now: datetime | None = None,
) -> Resolution:
    """Determina el siguiente paso de UI, no una autorización de base de datos."""
    now = now or datetime.now(timezone.utc)
    if not identity_verified:
        return Resolution(Action.LINK_REQUIRED, False)
    if not required_contract_version or accepted_contract_version != required_contract_version:
        return Resolution(Action.CONTRACT_REQUIRED, False)
    if optional_purpose is None:
        return Resolution(Action.READY, False)
    if proof is None or not proof.valid(
        purpose=optional_purpose, product=product, notice_version=notice_version, now=now
    ):
        return Resolution(Action.OPTIONAL_PERMISSION_REQUIRED, False)
    return Resolution(Action.READY, True)


def general_service_after_decline() -> Resolution:
    """Rechazar un permiso opcional jamás bloquea el servicio general."""
    return Resolution(Action.GENERAL_SERVICE, False, False)
