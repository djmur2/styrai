"""Application workflow for policy decisions and human approval."""

from __future__ import annotations

import hashlib
import hmac
import json
from copy import deepcopy
from uuid import uuid4

from .audit import HashChainedAuditLog
from .models import (
    ActionRequest,
    ActionStatus,
    Decision,
    GovernedAction,
    PolicyDecision,
)
from .policy import PolicyEngine
from .registry import ModelPassportRegistry


class GovernanceWorkflowError(RuntimeError):
    """Raised when a governed action is moved through an invalid state."""


class GovernanceService:
    def __init__(
        self,
        engine: PolicyEngine,
        audit_log: HashChainedAuditLog,
        registry: ModelPassportRegistry | None = None,
    ) -> None:
        self.engine = engine
        self.audit_log = audit_log
        self.registry = registry
        self._actions: dict[str, GovernedAction] = {}

    @staticmethod
    def _issue_receipt(governed: GovernedAction) -> str:
        receipt_claims = {
            "action": governed.request.evidence_view(),
            "decision": governed.decision.as_dict(),
            "approved_by": sorted(governed.approved_by),
        }
        canonical = json.dumps(
            receipt_claims, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        return "styrai_receipt_v1_" + hashlib.sha256(canonical).hexdigest()

    def _authorize(self, governed: GovernedAction, basis: str) -> None:
        governed.status = ActionStatus.AUTHORIZED
        governed.authorization_receipt = self._issue_receipt(governed)
        self.audit_log.append(
            "action.authorized",
            governed.request.action_id,
            {
                "authorization_basis": basis,
                "approval_id": governed.approval_id,
                "approved_by": sorted(governed.approved_by),
                "policy_version": governed.decision.policy_version,
                "authorization_receipt": governed.authorization_receipt,
            },
        )

    def propose(self, request: ActionRequest) -> GovernedAction:
        # Keep the governed copy isolated from any mutable dictionary owned by
        # the caller. The parameter digest in evidence_view then binds the
        # exact approved payload without retaining that payload in evidence.
        request = deepcopy(request)
        if request.action_id in self._actions:
            raise GovernanceWorkflowError("Action IDs must be unique.")

        self.audit_log.append(
            "action.proposed", request.action_id, request.evidence_view()
        )
        decision: PolicyDecision
        if self.registry is not None:
            assessment = self.registry.assess(request)
            self.audit_log.append(
                "model.passport_checked", request.action_id, assessment.as_dict()
            )
            if assessment.allowed:
                decision = self.engine.evaluate(request)
            else:
                decision = PolicyDecision(
                    effect=Decision.DENY,
                    policy_version=self.engine.policy_set.version,
                    rule_id=f"model-passport:{assessment.code}",
                    reason=assessment.reason,
                    required_approvals=0,
                )
        else:
            decision = self.engine.evaluate(request)
        status_by_decision = {
            Decision.ALLOW: ActionStatus.AUTHORIZED,
            Decision.DENY: ActionStatus.DENIED,
            Decision.REQUIRE_APPROVAL: ActionStatus.WAITING_APPROVAL,
        }
        approval_id = (
            str(uuid4()) if decision.effect is Decision.REQUIRE_APPROVAL else None
        )
        governed = GovernedAction(
            request=request,
            decision=decision,
            status=status_by_decision[decision.effect],
            approval_id=approval_id,
        )
        self._actions[request.action_id] = governed
        self.audit_log.append(
            "policy.decided",
            request.action_id,
            {
                **decision.as_dict(),
                "status": governed.status.value,
                "approval_id": approval_id,
            },
        )
        if governed.status is ActionStatus.AUTHORIZED:
            self._authorize(governed, "policy")
        return governed

    def decide_approval(
        self,
        action_id: str,
        approver_id: str,
        approved: bool,
        rationale: str,
    ) -> GovernedAction:
        governed = self._actions.get(action_id)
        if governed is None:
            raise GovernanceWorkflowError("Unknown action.")
        if governed.status is not ActionStatus.WAITING_APPROVAL:
            raise GovernanceWorkflowError("Action is not waiting for approval.")
        if not rationale.strip():
            raise GovernanceWorkflowError("Approval decisions require a rationale.")
        if approver_id == governed.request.on_behalf_of:
            raise GovernanceWorkflowError("The action initiator cannot approve the action.")
        if approver_id in governed.approved_by:
            raise GovernanceWorkflowError("Each approval must come from a distinct person.")

        if approved:
            governed.approved_by.append(approver_id)
            enough_approvals = (
                len(governed.approved_by) >= governed.decision.required_approvals
            )
            governed.status = (
                ActionStatus.AUTHORIZED
                if enough_approvals
                else ActionStatus.WAITING_APPROVAL
            )
        else:
            governed.status = ActionStatus.DENIED
        event_type = "approval.granted" if approved else "approval.denied"
        self.audit_log.append(
            event_type,
            action_id,
            {
                "approval_id": governed.approval_id,
                "approver_id": approver_id,
                "rationale": rationale.strip(),
                "resulting_status": governed.status.value,
                "policy_version": governed.decision.policy_version,
                "approvals_received": len(governed.approved_by),
                "approvals_required": governed.decision.required_approvals,
            },
        )
        if approved and governed.status is ActionStatus.AUTHORIZED:
            self._authorize(governed, "human_approval")
        return governed

    def get(self, action_id: str) -> GovernedAction:
        try:
            return self._actions[action_id]
        except KeyError as exc:
            raise GovernanceWorkflowError("Unknown action.") from exc

    def assert_authorized(self, action_id: str) -> GovernedAction:
        """Return an action only when its current claims match its receipt."""

        governed = self.get(action_id)
        if (
            governed.status is not ActionStatus.AUTHORIZED
            or not governed.authorization_receipt
        ):
            raise GovernanceWorkflowError("The action is not authorized.")
        expected = self._issue_receipt(governed)
        if not hmac.compare_digest(expected, governed.authorization_receipt):
            raise GovernanceWorkflowError(
                "The approved action payload changed after authorization."
            )
        return governed

    def list_actions(self) -> tuple[GovernedAction, ...]:
        return tuple(self._actions.values())
