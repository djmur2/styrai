# StyrAI structured regulation and policy design

**Design date:** 10 October 2026  
**Purpose:** implementation specification for upload-driven governance runs. This
is product design, not legal advice or a compliance certification.

## Executive decision

StyrAI should not calculate or display a generic **compliance percentage**. A
result such as `96% compliant` is both mathematically weak and legally
misleading: one failed prohibition or one missing critical safeguard cannot be
offset by many low-impact passes.

The minimum credible product is a hybrid system:

1. a versioned library of authoritative sources and exact provisions;
2. a separately versioned library of customer policies and approved clauses;
3. deterministic applicability and control tests over uploaded data;
4. an LLM used to extract **candidate** rules and explain grounded results; and
5. human approval for legal mappings, ambiguous applicability and every policy
rule before it can enforce anything.

Every run must pin the uploaded dataset hash, dataset schema, regulation-library
version, policy version, control-test version and evaluation-engine version. An
LLM-assisted ingestion must additionally pin the model, prompt template and
extracted source chunks.

## What is wrong with the present prototype

The current implementation is directionally useful but not yet credible as a
regulation and policy evaluation product:

- `Assessment.readiness_score` is calculated as passed controls divided by six
  controls. A system with one critical failure can therefore be presented as
  83% ready.
- The wider dashboard seeds arbitrary control `coverage` values such as 96, 92
  and 89 and averages them into `control_coverage`.
- Framework cards average those same values even though EU law, DORA, GDPR and
  NIST AI RMF have different scopes and legal force.
- Mappings are untyped strings. They do not record the exact paragraph, operator
  role, jurisdiction, effective date, applicability facts, source version,
  official URL, mapping rationale or legal reviewer.
- The evaluator conflates internal controls with legal requirements. For
  example, an internal model-version gate can be good evidence for risk
  management, but a version mismatch is not by itself proof of an EU AI Act
  Article 15 violation.
- DORA Article 11 concerns ICT response and recovery. A model-drift threshold
  should not be labelled a DORA Article 11 gap unless the facts establish an
  in-scope financial entity and an ICT-related operational-resilience impact.
- NIST AI RMF is a voluntary framework, not a regulation, and cannot be
  “violated” unless a company separately adopts an outcome as binding policy.
- The current global thresholds (`drift_score > 0.15`, for example) have no
  dataset definition, reference window, sample-size requirement, uncertainty or
  customer approval record.

The existing `legal_violation_confirmed: false` safeguard is correct and should
remain.

## Minimum authoritative library

The initial library should be intentionally bounded. It should contain the
following official, versioned sources and only the provisions needed by the two
demo rule packs.

| Source | Initial provisions | Treatment |
|---|---|---|
| EU AI Act, consolidated 27 July 2026 | Arts. 2, 3, 5, 6; Annex III; Arts. 9–15, 16–20, 25–27, 49, 50, 72, 73 and 113 | Regulation; role-, use-case- and date-dependent |
| GDPR | Arts. 4–6, 9, 13–14, 22, 25, 28, 30, 32–35 and 44–49 | Regulation; requires facts about personal data, controller/processor role, purpose, legal basis and transfers |
| DORA | Arts. 2–6, 8–13, 17–30 | Regulation for in-scope financial entities and ICT risk; never treat as a general AI-quality law |
| NIST AI RMF 1.0 | GOVERN 1.1, 1.3 and 1.6; MAP 1.1; MEASURE 1.1 and 1.2; MANAGE 1.1–1.3 | Voluntary framework; label as alignment or adopted internal policy, never legal compliance |

Current timing matters. Under Regulation (EU) 2026/1744, the Chapter III
high-risk rules for Annex III systems apply from **2 December 2027**, and those
for Annex I product systems apply from **2 August 2028**. Article 50 transparency
rules apply from 2 August 2026, subject to the provision's scope and transition
details. A run performed in October 2026 may therefore report an Annex III
**readiness finding**, but it must not report a present legal breach of a
future-dated Chapter III duty.

### Authoritative source records

