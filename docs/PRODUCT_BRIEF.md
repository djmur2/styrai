# StyrAI Product Brief

## Working proposition

StyrAI is an AI-governance operations layer for organisations deploying models
and agents in regulated or quality-sensitive workflows. It provides one control
plane for discovery, production use, data boundaries, model health, accountable
action and evidence.

It gives the buyer a defensible answer to seven questions:

1. Which models and agents are in use, and who owns them?
2. Is the exact model version operating within its approved purpose and boundary?
3. What information is being sent, and was it allowed, redacted or blocked?
4. Is the production model still healthy and within approved thresholds?
5. Which agent acted, and on whose behalf?
6. What policy, automation and human approval applied at that moment?
7. Can the organisation reconstruct the decision, containment and outcome later?

## Initial customer

The initial design partner should be a European mid-sized financial-services or
quality-regulated organisation that:

- is piloting or operating at least one AI agent;
- lets that agent access internal documents or business tools;
- has a security, quality, privacy, risk, or compliance stakeholder;
- finds large enterprise governance suites disproportionate;
- can provide one bounded, non-safety-critical workflow for a pilot.

The two opening hypotheses are Nordic financial services and Nordic life
sciences/diagnostics. They share a control plane but must not become two parallel
product builds. Run a short evidence sprint in both and select the first vertical
from paid pull, buyer access and deployment feasibility.

## Initial job to be done

> Let us operate useful AI in production without losing visibility, control of
> sensitive information, model assurance, human accountability or audit evidence.

## First product boundary

The demonstrable product will:

- inventory registered and discovered AI systems, providers, owners and uses;
- register an agent and its human principal;
- require an approved passport for the exact model version and intended use;
- inspect outbound model inputs and block secrets or unapproved destinations;
- redact confidential information before an approved external gateway;
- monitor quality, drift, errors, latency, usage and cost;
- contain threshold breaches and silent model-version changes;
- receive proposed tool actions through a gateway;
- apply deterministic, versioned rules;
- fail closed when no rule permits an action;
- route selected actions to a named human approver;
- support separation of duties and multi-person approval;
- issue a decision receipt binding action, policy, model and approvers;
- produce a tamper-evident action and approval record;
- turn breaches into owned incidents and automated response;
- export evidence packs and technical framework crosswalks for internal review.

It will not initially:

- build general-purpose agents;
- train or host foundation models;
- replace identity, data-loss-prevention, SIEM, GRC or independent model-validation platforms;
- evaluate every dimension of model quality, fairness or safety;
- guarantee legal or regulatory compliance;
- support every model provider and agent framework.

## Differentiation hypothesis

StyrAI should be easier to buy and operate than a broad enterprise
AI-governance suite. The wedge is continuous runtime control plus usable evidence:
a provider-neutral layer that connects existing gateways, telemetry, identity,
ticketing and assurance tools instead of demanding they be replaced.

The hypothesis is unproven until a buyer pays for a pilot.

## Product success measures

- report-only installation into one workflow in less than two working days;
- every discovered AI system assigned an owner and approved/blocked disposition;
- prohibited secrets do not cross the model trust boundary in the agreed tests;
- monitoring and version breaches trigger the agreed containment workflow;
- every governed action linked to an agent, principal, model version, use case,
  policy version and outcome;
- selected high-risk actions cannot proceed without recorded approval;
- an internal reviewer can reconstruct a sampled action in under five minutes;
- the customer agrees to pay for continued operation after the pilot.
