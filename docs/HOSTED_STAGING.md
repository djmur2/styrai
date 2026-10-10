# Hosted StyrAI staging

The shared StyrAI demonstration runs as a separate, password-protected Amazon
Lightsail container service. A collaborator needs only the HTTPS link and their
StyrAI username/password to use it. GitHub access is required only for someone
who will change source code or review pull requests.

## Operating model

- **Hosting:** one Lightsail Nano container node in `eu-north-1` (Stockholm).
- **Expected cost:** USD 7 per month while the service exists, plus private
  image storage and transfer above the included Lightsail allowance.
- **Access:** branded form login backed by PBKDF2 password verification and a
  signed, Secure, HttpOnly, SameSite=Strict session cookie. The public health
  endpoint contains no business data.
- **Deployment:** every verified change merged to `main` is built by GitHub
  Actions, stored in a private ECR repository and deployed automatically using
  short-lived AWS credentials.
- **AWS credentials:** GitHub receives no stored AWS access key. AWS trusts only
  the `main` branch of `djmur2/styrai` through OpenID Connect.
- **Isolation:** the existing `options_trading` EC2 instance, disk, network and
  security group are not used or modified.
- **Data:** use synthetic data only. Uploaded data and demo state are shared by
  the active container but are not durable; a deployment or container restart
  resets the working state. Production persistence is a later architecture
  milestone.

## First-time bootstrap

The infrastructure is declared in
`infra/lightsail/staging-foundation.yaml`. It creates:

1. the `styrai-staging` Lightsail service at Nano power and scale one;
2. a private, scan-on-push ECR repository with image retention;
3. a GitHub Actions identity provider and a deployment role restricted to the
   repository's `main` branch.

The separate `infra/lightsail/staging-budget.yaml` template creates a USD 15
monthly Amazon Lightsail budget notification in the AWS billing home Region.

Deploy the foundation from an authenticated AWS CloudShell in Stockholm:

```bash
aws cloudformation deploy \
  --region eu-north-1 \
  --stack-name styrai-staging-foundation \
  --template-file staging-foundation.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --no-fail-on-empty-changeset
```

Deploy the billing guardrail in US East (N. Virginia), where this account
exposes the AWS Budgets CloudFormation resource:

```bash
aws cloudformation deploy \
  --region us-east-1 \
  --stack-name styrai-staging-budget \
  --template-file staging-budget.yaml \
  --no-fail-on-empty-changeset
```

Then copy the `GitHubDeployRoleArn` stack output into the repository variable
`AWS_DEPLOY_ROLE_ARN`. Store the generated authentication mapping as the
repository secret `STYRAI_AUTH_USERS_JSON`, and store a separate high-entropy
secret of at least 32 bytes as `STYRAI_SESSION_SECRET`. The application fails
closed when website authentication is enabled without this signing secret.
None of these values gives a website user AWS access.

The initial deployment can then be launched from **GitHub → Actions → Deploy
StyrAI staging → Run workflow**. Subsequent merges to `main` deploy
automatically after the test suite and container build succeed.

## Sharing with a collaborator

Send the collaborator:

1. the service's HTTPS URL;
2. their StyrAI username; and
3. their temporary password through a separate channel.

They can upload synthetic CSV/JSON datasets, upload written company policies,
run governance assessments and exercise the model-monitoring and outbound-data
controls. They do not need AWS or GitHub access for any of those actions.

## Updating the application

A source-code contributor works through GitHub:

1. create a branch;
2. make and test a change;
3. open a pull request;
4. merge after review and passing checks; and
5. allow the staging workflow to publish the update.

Existing staging sessions are intentionally invalidated during a deployment or
container restart, and current in-memory uploads and run results are cleared.
Signing out removes the active session from the single-node session registry,
so a copied old cookie cannot be replayed. The application version in the
GitHub deployment summary identifies the deployed commit.

## Rollback

Lightsail retains earlier deployments and ECR retains the 20 most recent
images. To roll back, re-run the deployment workflow from the desired commit or
create a deployment that references the earlier immutable image tag. Verify
`/api/health` and the sign-in challenge before sharing the restored link.

## Custom domain

The default Lightsail hostname is HTTPS-enabled and can be shared immediately.
`staging.styrai.com` can be added later without changing the application:

1. request a Lightsail certificate for `staging.styrai.com`;
2. add its validation CNAME in the current GoDaddy DNS zone;
3. attach the validated certificate to the container service; and
4. point the `staging` CNAME at the Lightsail service hostname.

Keep the default hostname available until the custom hostname has been tested.

## Removing the monthly charge

Disabling a Lightsail container service does not stop its charge. Delete the
CloudFormation stack when the shared demo is no longer required. The ECR
repository is intentionally protected from automatic deletion while it still
contains images, so remove retained staging images first if the stack deletion
reports that repository as non-empty.
