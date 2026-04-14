output "api_invoke_url" {
  description = "Base URL for the prod stage (append /redact for POST)."
  value       = aws_api_gateway_stage.prod.invoke_url
}

output "cognito_user_pool_id" {
  value = aws_cognito_user_pool.this.id
}

output "cognito_user_pool_arn" {
  value = aws_cognito_user_pool.this.arn
}

output "cognito_app_client_id" {
  value     = aws_cognito_user_pool_client.api.id
  sensitive = false
}

output "azure_secret_arn" {
  description = "Put JSON credentials with aws secretsmanager put-secret-value."
  value       = aws_secretsmanager_secret.azure_blob.arn
}

output "lambda_function_name" {
  value = aws_lambda_function.redact.function_name
}

output "lambda_role_arn" {
  value = aws_iam_role.lambda_exec.arn
}
