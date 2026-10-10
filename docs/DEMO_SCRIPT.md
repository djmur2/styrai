# StyrAI AI Governance Control Room Demo

## The story to tell

StyrAI is a control plane for AI already operating inside an enterprise. It
maintains the deployed-model estate, evaluates models against approved operating
boundaries, inspects AI traffic before it crosses a trust boundary, applies
corporate policy and preserves the evidence of every intervention.

The primary demonstration proves four distinct capabilities:

1. running uploaded synthetic evidence through separately governed regulatory
   and company-policy layers, with exact citations and defensible counts;
2. stopping sensitive data before an external AI provider is invoked;
3. containing a deployed financial-services model when it leaves its approved
   operating envelope; and
4. detecting a healthcare model-version and assurance gap, then mapping the
   policies and regulatory obligations that may be affected.

This is not a payment-approval demonstration. Payment and clinical write-back
workflows remain secondary examples of agent-action controls.

## Before the audience arrives

1. Double-click **Start StyrAI Demo.command** and keep its Terminal window open.
2. Confirm the browser opens at the local presenter address printed in the
   Terminal window. The launcher checks ports `8765` through `8775`, verifies
   that any reusable process exposes the current governance API, and skips
   stale builds.
3. Confirm the page heading is **AI Control Room**.
4. Select **Reset demo** in the top-right corner.
5. Confirm the **Upload-driven governance run** workbench appears above the
   quick-control tests.
6. Confirm the three quick-control cards appear:
   - **Stop a data leak**
   - **Contain model drift**
   - **Flag control gaps**

If the launcher does not open the browser, copy its printed address into the
browser manually. If a previous run is visible, select **Reset** inside the
scenario panel or **Reset demo** in the top bar before presenting.

## Opening narration

> StyrAI governs two things most companies cannot yet see in one place: the
> models running in production, and the information employees and applications
> send to AI. This demonstration is local and synthetic, but the policy,
> enforcement, monitoring, incident and evidence logic is executing now.

Point first to the empty upload workbench and say:

> There is no pre-populated compliance score. We will provide the evidence,
> inspect what was parsed, select the authorities to test and then create a
> persistent, row-level run result.

Then point briefly to the four wider estate facts:

- **AI systems discovered**
- **Production monitoring** (monitored systems / deployed systems)
- **Sensitive calls stopped**
- **Raw prompts retained: 0**

Then explain the visual sequence used by every scenario:

`What StyrAI observes → What StyrAI checks → What StyrAI does`

## Primary scenario — upload evidence and apply a stricter company policy

### Set up the story

The included finance dataset represents six fictional AI-assisted credit
outcomes. The included company policy imposes a manual-review threshold that is
more conservative than the regulatory control proxies used in the prototype.

Say:

> Regulation and company policy are not one blended score. StyrAI will evaluate
> each authority separately, preserve the source it used and apply the stricter
> operational disposition when the two layers differ.

### Step 1 — upload the synthetic dataset

In **Upload synthetic CSV or JSON**, choose:

`samples/synthetic-credit-decisions.csv`

Confirm the workbench displays:

- the exact filename;
- the number of parsed records and detected fields;
- schema chips for the supplied columns; and
- a preview of the uploaded rows.

Point out that the results panel is still absent. The preview is evidence about
what StyrAI received; it is not a pre-calculated result.

### Step 2 — upload the written company policy

Select **Upload .txt or .md** and choose:

`samples/stricter-company-ai-policy.md`

Read the finance clause aloud:

> AI-assisted credit decisions with confidence below 80% require manual review
> before communication.

The policy is synthetic. Its purpose is to demonstrate a requirement that can
be more conservative than the current regulatory screen.

### Step 3 — review the authorities before execution

In **Regulation library**, point out that each housed source displays:

- its exact article or provision;
- the source version;
- an applicability or readiness date;
- the operational control proxy it informs; and
- a link to the official source.

State explicitly:

> A source citation does not prove that a law applies to this company, system or
> record. StyrAI surfaces a control proxy and the evidence needed for qualified
> legal or compliance review; it does not make the legal conclusion.

Contrast those cards with the uploaded **Company** source. The two authorities
will produce separate results.

### Step 4 — make the human activation decision and run

Select **Run governance assessment**, read the extracted rule in the confirmation
dialog and select **OK** to activate it for this run.

In this local prototype, the confirmation is the explicit human activation
step. The system uses deterministic pattern matching to create a draft only for
supported clause shapes, shows the proposed rule and the number of unparsed
clauses, then activates only after approval. There is no background activation
and no external LLM call.

Say:

> Written policy is never silently converted into an enforcement rule. A human
> chooses the source and initiates activation. Unsupported or ambiguous text
> remains visible for human review instead of being guessed into policy.

### Step 5 — explain the counts

When the result appears, call out the count cards before discussing any one
finding:

