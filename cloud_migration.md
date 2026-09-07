# Local MLOps Cloud Migration Guide

## 1. Migration Boundary

The local system is container-first and provider-neutral:

```text
API container       -> online prediction service
Training container  -> candidate training and MLflow registration
Monitor container   -> quality and drift report
MLflow              -> experiment tracking and model registry
Kafka adapter       -> optional real-time prediction stream
```

The cloud migration keeps these contracts unchanged. Only compute placement, identity, storage, registry hosting, and networking change.

## 2. Azure

Recommended mapping:

- API: Azure Container Apps
- Training: Container Apps Job or Azure Machine Learning job
- Monitoring: scheduled Container Apps Job
- Registry: protected MLflow deployment on Container Apps or AKS
- Artifacts: Azure Blob Storage
- Registry database: Azure Database for PostgreSQL
- Kafka-compatible stream: Azure Event Hubs Kafka endpoint or managed Kafka
- Secrets: Azure Key Vault
- Identity: managed identity
- Observability: Azure Monitor, Application Insights, and Log Analytics

Template: `deploy/azure/container-app.yaml`.

Use `/ready` for readiness and `/health` for liveness. Store MLflow URIs and Kafka credentials in Key Vault-backed Container Apps secrets. Use private networking for registry, database, storage, and messaging where required.

## 3. AWS

Recommended mapping:

- API: ECS/Fargate or App Runner
- Training: AWS Batch or scheduled ECS task
- Monitoring: EventBridge plus ECS/Batch task
- Registry: MLflow on ECS/EKS
- Artifacts: S3
- Registry database: RDS PostgreSQL
- Kafka: Amazon MSK
- Secrets: Secrets Manager
- Identity: task roles
- Observability: CloudWatch, X-Ray, and managed Prometheus/Grafana where required

Template: `deploy/aws/ecs-task-definition.json`.

Use task roles instead of embedded AWS credentials. Configure the ECS service health check against `/ready`, private subnets for data services, and security groups that restrict registry/database access.

## 4. GCP

Recommended mapping:

- API: Cloud Run or GKE
- Training: Cloud Run Job or Vertex AI job
- Monitoring: Cloud Scheduler plus Cloud Run Job
- Registry: MLflow on Cloud Run/GKE
- Artifacts: GCS
- Registry database: Cloud SQL PostgreSQL
- Kafka: managed Kafka or a Pub/Sub adapter
- Secrets: Secret Manager
- Identity: service accounts with least privilege
- Observability: Cloud Monitoring, Cloud Logging, and managed Prometheus

Template: `deploy/gcp/cloud-run.yaml`.

Use a dedicated runtime service account, Secret Manager references, VPC connectors or private networking for managed services, and Cloud Run startup/liveness probes.

## 5. Common Deployment Contract

Required configuration:

```text
VESSEL_DELAY_IMAGE
MLFLOW_ENABLED
MLFLOW_TRACKING_URI
MLFLOW_REGISTRY_URI
KAFKA_BOOTSTRAP_SERVERS (streaming only)
```

Required operational checks:

- `/health` returns model source and registry version.
- `/ready` returns `200` and feature contract status `MATCH`.
- `/metrics` reports latency, error rate, uptime, and model identity.
- Monitoring status is `PASS` or explicitly reviewed before release.
- MLflow `champion` alias points to the approved version.
- Object storage and registry database are durable and backed up.
- The previous champion is available for rollback.

## 6. Migration Sequence

1. Build the image locally and run the test suite.
2. Push the image to ACR, ECR, or Artifact Registry.
3. Provision managed PostgreSQL, object storage, secrets, identity, and registry.
4. Configure MLflow tracking and registry URIs.
5. Run training as a cloud job and verify the promotion gate.
6. Deploy the API using the provider template.
7. Run monitoring against a versioned reference dataset.
8. Configure Kafka topics and consumer identity if streaming is enabled.
9. Deploy canary capacity and verify health, readiness, feature contract, latency, and error rate.
10. Expand traffic only after observation and rollback testing.

## 7. Security and Reliability

- Use managed identity, task roles, or service accounts.
- Never embed cloud keys, registry passwords, or Kafka credentials in images.
- Use TLS for API, MLflow, database, object storage, and Kafka connections.
- Restrict registry writes to training/release identities.
- Give serving identities read-only model access.
- Keep the API stateless and externalize model/registry state.
- Use private endpoints or private networking for control-plane services.
- Export application metrics and logs to the provider observability platform.
- Test rollback by moving the MLflow alias to a known approved version.

## 8. Scope Boundary

These artifacts prepare the application for migration; they do not provision cloud resources or deploy images. Target subscriptions/projects, regions, network topology, registry endpoints, and credentials must be supplied before a live deployment.
