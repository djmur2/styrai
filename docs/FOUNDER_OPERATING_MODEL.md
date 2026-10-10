# StyrAI founder operating model

## One source of truth

StyrAI uses this private GitHub repository as the single home for product code,
infrastructure definitions, product documentation, decisions and delivery work.
GitHub Issues and a GitHub Project should be used for planning until the team has
a demonstrated need for a separate Jira subscription.

The operating stack is intentionally small:

| System | Purpose | Authority |
| --- | --- | --- |
| GitHub | Code, reviews, issues, roadmap and automated delivery | Product source of truth |
| AWS | Authenticated staging and production workloads | Runtime source of truth |
| GoDaddy | Domain registration and DNS until migration is justified | Domain source of truth |

## Environments

| Environment | Address | Use | Data rule |
| --- | --- | --- | --- |
| Local | `127.0.0.1` | Development and rehearsals | Synthetic data only |
| Staging | `staging.styrai.com` | Founder collaboration and investor demos | Synthetic data only |
| Production | `app.styrai.com` | Future customer pilots | Not enabled until security and privacy acceptance |

Merges to `main` will eventually deploy to staging after tests pass. Production
will remain a separately approved release until the company has a mature release
process and customer commitments.

## Change workflow

1. Create or select a GitHub Issue with a measurable acceptance test.
2. Implement the change on a short-lived branch.
3. Open a pull request and allow the automated tests and container build to run.
4. Have the other founder review material product, policy or security decisions.
5. Merge to `main`; the staging deployment runs automatically once AWS is wired.
6. Record operating evidence and material decisions in the repository.

No passwords, access keys, real customer records, patient information, financial
records or raw confidential prompts belong in GitHub. AWS access should use
short-lived identity federation. GitHub Actions should deploy with OpenID Connect,
not stored AWS access keys.

## Founder responsibilities

The account owner retains the few decisions that cannot safely be delegated:

- complete MFA or identity-provider challenges;
- approve partner access and other permission changes;
- approve the first deployment or any material increase in cloud spend;
- approve production use of non-synthetic data; and
- approve legal, regulatory and customer-facing claims.

Codex can prepare and operate the remaining workflow: backlog maintenance,
implementation, tests, documentation, infrastructure-as-code, deployment
preparation, release evidence and monitoring follow-up.

## Deployment gates

The public application must not be launched from the current local server without
the following controls:

- authenticated access and named users;
- TLS, secure headers and request-size limits;
- durable evidence storage with encryption, backup and retention rules;
- secrets management and short-lived deployment credentials;
- environment separation and least-privilege roles;
- structured logs, health checks, alarms and budget alerts;
- synthetic-only staging data and explicit production data approval; and
- tested restore, rollback and incident-response procedures.

## Immediate delivery sequence

1. Preserve the tested prototype in this repository.
2. Add continuous testing and a reproducible container build.
3. Inventory the existing AWS EC2, VPC and storage resources before reuse.
4. Define AWS infrastructure as code and an authenticated staging environment.
5. Connect `staging.styrai.com` after deployment health checks pass.
6. Invite the second founder to GitHub and staging with named, separate accounts.
7. Add automated cost, uptime, security and regulatory-content monitoring.
