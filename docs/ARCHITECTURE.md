# StyrAI Architecture Direction

## What the current prototype proves

```text
AI inventory + exact model/use passport
                  |
                  v
Fictional employee application
                  |
                  v
StyrAI runtime overlay / enforcement gateway
        | classify data + inspect destination/version/use
        | redact / allow / block
        v
Local deterministic model adapter ---> safe draft
                                           |
                                           v
                                  proposed external action
                                           |
                              policy + named human approval
                                           |
                                authorisation receipt
                                           |
                                           v
                              local simulated tool adapter
                                           |
                                delivery/outcome receipt

Every stage ------> shared correlation IDs ------> hash-chained evidence
                                                        |
                                      command centre + evidence export
```

The demonstration is deterministic and local. The policy, redaction, passport,
approval, authorisation, execution gate and hash chain run as code. The external
model and email delivery are deliberately replaced by local adapters, so no
network or external side effect occurs. Runtime evidence stores a prompt hash,
classification, detected pattern types, destination, decision and controls; it
excludes the raw input, redacted preview and email body from the audit log.

The original governed-action workflow remains available underneath the broader
platform. It demonstrates fail-closed policy decisions, exact model passports,
one- and two-person approval, separation of duties and action-bound receipts.

## Production target

```text
Customer environment                            StyrAI control plane

Apps, agents and model SDKs                     Tenant / identity boundary
          |                                                |
Customer-side gateway / SDK --------------------> policy decision API
  - identity context                              - asset + owner registry
  - DLP/classification                            - model/use passports
  - local redaction                               - versioned policy
  - prompt remains local                          - approval orchestration
          |                                       - incident workflows
Approved provider or local model                  - control/evidence mapping
          |                                                |
Telemetry / outcomes ----------------------------> monitoring + evidence store
                                                          |
                                             SIEM / GRC / ticketing exports
```

StyrAI is provider- and framework-neutral. A small customer-side connector
should intercept model calls, perform sensitive-data inspection close to the
source, request a short-lived decision and emit metadata-only outcomes. The cloud
control plane holds policy, inventory, workflow and assurance state. A fully
customer-hosted or edge enforcement option should be added only when a paying
customer's boundary requires it.

## Core bounded contexts

| Context | Production responsibility |
|---|---|
| Inventory | discovered/registered systems, owners, providers, purposes, risk and lifecycle |
| Passport | approved model/version, use, tools, region, data classes and review dates |
| Runtime control | deterministic destination/data/action decision and signed receipt |
| Execution orchestration | correlated source task, model result, action gate and final outcome |
| Monitoring | quality, drift, error, latency, usage, cost and outcome thresholds |
| Human oversight | named roles, separation of duties, approvals and escalation |
| Automation | idempotent, observable discovery, containment, review and evidence workflows |
| Incident | severity, ownership, automatic action, resolution and reconstruction |
| Assurance | append-only records, control tests, framework crosswalk and evidence export |

## Trust and security boundaries

- A governed agent cannot write or alter its own authoritative evidence.
- Identity distinguishes the AI system, service identity, human principal,
  approver and control owner.
- Decisions bind to immutable versions of the policy, model passport and proposed
  action; short-lived authorisation is non-replayable.
- Unknown models, versions, uses, destinations and actions fail closed.
- Restricted data does not leave the customer boundary. Confidential data reaches
  an external provider only through an approved, zero-retention route after
  required redaction.
- Secrets are blocked from every model destination.
- Raw prompts remain customer-side by default. Central evidence receives hashes,
  classifications, redaction counts and operational metadata.
- Approval binds to the exact proposal. Initiators cannot approve their own
  action, and material operations can require multiple distinct approvers.
- Tool adapters require the bound authorisation receipt and reconcile a single,
  idempotent execution outcome; replay does not create a second action.
- Monitoring thresholds do not silently rewrite policy; they activate pre-agreed
  containment and a human-owned validation workflow.
- Production evidence uses isolated append-only storage, restricted writers,
  signed receipts, retention policy, independent monitoring and tested recovery.

## Integration sequence for a design partner

1. Add authenticated, tenant-isolated APIs and durable stores.
2. Integrate enterprise identity and establish agent/workload identity.
3. Install a report-only connector at one approved model gateway.
4. Reconcile discovered use against the inventory and passports.
5. Enable metadata-only monitoring and validate thresholds with the model owner.
6. Turn on secret blocking, then approved confidential-data redaction.
7. Add human approval for one bounded consequential action.
8. Connect incident notifications and evidence export to the customer's existing
   ticketing, SIEM or GRC workflow.
9. Complete threat modelling, privacy/security assessment, resilience tests and
   rollback before enforcement expands.

Each enforcement step starts in report-only mode, is measured against customer-
approved test cases, and has an explicit rollback. Regulatory mappings remain
technical crosswalks rather than certification claims.
