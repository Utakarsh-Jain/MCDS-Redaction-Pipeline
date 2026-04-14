# IAM and secrets

## Lambda policy template

`lambda-redaction-policy.json` is a **template**. Replace placeholders before attaching:

| Placeholder | Meaning |
|-------------|---------|
| `REGION` | AWS region (e.g. `us-east-1`) |
| `ACCOUNT_ID` | 12-digit account id |
| `FUNCTION_NAME` | Lambda function name |
| `SAGEMAKER_ENDPOINT_NAME` | SageMaker endpoint **name** (not full ARN in Resource) |
| `SECRET_NAME_PREFIX` | Secrets Manager secret name prefix (suffix `-xxxxxx` is random; IAM uses `secret:name-*`) |
| `KMS_KEY_ID` | Only if the secret uses a customer-managed CMK; otherwise **omit** the `KmsDecryptViaSecretsManager` statement |

Terraform in `../terraform/` generates a scoped inline policy automatically.

To enable **AWS X-Ray** on the Lambda function, merge `lambda-xray-optional.json` into the role policy (or attach `arn:aws:iam::aws:policy/AWSXRayDaemonWriteAccess`) and set Lambda `tracing_config.mode = Active`.

## Azure secret shape (Secrets Manager)

Store **one** JSON object as the secret string. Supported keys:

- **Option A:** `connection_string` — full Azure Storage connection string.
- **Option B:** `account_url` + `sas_token` — e.g. `https://myacct.blob.core.windows.net` and the SAS **without** leading `?`.

See `azure-secret.example.json` (replace with real values only in the AWS console or via CI, never commit secrets).
