# Async processing, batch, and observability (extensions)

## Async with SQS

**Goal:** Return quickly with `202 Accepted` and a `job_id` while workers process heavy documents.

1. API Gateway **Lambda A** (thin): validate JWT context, enqueue `{ job_id, s3_uri or text pointer, user_sub }` to **SQS**.
2. **Lambda B** (worker): triggered by SQS, loads text from S3 if needed, runs the same SageMaker + redaction + Azure upload path.
3. Store status in **DynamoDB** (`job_id` → `PENDING | DONE | FAILED`).
4. Optional: **API Gateway GET /jobs/{id}** backed by Lambda reading DynamoDB; authorize same Cognito pool.

**Pitfalls:** Visibility timeout vs Lambda timeout; use **DLQ** and `maxReceiveCount`; idempotent writes keyed by `job_id`.

## EventBridge

Use **EventBridge** when uploads to S3 or control-plane events should **start** redaction (fan-out to Lambda/SQS). Keeps the HTTP API for interactive use and events for batch pipelines.

## Batch inference

For large backlogs, **SageMaker Batch Transform** reads input from S3 and writes predictions to S3. A follow-up Lambda or **Glue** job reads predictions, applies redaction, and streams results to Azure. Often cheaper than millions of synchronous `InvokeEndpoint` calls.

## Observability

- **Structured logs:** JSON lines with `request_id`, `user_sub`, stage timings (`sm_ms`, `azure_ms`), `entity_count`.
- **CloudWatch metrics:** Custom `Namespace=PIIRedaction` for errors, throttles, SM latency; alarms on `5XX`, `Duration`, `Errors`.
- **API Gateway execution logging:** Enable access logs to S3 or CloudWatch (mind PII in URLs — avoid logging raw bodies).
- **X-Ray:** Set `tracing_config` on Lambda to `Active`, attach `AWSXRayDaemonWriteAccess`, enable tracing on API stage; add subsegments around boto3 calls where useful.

## Cost and scaling

- **Lambda:** Concurrency limits, provisioned concurrency for steady traffic; memory vs duration tradeoff.
- **SageMaker:** Multi-instance endpoint, auto-scaling policies on invocations or latency.
- **API Gateway:** Caching rarely helps for unique bodies; usage plans for tiering.
- **Egress:** NAT Gateway charges if Lambda is in a VPC only for fixed egress; hybrid egress to Azure is standard internet path unless using private link patterns.
