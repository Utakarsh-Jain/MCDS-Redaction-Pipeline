resource "aws_iam_role" "lambda_exec" {
  name = "${var.project_name}-lambda-exec"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

locals {
  lambda_kms_decrypt_statement = var.secret_kms_key_arn == null ? [] : [
    {
      Sid    = "KmsDecryptSecret"
      Effect = "Allow"
      Action = ["kms:Decrypt"]
      Resource = [var.secret_kms_key_arn]
      Condition = {
        StringEquals = {
          "kms:ViaService" = "secretsmanager.${data.aws_region.current.name}.amazonaws.com"
        }
      }
    },
  ]
}

resource "aws_iam_role_policy" "lambda_redaction" {
  name = "${var.project_name}-lambda-inline"
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(
      [
        {
          Sid    = "SageMakerInvoke"
          Effect = "Allow"
          Action = "sagemaker:InvokeEndpoint"
          Resource = format(
            "arn:aws:sagemaker:%s:%s:endpoint/%s",
            data.aws_region.current.name,
            data.aws_caller_identity.current.account_id,
            var.sagemaker_endpoint_name
          )
        },
        {
          Sid    = "SecretsManagerRead"
          Effect = "Allow"
          Action = [
            "secretsmanager:GetSecretValue",
            "secretsmanager:DescribeSecret",
          ]
          Resource = aws_secretsmanager_secret.azure_blob.arn
        },
      ],
      local.lambda_kms_decrypt_statement
    )
  })
}

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${var.project_name}-redact"
  retention_in_days = 30
}

resource "aws_lambda_function" "redact" {
  function_name = "${var.project_name}-redact"
  role          = aws_iam_role.lambda_exec.arn
  handler       = "redact_handler.lambda_handler"
  runtime       = var.lambda_runtime
  timeout       = var.lambda_timeout_seconds
  memory_size   = var.lambda_memory_mb

  filename         = var.lambda_zip_path
  source_code_hash = filebase64sha256(var.lambda_zip_path)

  environment {
    variables = {
      SAGEMAKER_ENDPOINT_NAME  = var.sagemaker_endpoint_name
      AZURE_BLOB_SECRET_ARN     = aws_secretsmanager_secret.azure_blob.arn
      AZURE_OUTPUT_CONTAINER    = var.azure_output_container
      BLOB_PREFIX               = var.blob_prefix
      MAX_INPUT_CHARS           = tostring(var.max_input_chars)
      SECRET_CACHE_TTL_SEC      = "300"
      SAGEMAKER_CONTENT_TYPE    = "application/json"
      SAGEMAKER_ACCEPT          = "application/json"
    }
  }

  depends_on = [aws_cloudwatch_log_group.lambda]
}