```json
{
  "source_id": "eu-ai-act-2024-1689@2026-07-27",
  "source_type": "regulation",
  "jurisdictions": ["EU"],
  "official_title": "Regulation (EU) 2024/1689 laying down harmonised rules on artificial intelligence",
  "citation": "Regulation (EU) 2024/1689",
  "publisher": "European Union",
  "language": "en",
  "authoritative_url": "https://eur-lex.europa.eu/eli/reg/2024/1689/2026-07-27/eng",
  "consolidated_at": "2026-07-27",
  "retrieved_at": "2026-10-10T00:00:00Z",
  "content_sha256": "sha256-of-the-retained-source-snapshot",
  "legal_status": "in_force_progressive_application",
  "review_status": "pending_legal_validation",
  "supersedes_source_id": "eu-ai-act-2024-1689@2024-07-12"
}
```

Required `source_type` values are `regulation`, `regulatory_guidance`,
`voluntary_framework` and `internal_policy`. The UI must keep those categories
separate.

### Provision record

```json
{
  "provision_id": "eu-ai-act-2024-1689-art50-p1",
  "source_id": "eu-ai-act-2024-1689@2026-07-27",
  "locator": {"article": "50", "paragraph": "1", "point": null, "annex": null},
  "heading": "Transparency obligations for providers and deployers of certain AI systems",
  "authoritative_url": "https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50",
  "source_text_hash": "sha256-of-the-exact-paragraph",
  "source_excerpt": "Providers shall ensure that AI systems intended to interact directly with natural persons ...",
  "normalized_requirement": "A provider of an AI system intended to interact directly with natural persons must design it so those persons are informed they are interacting with AI, unless that is obvious in context.",
  "subject_roles": ["provider"],
  "applicable_from": "2026-08-02",
  "applicable_until": null,
  "applicability_expression": {
    "all": [
      {"fact": "operator_role", "op": "contains", "value": "provider"},
      {"fact": "direct_natural_person_interaction", "op": "eq", "value": true},
      {"fact": "evaluation_date", "op": "gte", "value": "2026-08-02"}
    ]
  },
  "exceptions_require_review": true,
  "evaluation_mode": "deterministic_control_plus_review",
  "legal_review": {"status": "pending", "reviewer": null, "reviewed_at": null}
}
```

Store an authoritative snapshot or canonical text hash, not just an LLM
summary. Display the exact article/paragraph, short source excerpt and official
link next to every result. Full-text search can operate over retained source
chunks, but the normalized requirement must never replace the source.

## Customer policy library

### Policy-document record

```json
{
  "policy_document_id": "northstar-customer-ai-policy@3.2",
  "source_type": "internal_policy",
  "title": "Customer Communications AI Policy",
  "issuer": "Northstar Bank",
  "owner": "Chief Customer Officer",
  "version": "3.2",
  "status": "approved",
  "effective_from": "2026-09-01",
  "effective_until": null,
  "source_filename": "customer-ai-policy-v3.2.pdf",
  "source_sha256": "sha256-of-uploaded-file",
  "classification": "confidential",
  "approved_by": "policy-owner-identifier",
  "approved_at": "2026-08-20T12:30:00Z",
  "ingested_at": "2026-10-10T09:00:00Z"
}
```

### Approved policy-clause record

```json
{
  "clause_id": "northstar-customer-ai-policy@3.2#section-7.4",
  "policy_document_id": "northstar-customer-ai-policy@3.2",
  "locator": {"page": 12, "section": "7.4", "heading": "Refund commitments"},
  "source_text": "Any AI-generated customer communication proposing a refund above EUR 500 must be approved by a Customer Operations Manager before release.",
  "source_text_hash": "sha256-of-exact-clause",
  "normalized_rule": {
    "all": [
      {"field": "content_origin", "op": "eq", "value": "ai_generated"},
      {"field": "communication_audience", "op": "eq", "value": "customer"},
      {"field": "refund_amount_eur", "op": "gt", "value": 500}
    ]
  },
  "effect": "manual_review",
  "severity": "high",
  "required_approver_role": "customer_operations_manager",
  "missing_fact_action": "manual_review",
  "exceptions": [],
  "precedence": 700,
  "extraction": {
    "method": "llm_assisted",
    "model": "record-exact-model-version",
    "prompt_template_version": "policy-extract-v1",
    "confidence": 0.94
  },
  "approval": {
    "status": "approved",
    "reviewer": "policy-owner-identifier",
    "reviewed_at": "2026-10-10T09:15:00Z"
  }
}
```

