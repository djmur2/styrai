# StyrAI

**Opening the partner package? Start with `START_HERE.md` for one-click macOS
and Windows launch instructions, Linux commands, the three-minute demo and
troubleshooting.**

StyrAI is a working prototype of an enterprise AI-governance control
plane. It demonstrates two controls that organisations need once AI is in real
use:

1. continuous oversight of deployed models against their approved purpose,
   version, operating limits and policy obligations; and
2. runtime enforcement over employee and application use of AI, including
   stopping sensitive information before it reaches an external model.

The prototype combines an AI-system inventory, model passports, policy and
obligation assessments, production-monitoring signals, an outbound AI-use
gateway, automated containment, findings, incidents and reconstructable
evidence in one interface.

## Start the working demonstration

Requirements: Python 3.11 or newer. There are no third-party dependencies.

### Recommended: double-click on a Mac

1. Open this folder in Finder.
2. Double-click **Start StyrAI Demo.command**.
3. Keep the Terminal window open while presenting.

The launcher checks Python and ports `8765` through `8775`, then opens the
current demonstration on the first available local address. It reuses a server
only after verifying the StyrAI health response, the AI-governance API and the
versioned CSV/JSON upload contract; an older process occupying `8765` is
ignored. The Terminal window prints the exact address it selected. macOS may
ask you to confirm that you want to open the launcher the first time.

### Terminal fallback

Open Terminal in this folder and run:

```bash
python3 -m murphyos.web --open-browser
```

If the browser does not open, copy the local presenter address printed in the
Terminal window. With no other local process running, it will normally be
`http://127.0.0.1:8765/?presentation=1`.

The internal Python package retains the original `murphyos` development name.
The product, interface, evidence schemas and documentation use **StyrAI**.

### Optional authentication for hosted synthetic staging

Local launch remains unchanged and does not require a login. For a shared
staging deployment, set `STYRAI_AUTH_USERS_JSON` to a JSON object mapping each
founder's distinct username to a salted PBKDF2-SHA256 password hash. Generate a
hash interactively with the standard-library helper:

```bash
python3 -m murphyos.auth
```

The helper reads the password without echo and prints only the encoded hash.
Store the resulting JSON value in the hosting platform's secret store; never
commit it or plaintext passwords to this repository. Also configure a separate
high-entropy `STYRAI_SESSION_SECRET` of at least 32 bytes. When authentication is
enabled, `GET /api/health` remains public and browser users sign in through the
StyrAI form. The application issues a signed Secure, HttpOnly, SameSite=Strict
session cookie and fails closed if the signing secret is absent. Expose that
mode only behind HTTPS. Browser mutation requests also carry a StyrAI-specific
request marker, and identity-bearing actor and approval fields are attributed
to the authenticated username.

Restarting the application continues the existing audit chain. An explicit demo
reset rotates a non-empty audit file beside the current file before creating a
fresh chain, so the hosting filesystem or mounted volume must itself be durable
for those records to survive container replacement.

The shared staging architecture, collaborator access model, automatic-deploy
workflow, cost boundary and operating runbook are in
[`docs/HOSTED_STAGING.md`](docs/HOSTED_STAGING.md). A collaborator who only
uses the demonstration needs the HTTPS link and a StyrAI login; GitHub access is
needed only to contribute or review source-code changes.

## The primary demonstration: upload-driven governance

The first screen is **AI Control Room**. Its primary workbench starts empty:
there is no pre-populated compliance score and nothing is counted until the
presenter supplies synthetic evidence. The included upload pack makes the full
flow executable:

1. upload `samples/synthetic-credit-decisions.csv`;
2. inspect the detected fields, parsed-record count and row preview;
3. upload `samples/stricter-company-ai-policy.md`;
4. review the housed regulation library, including the exact provision, source
   version, applicability note and control proxy; and
5. select **Run governance assessment**, review the extracted rules in the
   confirmation dialog, and approve them for the user-initiated run before
   evaluating every uploaded row.

The result keeps three different authorities separate:

- **Regulatory screen** — deterministic control proxies cross-referenced to
  exact provisions. A pass means only that no gap was detected by the
  applicable rules tested; it is not a legal opinion or certification.
- **Internal policy** — the uploaded company requirements, which can be more
  conservative than current regulation and can require review even when the
  regulatory screen passes.
- **Advisory framework mapping** — guidance such as NIST AI RMF, shown for
  operating context and never counted as law or internal-policy compliance.

In the included finance sample, record `FIN-1002` carries the evidence needed
to pass the applicable regulatory control proxies, but its confidence is below
the company policy's 80% threshold and no manual review is recorded. StyrAI
therefore displays **regulatory pass + internal manual review**, cites the
uploaded clause and identifies the required action.

### What the counts mean

StyrAI does not use an overall “96% compliant” score. It reports explicit
numerators and denominators:

- records evaluated out of records uploaded;
- applicable regulatory controls tested, passed, potential gaps, insufficient
  evidence and not-applicable controls;
- internal-policy control checks passed, failed/blocked, routed to manual
  review or not applicable; and
- row-level findings, which can exceed the record count because one record may
  trigger more than one rule.

Missing evidence is never silently counted as a pass. The results remain split
by authority so a strong result in one layer cannot offset a failure or review
requirement in another.

### Written-policy interpretation and the role of an LLM

The current prototype deliberately makes no external model call. It uses
deterministic pattern matching to convert supported written clauses into a
machine-readable **draft**. After the operator selects **Run governance
assessment**, a confirmation dialog shows the extracted rules; approving that
dialog is the explicit human activation for the demonstration.
The activated rules are then evaluated deterministically, with the uploaded
clause preserved as the citation. Unsupported or ambiguous language is left
for human review rather than silently enforced.

In production, an LLM can improve policy ingestion by proposing clauses,
conditions, fields and citations from unstructured text. Those proposals should
remain drafts until a policy owner approves the source, interpretation,
applicability and effective date. The runtime decision should execute approved,
versioned rules; the LLM should assist drafting and evidence extraction, not act
as the compliance judge.

## Secondary executable control tests

Below the upload workbench, AI Control Room retains three quick control tests:

1. **Stop a data leak** — a fictional employee attempts to paste customer data
   and a credential into an unapproved public AI service. StyrAI classifies the
   input, rejects the destination, prevents transmission, opens the governance
   response and records metadata-only evidence.
2. **Contain model drift** — a production credit-risk model crosses its approved
   population-drift threshold. StyrAI records the internal policy breach, moves
   the model into a guarded state, routes write-capable calls to a fallback,
   opens validation work and links the incident to evidence.
3. **Flag control gaps** — a deployed healthcare summarisation model reports an
   unreviewed version. StyrAI detects the passport mismatch, performs a control
   assessment, identifies policy gaps and maps the regulatory obligations that
   may be at risk. It does **not** claim that a legal violation has been proven.

Each quick test shows the same three-part operating model:

`synthetic event → control evaluation → enforcement outcome`

The **Correlated evidence** panel then shows the event, finding, incident,
assessment, policy and audit references created by that control test.

See `docs/DEMO_SCRIPT.md` for the exact upload walkthrough, count definitions,
architecture explanation and quick-test narration.

## Suggested seven-minute demonstration

Start by selecting **Reset demo** so the estate is at its deterministic
baseline.

1. In **Upload-driven governance run**, upload
   `samples/synthetic-credit-decisions.csv`. Confirm the detected row count and
   fields before any result is shown.
2. Upload `samples/stricter-company-ai-policy.md`. Review its 80% finance
   threshold, then point out the exact provisions and applicability notes in
   the regulation library.
3. Select **Run governance assessment**, review the extracted-rule confirmation
   and approve it. Explain that this deliberate operator decision activates the
   supported policy draft; there is no background or autonomous activation.
4. Show the separate regulatory and internal-policy counts. Open the
   `FIN-1002` finding and call out the regulatory pass, internal manual-review
   decision, uploaded clause, observed evidence and required action.
5. Keep **Stop a data leak** selected. Point out the fictional prompt, the
   external destination and the intentionally understated `Internal`
   classification. Select **Intercept outbound AI request**.
6. Show **BLOCKED BEFORE PROVIDER**, then call out **External model invoked: No**,
   **Raw prompt stored: No**, the detected sensitive patterns and the linked
   incident and evidence identifiers.
7. Select **Contain model drift**, review the healthy model passport, then select
   **Inject and contain drift**. Show the drift movement from `0.06` to `0.27`
   against the `0.15` limit, the guarded production state and the fallback
   response.
8. State the distinction shown by the product: this is a confirmed internal
   policy breach and an obligation may be at risk; it is not an automated legal
   conclusion.
9. Select **Flag control gaps**, compare the healthcare model's approved and
   observed versions, then select **Assess deployed AI system**.
10. Show the unreviewed version, high-priority findings, named owner, mapped
   obligations and **Legal violation confirmed: No**.
11. Use **AI systems**, **Model assurance**, **Policies & obligations** and
   **Findings & response** to show how the same events update the wider control
   plane. Finish with **Generate evidence pack**.

## What is functional and what is simulated

