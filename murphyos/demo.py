"""Run a small governed-action demonstration."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .audit import HashChainedAuditLog
from .models import ActionRequest, Decision, PolicyRule, PolicySet
from .policy import PolicyEngine
from .registry import ModelPassport, ModelPassportRegistry
from .service import GovernanceService


def demo_policy() -> PolicySet:
    return PolicySet(
        version="demo-2026-08-22.2",
        rules=(
            PolicyRule(
                rule_id="four-eyes-material-payment",
                description=(
                    "Financial payments of 100,000 or more require two distinct "
                    "human approvers."
                ),
                effect=Decision.REQUIRE_APPROVAL,
                priority=400,
                tool="payments",
                operation="release",
                industries=("financial_services",),
                minimum_amount=100_000,
                required_approvals=2,
            ),
            PolicyRule(
                rule_id="approve-financial-payment",
                description="Every agent-proposed financial payment requires approval.",
                effect=Decision.REQUIRE_APPROVAL,
                priority=350,
                tool="payments",
                operation="release",
                industries=("financial_services",),
                required_approvals=1,
            ),
            PolicyRule(
                rule_id="approve-healthcare-visit-summary",
                description=(
                    "Publishing an AI-drafted patient visit summary requires one "
                    "accountable human approval."
                ),
                effect=Decision.REQUIRE_APPROVAL,
                priority=325,
                tool="patient_portal",
                operation="publish_summary",
                industries=("healthcare",),
                required_approvals=1,
            ),
            PolicyRule(
                rule_id="deny-restricted-external-send",
                description="Restricted information cannot be sent externally.",
                effect=Decision.DENY,
                priority=300,
                tool="email",
                operation="send_external",
                resource_classifications=("restricted",),
            ),
            PolicyRule(
                rule_id="approve-external-email",
                description="External email requires a named human approver.",
                effect=Decision.REQUIRE_APPROVAL,
                priority=200,
                tool="email",
                operation="send_external",
            ),
            PolicyRule(
                rule_id="allow-internal-read",
                description="Agents may read public or internal documents.",
                effect=Decision.ALLOW,
                priority=100,
                tool="documents",
                operation="read",
                resource_classifications=("public", "internal"),
            ),
        ),
    )


def demo_registry() -> ModelPassportRegistry:
    return ModelPassportRegistry(
        version="registry-2026-08-22.1",
        passports=(
            ModelPassport(
                model_id="enterprise-language-model",
                version="2026-08",
                provider="approved-third-party-provider",
                owner="Head of Customer Operations",
                risk_tier="medium",
                intended_uses=("customer_service", "customer_communication"),
                allowed_tools=("documents", "email"),
                allowed_classifications=("public", "internal", "restricted"),
            ),
            ModelPassport(
                model_id="approved-operations-model",
                version="2026-08-15",
                provider="customer-hosted",
                owner="Head of Payment Operations",
                risk_tier="high",
                intended_uses=("payment_operations",),
                allowed_tools=("payments",),
                allowed_classifications=("restricted",),
            ),
            ModelPassport(
                model_id="clinical-summary-model",
                version="2026-08-2",
                provider="customer-hosted-healthcare",
                owner="Director of Clinical Informatics",
                risk_tier="high",
                intended_uses=("patient_visit_summary",),
                allowed_tools=("patient_portal",),
                allowed_classifications=("restricted",),
            ),
        ),
    )


def run(audit_path: Path) -> None:
    if audit_path.exists():
        audit_path.unlink()
    service = GovernanceService(
        PolicyEngine(demo_policy()), HashChainedAuditLog(audit_path)
    )

    actions = [
        ActionRequest(
            agent_id="quality-assistant",
            on_behalf_of="employee-1042",
            tool="documents",
            operation="read",
            resource="sop-184",
            resource_classification="internal",
        ),
        ActionRequest(
            agent_id="quality-assistant",
            on_behalf_of="employee-1042",
            tool="email",
            operation="send_external",
            resource="supplier@example.test",
            resource_classification="internal",
        ),
        ActionRequest(
            agent_id="quality-assistant",
            on_behalf_of="employee-1042",
            tool="email",
            operation="send_external",
            resource="supplier@example.test",
            resource_classification="restricted",
        ),
        ActionRequest(
            agent_id="payment-operations-agent",
            on_behalf_of="payments-operator-19",
            tool="payments",
            operation="release",
            resource="payment-batch-8831",
            resource_classification="restricted",
            industry="financial_services",
            use_case="payment_operations",
            model_id="approved-operations-model",
            model_version="2026-08-15",
            risk_attributes={"amount": 250_000, "currency": "NOK"},
        ),
    ]

    governed = [service.propose(action) for action in actions]
    service.decide_approval(
        governed[1].request.action_id,
        approver_id="quality-manager-7",
        approved=True,
        rationale="Supplier is approved and the message contains no restricted data.",
    )
    service.decide_approval(
        governed[3].request.action_id,
        approver_id="payments-manager-4",
        approved=True,
        rationale="Payment batch reconciles to the approved settlement file.",
    )
    service.decide_approval(
        governed[3].request.action_id,
        approver_id="treasury-controller-2",
        approved=True,
        rationale="Independent four-eyes review completed.",
    )

    print("StyrAI governed-action demonstration\n")
    for item in governed:
        current = service.get(item.request.action_id)
        print(json.dumps(current.as_dict(), indent=2))
    print(f"\nAudit records: {len(service.audit_log.records())}")
    print(f"Audit chain valid: {service.audit_log.verify()}")
    print(f"Audit path: {audit_path.resolve()}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--audit-path",
        type=Path,
        default=Path("work/demo-audit.jsonl"),
        help="Location for demonstration audit evidence.",
    )
    args = parser.parse_args()
    run(args.audit_path)


if __name__ == "__main__":
    main()