- **Records evaluated** is records processed out of records uploaded.
- **Regulatory controls** separate tested/applicable, pass, potential gap,
  insufficient evidence and not applicable.
- **Internal policy** separates pass, fail/block, manual review and not
  evaluated.
- **Row-level findings** may exceed the number of records because one record can
  trigger more than one rule.

Say:

> StyrAI does not report “96% compliant.” Every number has a named population
> and denominator. Missing evidence is insufficient evidence, not a pass, and a
> strong result in one authority cannot cancel a review requirement in another.

The regulatory label **Pass** means only that the applicable deterministic
control proxies tested for that row did not detect a gap. It does not mean the
organisation or system is legally compliant.

### Step 6 — show regulation pass plus internal manual review

In **Row-level findings and exact references**, locate record `FIN-1002`.

Call out:

- regulatory screen: pass for the applicable proxies tested;
- internal policy: manual review required;
- observed confidence: below the uploaded 80% company threshold;
- completed manual review: not evidenced;
- exact citation: the uploaded company-policy clause; and
- required action: route the record to manual review before communication.

Say:

> This is the key governance case. The system does not manufacture a legal
> failure simply because management chose a stricter rule. It preserves the
> regulatory pass, records the internal-policy exception and applies the
> stricter operational disposition: manual review.

### Proof statement

> The statistics now come from the uploaded rows, not seeded dashboard values.
> Each result is traceable to a record, an approved rule version, an exact source
> and the evidence that caused the disposition.

### What is real versus simulated

- Functional: CSV/JSON parsing, schema preview, deterministic control
  evaluation, policy-draft extraction, user-initiated activation, separate
  authority layers, exact citations, counts, dataset hash and evidence.
- Simulated: finance outcomes, policy owner identity, company approval workflow
  and regulatory applicability determination.
- Production requirement: authenticated policy-owner approval, durable policy
  versioning, customer schema mappings, validated regulatory content and
  governed data connectors.

## Quick control test 1 — stop a sensitive-data leak

### Set up the story

Keep **Stop a data leak** selected. The source card shows a fictional treasury
analyst attempting to use an unapproved public AI service.

Point out:

- destination: **Unapproved public AI**;
- declared class: **Internal**;
- trust boundary: **External provider**; and
- the fictional input contains an email address, bank account and API key.

Say:

> The employee has understated the classification. StyrAI does not trust the
> label alone; it inspects the content and reconciles the destination against the
> approved AI registry before any provider request is made.

### Execute

Select **Intercept outbound AI request**.

### Show the result

The outcome should read **BLOCKED BEFORE PROVIDER**. Call out:

- **Transmission: Prevented**
- **External model invoked: No**
- **Raw prompt stored: No**
- detected credential, email and account patterns
- the created incident

In **Correlated evidence**, show the runtime event, evidence ID, prompt hash,
policy IDs, finding and incident. Emphasise that the raw input is not part of the
governance evidence.

### Proof statement

> This is an enforceable data boundary, not employee training or a policy PDF.
> The prohibited request was stopped locally, the external provider was never
> invoked, and the response is reconstructable without retaining the secret.

### What is real versus simulated

- Functional: classification, sensitive-pattern detection, destination and
  passport checks, block decision, incident creation and evidence.
- Simulated: the employee identity, browser/network connector and public model
  provider.
- Production requirement: an enterprise AI gateway, browser control or API
  proxy connected to customer identity and policy sources.

## Quick control test 2 — contain a deployed finance model

### Set up the story

Select **Contain model drift**. The source card shows **Retail Credit Risk
Decision Support** in production.

Point out:

- model version: `12.4`;
- approved use: analyst decision support;
- owner: Head of Credit Model Risk; and
- current drift: `0.06`, within the approved maximum of `0.15`.

Say:

> Inventory is not enough. StyrAI continuously compares the deployed model's
> telemetry and version with the operating envelope approved in its passport.

### Execute

Select **Inject and contain drift**.

### Show the result

The outcome should read **MODEL CONTAINED**. Call out:

- drift changed from `0.06` to `0.27`;
- approved threshold: `0.15`;
- production state: guarded;
- write-capable calls: routed to fallback;
- monitoring policy breach: recorded; and
- a finding, incident and evidence record were created.

The control trace should show continuous telemetry, the model passport,
monitoring policy and automated containment as one linked decision.

### Proof statement

> The threshold breach is a confirmed internal policy breach. StyrAI contains
> the model immediately and identifies obligations that may be affected, but it
> does not pretend that a metric alone proves a legal violation.

### What is real versus simulated

- Functional: threshold evaluation, before/after telemetry, guarded state,
  policy finding, containment response, incident and evidence.
- Simulated: the production metric feed, model endpoint, fallback invocation and
  notifications.
- Production requirement: observability/model connectors and enforced routing
  integrated with the customer's model-serving layer.

