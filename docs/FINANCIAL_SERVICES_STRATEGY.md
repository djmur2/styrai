# StyrAI Financial Services Strategy

## Recommendation

Financial services should be a first-class StyrAI vertical hypothesis, not a
generic expansion into “model governance.” Banks and insurers already have model
risk, validation and GRC systems. StyrAI should integrate with those systems
and govern the runtime gap created by generative AI, third-party models and
agents that can act through business tools.

The initial proposition is:

> Put a policy and evidence boundary between financial AI agents and consequential
> business actions—without replacing the institution's existing model inventory,
> identity platform or risk-management framework.

## Why now

Finanstilsynet's 2026 risk analysis specifically calls out shadow AI, weak
traceability, model and decision risk, and agentic solutions acting without
sufficient human control. Its June 2026 outlook also highlights dependency and
concentration risk arising from a small number of advanced model providers.

DORA has applied in Norway since 1 July 2025. It reinforces board accountability,
ICT risk management, incident handling, resilience testing and third-party risk.
The EU AI Act now adds transparency and, for defined use cases, high-risk-system
requirements. Creditworthiness and credit scoring of natural persons, and life
and health insurance risk assessment and pricing, appear in Annex III, subject
to the detailed scope, exceptions and evolving implementation timeline.

These frameworks overlap. The buyer does not need another regulation summary;
the buyer needs evidence that operational controls actually ran.

## Best first workflow

Start with **agent-assisted payment operations or customer communication in a
test environment**.

Payment operations provides an unusually clear demonstration:

- every release has an initiator and a monetary threshold;
- separation of duties is familiar to buyers;
- high-value actions can require two independent approvers;
- the authorisation receipt can be reconciled to the eventual execution outcome;
- the first pilot can avoid autonomous credit, pricing, trading or advice.

Customer communication is the second candidate. It demonstrates model identity,
approved intended use, restricted-data controls, human review and disclosure,
while keeping the final decision with an employee.

## Segment order

| Priority | Segment/use case | Why | Initial posture |
|---|---|---|---|
| 1 | Payment and operations agents | Clear actions, thresholds, dual control and evidence | Pilot candidate |
| 2 | Customer-service and adviser copilots | Conduct, privacy and human-review pressure | Pilot candidate |
| 3 | Third-party GenAI/model change governance | DORA/provider concentration and version risk | Product expansion |
| 4 | Claims and underwriting support | Strong documentation and oversight need | Validate after first pilot |
| 5 | Creditworthiness, life/health pricing | Explicit high-risk AI Act territory | Later, assurance-heavy |
| 6 | Autonomous trading or investment advice | High conduct, market and loss exposure | Excluded from initial scope |

## Buyer group

The economic buyer is likely to be one of:

- Chief Risk Officer or operational-risk leader;
- Head of Model Risk or Model Validation;
- Chief Information Security Officer;
- Head of Compliance or Conduct Risk;
- AI governance or responsible-AI lead;
- business owner for payments, operations or customer service.

A pilot needs both a business owner and an independent risk/control owner.

## Product capabilities derived from the sector

### Implemented in the prototype

- deterministic allow, deny or approval-required decisions;
- fail-closed treatment of unknown actions;
- four-eyes approval for material payments;
- separation between initiator and approvers;
- model/version passports with intended-use and tool restrictions;
- policy-bound decision receipts;
- hash-chained evidence and action-specific evidence export.

### Next after customer validation

1. **Outcome reconciliation** — link the approved proposal to what the target
   system actually executed, including partial failure or reversal.
2. **Change-impact graph** — show which agents and controls are affected when a
   model, provider, tool, data source or policy changes.
3. **Third-party model register** — capture provider, hosting region, subprocessors,
   critical function, exit plan and DORA register references without duplicating
   the customer's authoritative register.
4. **Signed short-lived authorisation tokens** — bind approval to exact action
   parameters and prevent replay.
5. **Incident reconstruction pack** — export identities, policy state, model
   passport, approvals, outcome and evidence-integrity checks.
6. **Control evidence mappings** — map technical evidence to customer-selected
   DORA, AI Act, EBA/EIOPA/ESMA and internal policy controls.
7. **Shadow-agent discovery** — observe unregistered agent and model traffic,
   initially in report-only mode.

## Important product boundary

StyrAI must not claim to validate the predictive performance of every financial
model. It should ingest validation status from the customer's existing process
and enforce the approved-use boundary at runtime.

It should not store raw customer prompts, customer records or hidden model
reasoning by default. Store classified metadata, hashes and evidence necessary
for reconstruction, with sensitive payloads remaining customer-side wherever
possible.

## Commercial test

Offer a four-week, test-environment **Governed Financial Agent Pilot** at a
suggested NOK 150,000–300,000 price point. This is a pricing hypothesis.

The strongest proof is not positive feedback. It is a buyer supplying one real
workflow, appointing risk and business owners, accepting security review and
funding the pilot.

## Current primary sources

- [Finanstilsynet Risk and Vulnerability Analysis 2026](https://www.finanstilsynet.no/publikasjoner-og-analyser/risiko--og-sarbarhetsanalyse/risiko--og-sarbarhetsanalyse-2026/risiko--og-sarbarhetsanalyse-2026/risiko--og-sarbarhetsanalyse-2026/)
- [Finanstilsynet DORA overview](https://www.finanstilsynet.no/tema/dora/forordning-om-digital-operasjonell-motstandsdyktighet-i-finanssektoren-dora/)
- [EBA June 2026 Risk Assessment](https://www.eba.europa.eu/publications-and-media/publications/risk-assessment-report-june-2026)
- [EU AI Act consolidated text](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32024R1689)
- [EIOPA Opinion on AI governance and risk management](https://www.eiopa.europa.eu/publications/opinion-artificial-intelligence-governance-and-risk-management_en)
- [ESMA guidance on AI in investment services](https://www.esma.europa.eu/press-news/esma-news/esma-provides-guidance-firms-using-artificial-intelligence-investment-services)

This strategy is product and market analysis, not legal advice.
