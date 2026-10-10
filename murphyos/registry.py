"""Model and agent passport controls for approved use at runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import ActionRequest


@dataclass(frozen=True)
class ModelPassport:
    model_id: str
    version: str
    provider: str
    owner: str
    risk_tier: str
    intended_uses: tuple[str, ...]
    allowed_tools: tuple[str, ...]
    allowed_classifications: tuple[str, ...]
    status: str = "approved"

    @property
    def key(self) -> tuple[str, str]:
        return (self.model_id, self.version)


@dataclass(frozen=True)
class PassportAssessment:
    allowed: bool
    code: str
    reason: str
    registry_version: str
    model_id: str
    model_version: str
    owner: str | None = None
    risk_tier: str | None = None
    provider: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "code": self.code,
            "reason": self.reason,
            "registry_version": self.registry_version,
            "model_id": self.model_id,
            "model_version": self.model_version,
            "owner": self.owner,
            "risk_tier": self.risk_tier,
            "provider": self.provider,
        }


class ModelPassportRegistry:
    def __init__(self, version: str, passports: tuple[ModelPassport, ...]) -> None:
        self.version = version
        self._passports = {passport.key: passport for passport in passports}
        if len(self._passports) != len(passports):
            raise ValueError("Model passport keys must be unique.")

    def assess(self, action: ActionRequest) -> PassportAssessment:
        passport = self._passports.get((action.model_id, action.model_version))
        if passport is None:
            return PassportAssessment(
                allowed=False,
                code="model_not_registered",
                reason="The exact model and version has no approved passport.",
                registry_version=self.version,
                model_id=action.model_id,
                model_version=action.model_version,
            )

        common = {
            "registry_version": self.version,
            "model_id": passport.model_id,
            "model_version": passport.version,
            "owner": passport.owner,
            "risk_tier": passport.risk_tier,
            "provider": passport.provider,
        }
        if passport.status != "approved":
            return PassportAssessment(
                allowed=False,
                code="model_not_approved",
                reason=f"The model passport status is {passport.status!r}.",
                **common,
            )
        if action.use_case not in passport.intended_uses:
            return PassportAssessment(
                allowed=False,
                code="unapproved_use_case",
                reason="The proposed use is outside the model's approved intended uses.",
                **common,
            )
        if action.tool not in passport.allowed_tools:
            return PassportAssessment(
                allowed=False,
                code="unapproved_tool",
                reason="The model is not approved to use the proposed tool.",
                **common,
            )
        if action.resource_classification not in passport.allowed_classifications:
            return PassportAssessment(
                allowed=False,
                code="unapproved_data_classification",
                reason="The model is not approved for this data classification.",
                **common,
            )
        return PassportAssessment(
            allowed=True,
            code="passport_approved",
            reason="The exact model version and proposed use match an approved passport.",
            **common,
        )

    def passports(self) -> tuple[ModelPassport, ...]:
        return tuple(self._passports.values())

