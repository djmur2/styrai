"""Core data structures for the governed-action workflow."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4


class Decision(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


class ActionStatus(StrEnum):
    PROPOSED = "proposed"
    WAITING_APPROVAL = "waiting_approval"
    AUTHORIZED = "authorized"
    DENIED = "denied"


@dataclass(frozen=True)
class ActionRequest:
    agent_id: str
    on_behalf_of: str
    tool: str
    operation: str
    resource: str
    resource_classification: str
    industry: str = "general"
    use_case: str = "unspecified"
    model_id: str = "unregistered-model"
    model_version: str = "unknown"
    risk_attributes: dict[str, Any] = field(default_factory=dict)
    parameters: dict[str, Any] = field(default_factory=dict)
    action_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat(timespec="milliseconds")
    )

    def evidence_view(self) -> dict[str, Any]:
        """Return metadata suitable for the prototype audit record.

        Raw parameters are intentionally omitted. Risk attributes must be a
        deliberately allow-listed set of non-sensitive policy inputs. A
        production implementation must classify and redact every evidence field
        before persistence.
        """

        parameters_sha256 = hashlib.sha256(
            json.dumps(
                self.parameters,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()
        return {
            "action_id": self.action_id,
            "agent_id": self.agent_id,
            "on_behalf_of": self.on_behalf_of,
            "tool": self.tool,
            "operation": self.operation,
            "resource": self.resource,
            "resource_classification": self.resource_classification,
            "industry": self.industry,
            "use_case": self.use_case,
            "model_id": self.model_id,
            "model_version": self.model_version,
            "risk_attributes": self.risk_attributes,
            "parameters_sha256": parameters_sha256,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class PolicyRule:
    rule_id: str
    description: str
    effect: Decision
    priority: int
    tool: str = "*"
    operation: str = "*"
    resource_classifications: tuple[str, ...] = ("*",)
    industries: tuple[str, ...] = ("*",)
    minimum_amount: float | None = None
    required_approvals: int = 0

    def matches(self, action: ActionRequest) -> bool:
        tool_matches = self.tool in {"*", action.tool}
        operation_matches = self.operation in {"*", action.operation}
        classification_matches = (
            "*" in self.resource_classifications
            or action.resource_classification in self.resource_classifications
        )
        industry_matches = "*" in self.industries or action.industry in self.industries
        amount_matches = True
        if self.minimum_amount is not None:
            amount = action.risk_attributes.get("amount")
            amount_matches = (
                isinstance(amount, (int, float))
                and not isinstance(amount, bool)
                and amount >= self.minimum_amount
            )
        return (
            tool_matches
            and operation_matches
            and classification_matches
            and industry_matches
            and amount_matches
        )


@dataclass(frozen=True)
class PolicySet:
    version: str
    rules: tuple[PolicyRule, ...]
    default_effect: Decision = Decision.DENY


@dataclass(frozen=True)
class PolicyDecision:
    effect: Decision
    policy_version: str
    rule_id: str
    reason: str
    required_approvals: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "effect": self.effect.value,
            "policy_version": self.policy_version,
            "rule_id": self.rule_id,
            "reason": self.reason,
            "required_approvals": self.required_approvals,
        }


@dataclass
class GovernedAction:
    request: ActionRequest
    decision: PolicyDecision
    status: ActionStatus
    approval_id: str | None = None
    approved_by: list[str] = field(default_factory=list)
    authorization_receipt: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "action": self.request.evidence_view(),
            "decision": self.decision.as_dict(),
            "status": self.status.value,
            "approval_id": self.approval_id,
            "approved_by": list(self.approved_by),
            "approvals_received": len(self.approved_by),
            "authorization_receipt": self.authorization_receipt,
        }