An uploaded policy follows `uploaded -> parsed -> draft clauses -> owner review
-> approved -> effective -> retired`. Draft clauses may be used in preview
mode, but may not enforce. The policy owner must see the exact quoted text and
location beside the normalized rule before approval.

## Control tests and legal mappings

Do not encode a legal provision directly as a metric threshold. Create a
versioned control test and a separately approved mapping from that test to a
provision.

```json
{
  "test_id": "ai-disclosure-present@1.0",
  "name": "AI interaction disclosure present",
  "scope": "row",
  "inputs": ["direct_natural_person_interaction", "ai_disclosure_shown"],
  "metric": {
    "definition": "For each direct AI interaction, whether a clear AI disclosure was presented before or at the start of interaction.",
    "expression": "ai_disclosure_shown == true"
  },
  "minimum_evidence": ["disclosure_event_id", "disclosure_timestamp"],
  "missing_data_action": "insufficient_evidence",
  "engine": "styrai-deterministic-rules@1.0",
  "mappings": [
    {
      "provision_id": "eu-ai-act-2024-1689-art50-p1",
      "relationship": "evidence_support",
      "rationale": "The event is evidence for the provider-side disclosure control; it does not establish compliance with the whole Article or Act.",
      "approved_by": "legal-reviewer-identifier",
      "approved_at": "2026-10-10T10:00:00Z"
    }
  ]
}
```

Allowed mapping relationships are:

- `direct_test` — a tightly scoped test of an explicit provision condition;
- `evidence_support` — supporting evidence, not proof of compliance;
- `potential_gap_signal` — a technical failure that may put a provision at
  risk;
- `readiness_mapping` — preparation for a future-dated or not-yet-applicable
  duty; and
- `crosswalk_only` — conceptual alignment, such as NIST AI RMF.

## Dataset and run records

### Dataset manifest

```json
{
  "dataset_id": "DS-2026-10-10-001",
  "filename": "customer_service_ai_cases.csv",
  "sha256": "sha256-of-uploaded-bytes",
  "schema_id": "styrai.customer-ai-events@1.0",
  "uploaded_at": "2026-10-10T10:10:00Z",
  "synthetic": true,
  "row_count": 12,
  "accepted_rows": 12,
  "rejected_rows": 0,
  "validation_errors": [],
  "data_classification": "synthetic",
  "retention_until": "2026-11-10T00:00:00Z"
}
```

### Run manifest

```json
{
  "run_id": "RUN-2026-10-10-001",
  "dataset_id": "DS-2026-10-10-001",
  "evaluation_date": "2026-10-10",
  "context_facts": {
    "jurisdictions": ["EU"],
    "operator_roles": ["provider", "deployer"],
    "sector": "financial_services",
    "direct_natural_person_interaction": true,
    "ai_act_classification": "limited_risk_transparency",
    "personal_data_processed": true
  },
  "library_versions": {
    "regulations": "reg-pack-eu-2026-07-27@1.0",
    "internal_policy": "northstar-customer-ai-policy@3.2",
    "control_tests": "customer-communications-controls@1.0",
    "evaluation_engine": "styrai-deterministic-rules@1.0"
  },
  "mode": "assessment",
  "started_by": "demo-user",
  "started_at": "2026-10-10T10:12:00Z"
}
```

### Rule-result record

