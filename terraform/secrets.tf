resource "aws_secretsmanager_secret" "azure_blob" {
  name                    = "${var.project_name}/azure-blob-credentials"
  recovery_window_in_days = 7
  kms_key_id              = var.secret_kms_key_arn
}

# After first apply, set the secret value (JSON) via Console or:
# aws secretsmanager put-secret-value --secret-id <arn> --secret-string file://iam/azure-secret.example.json
