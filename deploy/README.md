# Cloud Migration Deployment Artifacts

These templates preserve the local Docker contract while mapping the system to Azure, AWS, or GCP. They are intentionally configuration-driven: registry URIs, image names, storage, secrets, and Kafka endpoints are supplied by the target platform.

## Services

| Local role | Azure | AWS | GCP |
|---|---|---|---|
| API | Azure Container Apps | ECS/Fargate | Cloud Run |
| Train | Container Apps Job or Azure ML job | AWS Batch or scheduled ECS task | Cloud Run Job or Vertex AI |
| Monitor | Container Apps Job | EventBridge + ECS/Batch | Cloud Scheduler + Cloud Run Job |
| Registry | Managed MLflow on ACA/AKS | Managed MLflow on ECS/EKS | Managed MLflow on Cloud Run/GKE |
| Object storage | Azure Blob Storage | S3 | GCS |
| Registry database | Azure Database for PostgreSQL | RDS PostgreSQL | Cloud SQL PostgreSQL |
| Kafka-compatible stream | Event Hubs Kafka endpoint | Amazon MSK | Managed Kafka or Pub/Sub adapter |

## Deployment sequence

1. Build and scan the image.
2. Push the same image to the provider registry.
3. Provision managed PostgreSQL, object storage, registry, secrets, and Kafka-compatible messaging.
4. Set `MLFLOW_TRACKING_URI`, `MLFLOW_REGISTRY_URI`, `MLFLOW_ENABLED`, and `KAFKA_BOOTSTRAP_SERVERS` through the platform secret/configuration service.
5. Run the training job and inspect the MLflow promotion gate.
6. Deploy the API with `/ready` as the readiness probe.
7. Schedule monitoring and retraining only after alert policy review.
8. Verify model version, feature contract hash, latency, error rate, and drift status.

The templates in this directory are starting points. Replace placeholder values and run each provider's validation tool before deployment.
