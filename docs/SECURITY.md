# Security practices (hybrid AWS–Azure)

## Authentication

- Use **Cognito** access tokens (or ID tokens) consistently with what API Gateway’s Cognito authorizer expects.
- Prefer **SRP** or **hosted UI** over raw `USER_PASSWORD_AUTH` in production.
- Add **MFA** (`cognito_mfa_configuration`) for sensitive environments.

## Secrets

- Azure credentials live only in **Secrets Manager**; Lambda reads by **ARN** at runtime.
- Rotate secrets on a schedule; after rotation, clear in-process cache (lower `SECRET_CACHE_TTL_SEC` or deploy) so new values load.
- Prefer **SAS tokens** with narrow permissions and expiry over full account keys when possible.

## IAM

- Lambda role is scoped to **one** SageMaker endpoint ARN, **one** secret ARN, and CloudWatch Logs.
- If the secret uses a **CMK**, grant `kms:Decrypt` only for that key with `kms:ViaService` = Secrets Manager.
- Do not attach broad `sagemaker:InvokeEndpoint` on `*`.

## Network

- Default Lambda egress reaches Azure over the public internet with TLS. For IP allowlisting on Azure, use **NAT Gateway** static IPs or Azure service configuration.
- Optional: **VPC endpoints** for SageMaker Runtime, Secrets Manager, and CloudWatch Logs to keep AWS-side traffic off the public internet.

## Data

- Redacted text is uploaded to Blob; enable **encryption at rest** (Microsoft-managed or customer-managed keys).
- Consider **separate containers** or prefixes per tenant using `sub` from JWT claims (already used in blob path).

## API hardening

- Attach **AWS WAF** to API Gateway for rate limits and geo rules.
- Set **maximum payload** and **quota** via API Gateway / usage plans.
- Never log raw **PII** or Azure connection strings.