```json
{
  "rule_result_id": "RES-001",
  "run_id": "RUN-2026-10-10-001",
  "scope": {"type": "row", "record_id": "CASE-006"},
  "source_type": "internal_policy",
  "source_ref": "northstar-customer-ai-policy@3.2#section-7.4",
  "applicability": {
    "status": "applicable",
    "basis": ["ai_generated", "customer_facing", "refund_amount_eur=750"],
    "unresolved_facts": []
  },
  "test": {
    "status": "manual_review",
    "observed": {"refund_amount_eur": 750, "approval_present": false},
    "expected": {"approval_role": "customer_operations_manager"},
    "evidence_refs": ["dataset:CASE-006"]
  },
  "classification": "internal_policy_review_required",
  "enforcement_action": "hold_for_review",
  "reason": "The amount exceeds the approved internal threshold and no manager approval is present.",
  "citation": {
    "label": "Customer Communications AI Policy v3.2, section 7.4",
    "source_text_hash": "sha256-of-exact-clause"
  },
  "legal_violation_confirmed": false
}
```

## Outcome vocabulary

Applicability and test outcome are different dimensions and must not be merged.

### Applicability

- `applicable`
- `not_applicable`
- `future_readiness`
- `undetermined`

### Evidence status

- `sufficient`
- `missing`
- `stale`
- `conflicting`

### Regulation control-test outcome

- `control_pass` — this one scoped test passed;
- `potential_gap` — technical evidence suggests a possible obligation gap;
- `insufficient_evidence`;
- `not_evaluated`; and
- `not_applicable`.

Never label these `legally compliant`, `violation confirmed` or `certified`.
Only a competent authority or qualified human process can make a legal finding.

### Internal-policy outcome

- `policy_pass`
- `manual_review`
- `policy_block`
- `policy_exception_required`
- `not_evaluated`
- `not_applicable`

### Advisory-framework outcome

- `aligned`
- `partially_implemented`
- `not_implemented`
- `not_evaluated`

NIST AI RMF must appear only in this advisory or internally adopted layer.

## Metrics that replace “96% compliant”

Display counts first. Percentages are acceptable only for clearly defined
operational rates, never as an overall legal score.

| Metric | Exact definition | Required display context |
|---|---|---|
| Applicable legal provisions | Count of provisions whose deterministic applicability facts resolved to `applicable` at the run date | Jurisdiction, role, date and rule-pack version |
| Future-readiness provisions | Count whose conditions fit but whose application date is in the future | Application date shown |
| Scoped control tests passed | Applicable legal control tests with sufficient evidence and `control_pass` | `x of y tested`; never “x% compliant” |
| Potential regulatory gaps | Applicable tests returning `potential_gap` | Exact provision and observation; legal review required |
| Insufficient evidence | Applicable tests missing, stale or conflicting required evidence | Missing fields/evidence listed |
| Internal review required | Applicable internal clauses returning `manual_review` | Clause text, owner and next action |
| Internal blocks | Applicable internal clauses returning `policy_block` | Clause and enforcement evidence |
| Rows evaluated | Valid rows reaching evaluation | Uploaded, accepted, rejected and skipped counts |
| Flag incidence | Flagged valid rows / evaluated valid rows | Numerator, denominator, time window and rule ID |
| Control test execution rate | Tests executed / tests scheduled | Operational assurance only; not legal compliance |

A headline should read, for example:

> 8 applicable legal control tests: 7 passed, 1 insufficient evidence. 3 internal
> policy rules: 2 passed, 1 requires review. Final decision: manual review.

It should not read `88% compliant`.

### Model-monitoring metric definitions

Metrics must be named precisely and thresholds must be customer-approved. They
are not regulatory thresholds unless an authoritative source explicitly says
so.

- **Population Stability Index (PSI):** for fixed score bins, sum
  `(current_share - reference_share) * ln(current_share / reference_share)`.
  Record bin edges, reference period, current period, smoothing rule, sample
  sizes and the policy threshold. The demo may use `0.15`, but must label it
  `Internal policy MON-001`, not an EU requirement.
- **Error rate:** incorrect predictions divided by labelled predictions. Show
  the outcome-labelling window and labelled-row coverage.
- **False-negative rate:** `FN / (TP + FN)`, reported per approved comparison
  group with sample sizes. A between-group gap is a monitoring signal, not a
  legal discrimination finding.
