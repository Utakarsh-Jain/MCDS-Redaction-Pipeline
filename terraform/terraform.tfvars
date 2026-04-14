aws_region              = "ap-south-1"
project_name            = "pii-redaction"
sagemaker_endpoint_name = "redaction-endpoint-v2"
azure_output_container  = "redacted-output"

# Build lambda/deployment.zip first (see docs/DEPLOYMENT.md)
lambda_zip_path = "../lambda/deployment.zip"

# Optional
# blob_prefix          = "tenant-a"
# secret_kms_key_arn   = "arn:aws:kms:us-east-1:123456789012:key/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
# lambda_timeout_seconds = 90
# lambda_memory_mb       = 1024
