# Deployment guide

## Prerequisites

- AWS CLI configured, Terraform `>= 1.5`, Python `3.10+` with `pip`
- An **existing** SageMaker **real-time endpoint** whose request/response match what `lambda/lib/inference.py` and `lambda/lib/redaction.py` expect (or adjust those modules)
- An Azure **Storage Account** and **container** for outputs; credentials available as connection string or account URL + SAS

## 1. Build the Lambda artifact

**Windows (PowerShell):**

```powershell
Set-Location "c:\Users\utaka\Downloads\MCDS-Redaction-Pipeline"
.\scripts\build_lambda_zip.ps1
```

**macOS / Linux:**

```bash
chmod +x scripts/build_lambda_zip.sh
./scripts/build_lambda_zip.sh
```

This creates `lambda/deployment.zip` (gitignored).

## 2. Configure Terraform variables

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars`: set `sagemaker_endpoint_name`, `azure_output_container`, and `lambda_zip_path` (default `../lambda/deployment.zip` is correct if you run Terraform from the `terraform/` directory).

## 3. Apply infrastructure

```bash
terraform init
terraform plan
terraform apply
```

## 4. Store Azure credentials in Secrets Manager

After apply, note `azure_secret_arn` from Terraform output. Put the JSON secret (see `iam/azure-secret.example.json` for shape):

```bash
aws secretsmanager put-secret-value \
  --secret-id "<azure_secret_arn>" \
  --secret-string file://../iam/azure-secret.example.json
```

Use a real JSON file locally; do not commit secrets.

## 5. Create a Cognito user

Use the console or CLI to create a user in the pool, or self-sign-up if enabled.

## 6. Call the API

Obtain tokens (example using USER_PASSWORD_AUTH — prefer SRP or hosted UI in production):

```bash
aws cognito-idp initiate-auth \
  --auth-flow USER_PASSWORD_AUTH \
  --client-id "<cognito_app_client_id>" \
  --auth-parameters USERNAME=you@example.com,PASSWORD='...'
```

Use `AuthenticationResult.AccessToken` in the `Authorization` header:

```bash
curl -s -X POST "<api_invoke_url>/redact" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"Contact John Doe at john@example.com"}'
```

`api_invoke_url` is the Terraform output `api_invoke_url` (ends with `/prod`).

## 7. SageMaker contract

Default payload: `{"text": "<string>", "max_length": null}`.

Default response: `{"entities": [{"start": 0, "end": 8, "type": "NAME"}, ...]}`.

If your model differs, update `lambda/lib/inference.py` and `lambda/lib/redaction.py` accordingly.

## Local unit tests (redaction only)

```bash
cd lambda
python -m unittest discover -s tests -p "test_*.py"
```

## Re-deploy code changes

Rebuild `deployment.zip`, then:

```bash
cd terraform
terraform apply
```

`source_code_hash` triggers Lambda update when the zip changes.