- **Brier score:** mean squared difference between predicted probability and
  binary outcome. Show cohort, window and sample size.
- **Human-review completion:** cases requiring review with a valid approval
  event divided by cases requiring review. An approval button alone is not
  proof that review was meaningful.
- **Data quality:** accepted, rejected, duplicate, missing-field and
  out-of-range row counts. Rejected rows never disappear from the denominator
  silently.

If a minimum sample size is not met, return `insufficient_evidence`; do not
convert statistical uncertainty into a pass.

## Rule precedence and decision aggregation

1. Determine source version and effective date.
2. Determine applicability from explicit facts. Missing or conflicting facts
   produce `undetermined` and route to review.
3. Run each applicable rule independently and retain its result.
4. An applicable legal prohibition or mandatory duty cannot be relaxed by an
   internal policy, waiver, NIST mapping or LLM suggestion.
5. An internal policy may be stricter than law and may elevate `allow` to
   `allow_with_controls`, `manual_review` or `block`.
6. An internal exception can relax only the internal rule that authorises the
   exception. It must be approved, scoped, time-limited and cannot override law.
7. A NIST outcome has no enforcement effect unless the company expressly adopts
   it in an approved internal policy.
8. Within one internal-policy hierarchy, a specific system/use-case clause may
   override a general clause only when the policy owner approved that
   relationship. Otherwise choose the stricter action and flag the conflict.
9. Do not attempt to automate doctrines such as lex specialis or resolve
   conflicting law. Route conflicts to legal review.

The final operational action uses the strongest applicable approved action:

`block > manual_review > allow_with_controls > allow`

This action precedence does **not** rank legal importance. The UI must retain
the separate result from every legal provision and internal clause.

## Scenario 1 — regulation control passes; policy requires review

### Dataset: `customer_service_ai_cases.csv`

An in-house customer-support assistant interacts directly with EU customers.
The company is configured as the provider and deployer. All rows show the AI
disclosure required by the configured Article 50(1) control. One row proposes a
refund above the company's stricter EUR 500 threshold.

Columns:

```text
case_id,event_time,system_id,model_version,direct_natural_person_interaction,
ai_disclosure_shown,disclosure_event_id,content_origin,communication_audience,
refund_amount_eur,customer_vulnerability_flag,human_review_required,
manager_approval_event_id,release_status
```

Representative row:

```csv
CASE-006,2026-10-08T09:14:00Z,customer-assistant,4.2,true,true,DISC-006,ai_generated,customer,750,false,true,,draft
```

Uploaded written policy:

> Any AI-generated customer communication proposing a refund above EUR 500
> must be approved by a Customer Operations Manager before release.

Expected result for `CASE-006`:

- EU AI Act Article 50(1) disclosure control: `control_pass`;
- internal policy section 7.4: `manual_review`;
- final action: `manual_review` / hold release;
- explanation: regulation test passed, but internal policy is stricter;
- legal violation confirmed: `false`.

This is the clearest demonstration of why regulation and internal policy must be
separate layers.

## Scenario 2 — uploaded model telemetry triggers containment

### Dataset: `credit_model_monitoring.csv`

The dataset contains synthetic baseline and current-period predictions for a
credit-risk decision-support model. It supports real calculations rather than
pre-populated cards.

Columns:

```text
record_id,period,decision_time,model_id,model_version,score_band,
predicted_default_probability,actual_default,recommended_decision,
human_reviewed,final_decision,comparison_group
```

Minimum credible demo volume: 1,000 baseline rows and 1,000 current rows, with
fixed score bins and at least 100 labelled current rows per displayed comparison
group. The run calculates PSI, labelled-outcome coverage, error rate, Brier
score, false-negative rate by group and human-review completion.

Expected synthetic outcome:

- score PSI: `0.22`, above customer policy `MON-001` threshold `0.15`;
- human-review completion: `100%` for cases requiring review;
- model version: exact passport match;
- internal policy: confirmed `policy_block` or `manual_review` according to the
  approved containment rule;