| Functional in this prototype | Simulated for demonstration | Required for a production pilot |
| --- | --- | --- |
| CSV/JSON parsing, schema preview and row-level rule evaluation | Synthetic finance and healthcare records | Customer-approved schemas and governed data connectors |
| Written-policy draft extraction and explicit user activation | Included fictional company policy | Policy-owner workflow, versioning and approval records |
| Versioned regulatory references and separate result layers | Demonstration control proxies and applicability mappings | Counsel-validated regulatory content and change management |
| Policy and passport evaluation | Model-provider inference | Enterprise identity and access integration |
| Sensitive-pattern detection | Employee and system identities | Real AI gateway, browser or API interception |
| Allow, redact, route and block decisions | Provider and network connections | Customer-approved classification and policy rules |
| Model metric and version evaluation | Monitoring telemetry feeds | Production model/observability connectors |
| Automated containment state | Fallback model invocation | Enforced routing and kill-switch integration |
| Findings, incidents and ownership | Notifications and ticket delivery | SIEM, GRC and case-management integration |
| Hash-chained evidence records | Regulatory applicability examples | Legal/compliance validation by jurisdiction |

All names, prompts, customers, patients, employees, models and events used in
the demo are fictional. Use synthetic data only in both local and shared staging
environments. The application does not contact a model provider, bank, EHR or
enterprise system.

StyrAI demonstrates operational controls and evidence. It does not provide
legal advice, determine regulatory applicability or certify compliance.

## Other product views

- **Portfolio overview** — AI estate, governed runtime activity, open findings
  and explicit control operating-status counts.
- **AI systems** — models, agents, providers, owners, intended uses, risk and
  deployment status.
- **Model assurance** — quality, drift, errors, latency and model-version
  controls.
- **AI use gateway** — an interactive outbound-input policy simulator with
  allow, redact and block decisions.
- **Policies & obligations** — technical controls mapped to EU AI Act, GDPR,
  DORA, ISO/IEC 42001 and NIST AI RMF examples.
- **Automations** — shadow-AI discovery, data-loss prevention, drift response,
  version gating, passport review and evidence generation.
- **Findings & response** — governance incidents, automated containment,
  ownership and evidence packs.

The earlier payment-release and clinical-write pipelines remain in the codebase
as secondary demonstrations of governed agent actions and regression coverage.
They are not the primary product story: StyrAI's primary demonstration is the AI
Control Room and its controls over deployed models and enterprise AI use.

Use fictional data only in all simulator fields.

## Run the tests

```bash
python3 -m unittest discover -s tests -v
```

The test suite covers the AI-governance control plane, including inventory and
assessment state, sensitive-data interception, destination checks, block and
redaction decisions, drift containment, model-version mismatches, findings,
incidents, evidence sanitisation and reset behaviour. It also retains regression
coverage for the secondary governed-action workflows.

## Project map

- `murphyos/ai_governance.py` — deployed-model inventory, control assessments,
  runtime AI-use inspection, monitoring, version controls, findings, incidents
  and evidence.
- `murphyos/dataset_governance.py` — synthetic CSV/JSON parsing, regulation
  library, written-policy drafts, activation, deterministic row evaluation and
  upload-run evidence.
- `murphyos/platform.py` — wider command-centre inventory, monitoring, DLP,
  automations, incidents and assurance packs.
- `murphyos/web.py` and `web/` — local API and non-technical StyrAI interface.
- `murphyos/audit.py` — append-only, hash-chained governance evidence.
- `murphyos/registry.py`, `policy.py` and `models.py` — model passports, policy
  evaluation and governed-action foundations.
- `murphyos/industry_pipelines.py` and `execution.py` — secondary finance and
  healthcare action-control demonstrations.
- `tests/test_ai_governance.py` — AI-control-plane acceptance coverage.
- `tests/test_dataset_governance.py` — upload, policy-draft, activation,
  regulation-reference, count-semantics and row-level result coverage.
- `tests/test_vertical_slice.py` and `tests/test_industry_pipelines.py` — wider
  platform and governed-action regression coverage.
- `docs/ARCHITECTURE.md` — system boundaries and target production architecture.
- `docs/DEMO_SCRIPT.md` — exact AI Control Room presenter flow.
- `docs/PRODUCT_BRIEF.md` — target buyer, positioning and product limits.
- `docs/PILOT_OFFER.md` — initial paid-pilot proposition.
- `docs/VALIDATION_PLAN.md` — market validation and stop/go gates.
- `docs/FINANCIAL_SERVICES_STRATEGY.md` — financial-services entry strategy.
- `docs/REGULATORY_WATCH.md` — official signals and product implications.
- `docs/PRODUCT_ROADMAP.md` — path from prototype to paid pilot.
- `samples/` — executable synthetic finance and healthcare datasets plus the
  stricter written company policy used in the upload demonstration.

## What remains before production

The prototype uses seeded in-memory state and a hash-chained audit file. A
production pilot still requires tenant isolation, enterprise authentication and
role-based authorisation, durable append-only storage, signed receipts,
customer-approved policies, a real AI gateway or telemetry connector, safe
customer-side sensitive-data handling, security and privacy review, legal
validation and tested operational resilience.
