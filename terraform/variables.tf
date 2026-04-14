variable "aws_region" {
  type        = string
  description = "Region for all resources (match SageMaker endpoint region when possible)."
  default     = "us-east-1"
}

variable "project_name" {
  type        = string
  description = "Prefix for named resources."
  default     = "pii-redaction"
}

variable "sagemaker_endpoint_name" {
  type        = string
  description = "Existing SageMaker real-time endpoint name."
}

variable "azure_output_container" {
  type        = string
  description = "Azure Blob container name for redacted outputs (must exist or create in Azure)."
}

variable "lambda_zip_path" {
  type        = string
  description = "Path to deployment.zip after running scripts/build_lambda_zip.*"
}

variable "lambda_runtime" {
  type        = string
  description = "Python runtime for Lambda."
  default     = "python3.12"
}

variable "lambda_timeout_seconds" {
  type        = number
  description = "Lambda timeout (SageMaker + Azure latency)."
  default     = 60
}

variable "lambda_memory_mb" {
  type        = number
  default     = 512
}

variable "max_input_chars" {
  type        = number
  description = "Passed to Lambda env MAX_INPUT_CHARS."
  default     = 100000
}

variable "blob_prefix" {
  type        = string
  description = "Optional logical prefix inside the container (no slashes required)."
  default     = ""
}

variable "secret_kms_key_arn" {
  type        = string
  description = "Optional CMK ARN for encrypting the Secrets Manager secret. Leave empty for default encryption."
  default     = null
}

variable "cognito_mfa_configuration" {
  type        = string
  description = "OFF, ON, or OPTIONAL for the user pool."
  default     = "OFF"
}