- EU AI Act Articles 9, 15, 26 and 72: `future_readiness` mappings until the
  applicable Annex III date and only after the operator role/classification are
  confirmed;
- GDPR Article 22: applicability review based on whether final decisions are
  solely automated and legally or similarly significant; the dataset alone must
  not claim compliance;
- DORA: no drift finding unless an in-scope financial entity and an ICT
  operational-resilience impact are established;
- legal violation confirmed: `false`.

The run should guard the model, route eligible traffic to the approved fallback,
open an owner task and preserve the calculation inputs and code version.

## Role of an LLM

Yes, an LLM is useful in the background, but it should assist the governance
engine rather than be the governance engine.

### Appropriate LLM tasks

- extract candidate clauses from a PDF, DOCX or pasted policy while preserving
  exact page/section locators;
- identify actors, conditions, thresholds, exceptions, dates, required evidence
  and proposed actions;
- retrieve potentially relevant provisions from the approved source library;
- propose a crosswalk and explain why it may be relevant;
- generate a plain-language explanation grounded only in the rule results and
  cited source chunks; and
- identify ambiguity or missing facts for a human reviewer.

### Tasks that remain deterministic or human-owned

- dataset validation and metric calculations;
- execution of approved policy expressions;
- source version and effective-date checks;
- final legal applicability and legal conclusions;
- activation or modification of an enforcement rule;
- approval of policy exceptions; and
- consequential block/release decisions where customer policy requires a human.

### LLM guardrails

- Treat every uploaded document as untrusted data. Ignore instructions embedded
  in the document and defend against prompt injection.
- Use retrieval only from approved, versioned source chunks and require a valid
  source locator for every extracted claim.
- Validate LLM output against a strict schema and an allow-listed policy DSL; no
  generated code or free-form condition may execute.
- A confidence score never converts a draft clause into an active rule. Low
  confidence, conflicts, exceptions or missing facts route to human review.
- Pin and record model/provider, exact model version, prompt-template version,
  chunk IDs, output hash and reviewer action.
- Do not send confidential policies or uploaded datasets to an external model
  unless the customer has approved that provider, region, retention and data
  class. Prefer customer-hosted/private inference for policy extraction.
- Do not retain raw regulated data centrally by default. Store hashes,
  calculated features and approved evidence references.
- An LLM explanation cannot change the deterministic result or final action.
- Regulation updates create a draft mapping-review task. They never silently
  change live enforcement.

The first implementation can use retrieval-augmented generation; it does not
need model fine-tuning. The commercial moat is the reviewed rule/evidence graph,
workflow and integrations—not merely calling an LLM over PDFs.

## Legal-overclaim guardrails

- Say `control test passed`, not `compliant with Article X`.
- Say `potential regulatory gap`, not `violation`, unless a qualified reviewer
  records that determination through a separately governed workflow.
- Say `future readiness` for AI Act Chapter III obligations before their
  applicable date.
- Show `not applicable` separately from `pass`.
- Show `insufficient evidence` separately from `fail`.
- Never infer AI Act high-risk status from the industry label alone. Classification
  depends on use case, role, Annex I/III conditions and exceptions.
- Do not infer GDPR Article 22 merely because an AI score exists. Determine
  whether a decision is solely automated and produces legal or similarly
  significant effects, then consider exceptions and safeguards.
- Do not map ordinary model drift directly to DORA. Confirm entity scope, ICT
  risk and operational impact.
- Never call NIST AI RMF a regulation or a source of legal violations.
- Preserve the existing disclaimer that StyrAI is not legal advice or a
  certification.

## Acceptance criteria for the next prototype

1. A user uploads a CSV and sees schema validation before the run starts.
2. Every statistic is calculated from that CSV, with numerator, denominator,
   window and definition visible.
3. A user uploads or pastes a written internal policy.
4. The system presents candidate clauses with exact quotations and locators.
5. The user explicitly approves a clause before it becomes executable.
6. A run displays regulation, internal policy and advisory-framework results in
   separate sections.
