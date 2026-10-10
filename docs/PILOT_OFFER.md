# StyrAI Design-Partner Pilot

## Outcome

Govern one bounded AI-agent workflow and give the customer a reviewable record of
what the agent attempted, which policy applied, who approved sensitive actions,
and what was ultimately authorised.

## Suggested format

Four weeks, fixed scope, one workflow, one agent or agent application, and no
production access until the customer's security owner approves the design.

For the financial-services variant, use a test payment-operations or customer-
communication workflow. Exclude autonomous credit decisions, insurance pricing,
trading and investment advice from the first pilot.

### Week 1 — workflow and risk mapping

- identify the agent, human owners, tools, data classes and consequential actions;
- document existing controls and approval points;
- agree the pilot policy and success measures.

### Week 2 — controlled integration

- connect a test environment to the StyrAI gateway;
- register the agent and human principal;
- register the exact model/version passport, intended use and tool scope;
- configure allow, deny and approval-required rules.

### Week 3 — evidence and failure testing

- exercise permitted, prohibited and ambiguous scenarios;
- exercise self-approval, duplicate approval, model-version change and unintended
  use scenarios;
- verify approval routing and fail-closed behaviour;
- produce the first evidence export and remediation list.

### Week 4 — decision and handover

- review findings with security, quality and business owners;
- document residual risks and operating responsibilities;
- agree stop, extend, or convert to a subscription.

## Customer receives

- one governed agent workflow in a controlled environment;
- workflow and control map;
- versioned pilot policy;
- action and approval evidence export;
- model passport and decision-receipt evidence;
- failure-test results;
- operating and residual-risk recommendations.

## Customer responsibilities

- nominate business, technical, and risk owners;
- provide a safe test environment and representative scenarios;
- approve data handling and access before connection;
- retain accountability for legal, regulatory, security and production decisions.

## Suggested price test

Test a fixed fee of **NOK 100,000–250,000** for the general pilot and **NOK
150,000–300,000** for a financial-services pilot requiring additional security,
risk and third-party review, depending on integration complexity.
This is a pricing hypothesis, not a market benchmark. Do not discount to zero in
exchange for vague feedback; a sharply limited paid discovery engagement is a
better signal than an open-ended free pilot.

## Conversion hypothesis

After a successful pilot, test **NOK 15,000–50,000 per month** for the control
plane, evidence retention, policy updates and support. Usage-based pricing can be
added only after actual action volumes are understood.

## Required disclaimer

StyrAI provides technical controls and evidence-management support. It does not
certify compliance or replace legal, regulatory, privacy, quality or security
advice.
