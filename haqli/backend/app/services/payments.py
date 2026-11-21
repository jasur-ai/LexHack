"""PaymentProvider interface with SimulatedProvider (zero live Payme/Click calls per Rule 1)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from app.db import uuid7_str


@dataclass
class PaymentResult:
    payment_id: str
    provider: str
    status: str
    amount_uzs: Decimal


class PaymentProvider(Protocol):
    name: str

    async def create_payment(self, *, order_id: str, amount_uzs: Decimal, user_id: str) -> PaymentResult: ...


class SimulatedProvider:
    """Instant simulated payment provider for demo & dev. Swap for PaymeProvider/ClickProvider post-launch."""

    name = "simulated"

    async def create_payment(self, *, order_id: str, amount_uzs: Decimal, user_id: str) -> PaymentResult:
        return PaymentResult(
            payment_id=f"sim_{uuid7_str()[:12]}",
            provider=self.name,
            status="paid",
            amount_uzs=amount_uzs,
        )


def get_payment_provider() -> PaymentProvider:
    return SimulatedProvider()