## Quick control test 3 — flag a healthcare policy and regulatory gap

### Set up the story

Select **Flag control gaps**. The source card shows **Clinical Visit Summary
Copilot**, a deployed system that handles restricted health information.

Before execution, point out that observed and approved versions match at
`2026.08.2`. Explain that the control test will simulate discovery of an
unreviewed provider/model version and then reassess the deployed system.

Say:

> StyrAI separates facts, company-policy breaches and regulatory relevance. It
> can identify evidence that an obligation is at risk without making an
> unsupported legal conclusion.

### Execute

Select **Assess deployed AI system**.

This action performs two linked controls:

1. it observes synthetic version `2026.09-unreviewed` against approved version
   `2026.08.2`; and
2. it reassesses the model passport, logging, oversight, monitoring, version
   control and assurance evidence.

### Show the result

The outcome should read **GAP FLAGGED** (or **GAPS FLAGGED** if multiple controls
fail). Call out:

- observed version: `2026.09-unreviewed`;
- approved version: `2026.08.2`;
- high-priority findings;
- assessment result: action required/review required;
- named accountable owner;
- internal policy breaches;
- regulatory obligations at risk; and
- the `2 Dec 2027` potential Annex III readiness horizon, clearly subject to an
  applicability review; and
- **Legal violation confirmed: No**.

In **Correlated evidence**, show the assessment ID, system, findings, policy
breaches, obligation mappings, owner and verified audit chain.

### Proof statement

> StyrAI turns a silent deployment change into an owned control issue. It pauses
> normal trust in the version, opens change-impact and revalidation work, maps
> the affected obligations and preserves the assessment evidence for review.

### What is real versus simulated

- Functional: version mismatch detection, passport reassessment, control-gap
  findings, obligation mapping, ownership and evidence.
- Simulated: provider version discovery, enterprise notifications and external
  regulatory-content feeds.
- Production requirement: registry/deployment connectors, approved policy
  content and jurisdiction-specific validation by compliance and legal owners.

## Show the wider operating platform

After the upload run and quick tests, use the left navigation to connect the
events to the wider platform:

1. **AI systems** — show the deployed and discovered model estate, ownership,
   intended use, provider and status.
2. **Model assurance** — show operating metrics and version controls.
3. **AI use gateway** — show the broader allow, redact, route and block policy
   model for outbound AI traffic.
4. **Policies & obligations** — show technical controls and framework mappings.
   State explicitly that a mapping is not certification.
5. **Automations** — show how discovery, DLP, drift and version events trigger a
   repeatable response.
6. **Findings & response** — show the incidents and owners created during the
   tests.
7. Select **Generate evidence pack** to finish with the assurance output.

## If asked, “Would an LLM evaluate this on the fly?”

Use this answer:

> An LLM can be valuable at the policy-ingestion boundary: it can propose
> clauses, conditions, field mappings and citations from long unstructured
> policies, and it can retrieve likely relevant obligations. Those outputs are
> drafts. A named policy or legal owner approves the interpretation,
> applicability, version and effective date. The live control path then runs
> approved deterministic rules. If evidence is ambiguous or an approved rule
> cannot decide it, StyrAI returns manual review or insufficient evidence. The
> LLM assists the work; it is not the compliance judge.

For this local build, no LLM is used. Conservative deterministic extraction
makes the behaviour reproducible and keeps the demo fully offline.

## Close the demonstration

> StyrAI is the enforcement and evidence layer between corporate AI policy and
> what models and users actually do. It gives management one inventory, catches
> deployed-model risk, prevents sensitive-data leakage, automates containment
> and preserves evidence for accountable review.

## Claims boundary

This is a functional local AI-governance prototype using uploaded synthetic
records and deterministic synthetic events. It houses a curated demonstration
regulation library, not a complete or continuously updated regulatory database.
It does not connect to a real model, employee device, model gateway,
observability platform, customer system, patient record or bank system. It does
not make credit or clinical decisions, provide medical advice, determine legal
applicability or certify compliance.

Production use requires authentication and authorisation, tenant isolation,
durable append-only storage, real gateway and telemetry connectors,
customer-approved policy, safe data-handling architecture, security and privacy
review, jurisdiction-specific legal validation and tested operational
resilience.

## Recovery during a live presentation

- If a result from an earlier rehearsal is visible, select **Reset**.
- If the upload run is not ready, confirm the CSV is uncompressed and was chosen
  from the unzipped `samples` folder. Select **Clear run** and upload it again.
- If the company-policy layer says **Not evaluated**, confirm
  `stricter-company-ai-policy.md` is visible in the policy source box before
  selecting **Run governance assessment**.
- If the page is stale, refresh once; completed backend evidence remains until
  reset.
- If the local server is not responding, return to the Terminal window, stop it,
  and double-click **Start StyrAI Demo.command** again.
- Never enter genuine customer, patient, employee, credential or company data.
