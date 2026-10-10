# StyrAI Regulatory Watch

**Review date:** 1 October 2026  
**Purpose:** product requirements and customer discovery, not legal advice.

## Current signals and product implications

| Signal | Current position | StyrAI implication |
|---|---|---|
| Norwegian financial-sector risk | Finanstilsynet's 2026 analysis highlights shadow AI, missing traceability, model/decision risk and insufficient human control over agentic actions | Inventory/passport gate, runtime policy, human approval and reconstructable evidence are core |
| DORA in Norway | Norwegian DORA law and regulations took effect 1 July 2025; focus includes ICT governance, incidents, testing and third-party risk | Treat model providers and agent infrastructure as governed dependencies; support incident and register evidence without claiming DORA compliance |
| EU AI Act enforcement | Enforcement powers now cover prohibited practices, relevant transparency duties and GPAI rules; Article 50 transparency duties started applying on 2 August 2026, subject to the Act's transition details | Add human-facing AI disclosure and machine-readable provenance where the customer use case requires it; record which rule and date actually apply rather than using one generic “AI Act compliant” status |
| AI Omnibus timing | The AI Omnibus entered into force on 27 July 2026; Annex III high-risk rules now apply from 2 December 2027 and high-risk rules for systems embedded in Annex I regulated products from 2 August 2028 | Keep the control library operational now, but make applicability and readiness dates explicit; never present an internal control breach as proof that a future-dated legal duty was violated |
| High-risk classification | Annex III includes natural-person creditworthiness/credit scoring and life/health insurance risk assessment and pricing; scope includes exceptions | Add explicit use-case classification, provider/deployer role, risk tier and an escalation path; do not infer classification from industry alone |
| High-risk guidance | Commission guidance is still evolving; draft classification guidance was published in May 2026 and final guidance is expected by end-2026 | Keep mappings versioned and clearly label draft/final status; do not hard-code one legal interpretation into runtime policy |
| Banking overlap | EBA mapped AI Act requirements against CRD, CRR, DORA, consumer-credit, mortgage-credit, payment and governance requirements | Create a customer-specific crosswalk from evidence to multiple obligations rather than separate evidence silos |
| Insurance governance | EIOPA's August 2025 opinion uses a risk-based, proportionate lifecycle approach and stresses governance, explainability, data, documentation and records | Model passport and evidence pack should work for non-high-risk systems as well as high-risk candidates |
| Investment services | ESMA expects existing MiFID II organisational, conduct and best-interest duties to apply when firms use AI | Adviser/customer-content workflows need human accountability, disclosure, competence and evidence; autonomous advice is outside the first pilot |
| Frontier-model concentration | Finanstilsynet and EBA identify cyber, dependency, provider concentration and third-party risks | Record provider/version/deployment boundary; build change-impact and exit-plan support after validation |
| NIST AI RMF revision | NIST states that AI RMF 1.0 is being revised and launched a 2026 critical-infrastructure profile initiative | Version NIST mappings, preserve the mapped source version in evidence and prepare for control-library migration rather than silently replacing existing mappings |

## Norway-specific caution

The Norwegian government currently describes the EU AI Act as EEA-relevant and
acceptable, with national legal changes and an Article 103 reservation required.
Until incorporation and Norwegian implementation are confirmed, StyrAI should
not market itself as certifying compliance with a Norwegian AI Act. Customers may
still prepare for the EU framework and may be directly exposed through EU
operations or product placement; that needs customer-specific legal analysis.

## Product requirements created by the watch

- every action records industry, use case, agent, human principal, model and
  exact model version;
- exact model versions require an approved passport;
- use outside a passport's intended purpose or tool scope fails closed;
- approvals bind to the exact proposal and policy version;
- material actions can require multiple distinct approvers;
- evidence exports distinguish technical facts from regulatory mappings;
- mappings carry framework name, provision/control, version, status and review
  date;
- mappings distinguish a rule's publication, application and enforcement dates;
- regulation updates create a review task, not automatic production-policy
  changes.

## Monitoring priorities

1. Final European Commission high-risk classification guidance and any changes
   to implementation support before the 2 December 2027 Annex III date.
2. Norway's EEA incorporation and national AI legislation.
3. EBA follow-up to its banking/payments AI Act mapping.
4. Finanstilsynet supervisory findings involving AI, models, outsourcing or DORA.
5. EIOPA and ESMA additions concerning GenAI and agentic systems.
6. Technical standards for AI Act evidence, logs, quality management and
   post-market monitoring.
7. The revised NIST AI RMF and the Trustworthy AI in Critical Infrastructure
   Profile.

## Primary sources

- [Norwegian government AI Act EEA note](https://www.regjeringen.no/no/sub/eos-notatbasen/notatene/2021/juni/forslag-til-forordning-om-kunstig-intelligens-ki-forordningen/id2884935/)
- [Finanstilsynet Risk and Vulnerability Analysis 2026](https://www.finanstilsynet.no/publikasjoner-og-analyser/risiko--og-sarbarhetsanalyse/risiko--og-sarbarhetsanalyse-2026/risiko--og-sarbarhetsanalyse-2026/risiko--og-sarbarhetsanalyse-2026/)
- [Finanstilsynet DORA overview](https://www.finanstilsynet.no/tema/dora/forordning-om-digital-operasjonell-motstandsdyktighet-i-finanssektoren-dora/)
- [European Commission high-risk guidance](https://digital-strategy.ec.europa.eu/en/policies/guidelines-ai-high-risk-systems)
- [European Commission: AI Omnibus enters into force](https://digital-strategy.ec.europa.eu/en/news/ai-omnibus-enters-force)
- [European Commission AI Act Service Desk: enforcement timeline](https://ai-act-service-desk.ec.europa.eu/en/ai-act/faq/when-does-enforcement-start)
- [EU AI Act text](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32024R1689)
- [EBA AI Act implications for banking and payments](https://www.eba.europa.eu/sites/default/files/2025-11/d8b999ce-a1d9-4964-9606-971bbc2aaf89/AI%20Act%20implications%20for%20the%20EU%20banking%20sector.pdf)
- [EIOPA AI governance opinion](https://www.eiopa.europa.eu/publications/opinion-artificial-intelligence-governance-and-risk-management_en)
- [ESMA AI investment-services guidance](https://www.esma.europa.eu/press-news/esma-news/esma-provides-guidance-firms-using-artificial-intelligence-investment-services)
- [NIST AI Risk Management Framework](https://www.nist.gov/itl/ai-risk-management-framework)