7. Each regulation result cites source, article/paragraph, official link,
   applicable date, rule version, observation and evidence.
8. The customer-service scenario produces `Article 50(1) control passed` and
   `Internal policy manual review required` for the same row.
9. The finance dataset calculates PSI and other metrics from uploaded rows and
   never uses seeded statistics.
10. No screen displays an overall compliance percentage.
11. Every run can be reconstructed from hashes and pinned versions.
12. Tests prove that document text cannot inject executable instructions and
    that a policy exception cannot override a legal prohibition.

## Audit notes on `dataset_governance.py` as reviewed 10 October 2026

The new upload runner is a useful deterministic demonstration and correctly
avoids an overall percentage, requires explicit policy activation, retains
source hashes and keeps `legal_violation_confirmed` false. Before it is treated
as a credible regulatory evaluator, the following issues need correction:

- AI Act Articles 13 and 14 are marked as staged readiness sources but their row
  results are still emitted as legal `pass` or `fail`. Emit `future_readiness`
  outcomes and keep them out of current-law pass counts until the applicable
  date and classification/role facts are established.
- A user-supplied `risk_class=high_impact` flag is not a legal high-risk
  classification. It should open a classification review rather than directly
  activating Chapter III legal tests.
- `explanation_present` is not a direct Article 13 test. Article 13 concerns the
  provider's transparency and instructions to deployers. Treat a row-level
  explanation indicator as supporting evidence only.
- Article 14 is primarily a provider-side design requirement. For a corporate
  deployer, Article 26(2) is the more direct oversight reference, subject to the
  staged application date and role/classification facts.
- A solely automated, significant decision does not satisfy GDPR Article 22
  merely because human-intervention and contestability flags are true. The
  engine must first establish an Article 22(2) exception/legal basis and then
  test the applicable safeguards.
- `contains_personal_data=true` plus `data_minimized=true` is a self-attestation,
  not a sufficient Article 5(1)(c) test. Purpose, necessity and field-level
  evidence are required.
- A row with all legal rules `not_applicable` and no active policy currently
  receives an overall `pass`; it should be `no_applicable_rules` or
  `not_evaluated`.
- The reported `tested` count includes `not_applicable` evaluations.
- `insufficient_evidence` currently outranks a confirmed internal
  `manual_review` in the row disposition. Evidence status and operational action
  should be separate dimensions so the stronger approved action remains review.
- The runner counts uploaded rows but does not yet calculate PSI, error rate,
  calibration, group metrics or outcome coverage from model telemetry. Those
  calculations are necessary to satisfy the request for data-derived model
  statistics.
- Dataset validation should reject duplicate record IDs and non-finite numbers
  such as `NaN` and infinity.
- Policy activation approves every regex-extracted rule together. Clause-level
  locators, hashes and approvals are safer, and tests should cover negation such
  as “does not require manual review.”

## Official primary sources used

- [EU AI Act consolidated text as at 27 July 2026](https://eur-lex.europa.eu/eli/reg/2024/1689/2026-07-27/eng)
- [Regulation (EU) 2026/1744 — Digital Omnibus on AI](https://eur-lex.europa.eu/eli/reg/2026/1744/oj/eng)
- [European Commission AI Act implementation timeline](https://ai-act-service-desk.ec.europa.eu/en/ai-act/eu-ai-act-implementation-timeline)
- [EU AI Act Article 9](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-9)
- [EU AI Act Article 14](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-14)
- [EU AI Act Article 15](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-15)
- [EU AI Act Article 26](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-26)
- [EU AI Act Article 50](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50)
- [EU AI Act Article 72](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-72)
- [GDPR — Regulation (EU) 2016/679](https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng)
- [DORA — Regulation (EU) 2022/2554](https://eur-lex.europa.eu/eli/reg/2022/2554/oj/eng)
- [NIST AI RMF 1.0](https://doi.org/10.6028/NIST.AI.100-1)
- [NIST AI RMF Core and current revision notice](https://airc.nist.gov/airmf-resources/airmf/5-sec-core/)
