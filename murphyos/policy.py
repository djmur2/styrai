"""Deterministic policy evaluation with a fail-closed default."""

from __future__ import annotations

from .models import ActionRequest, PolicyDecision, PolicySet


class PolicyEngine:
    def __init__(self, policy_set: PolicySet) -> None:
        self.policy_set = policy_set

    def evaluate(self, action: ActionRequest) -> PolicyDecision:
        for rule in sorted(
            self.policy_set.rules, key=lambda item: item.priority, reverse=True
        ):
            if rule.matches(action):
                return PolicyDecision(
                    effect=rule.effect,
                    policy_version=self.policy_set.version,
                    rule_id=rule.rule_id,
                    reason=rule.description,
                    required_approvals=(
                        max(1, rule.required_approvals)
                        if rule.effect.value == "require_approval"
                        else 0
                    ),
                )

        return PolicyDecision(
            effect=self.policy_set.default_effect,
            policy_version=self.policy_set.version,
            rule_id="default",
            reason="No explicit policy rule matched; the system failed closed.",
            required_approvals=0,
        )
