# Episode 10: Local to Azure, AWS, and GCP Cloud Migration

**Duration:** 42 minutes

## Business Problem

The application should move from local Docker and SQLite to managed cloud services without changing the model contract or operational controls.

## Video Flow

1. Review the local service boundaries.
2. Map each role to Azure, AWS, and GCP.
3. Replace local MLflow SQLite with managed PostgreSQL.
4. Replace local artifacts with object storage.
5. Move secrets into a cloud secret manager.
6. Deploy API and gateway behind private networking and an authenticated edge.
7. Schedule training and monitoring jobs.
8. Configure centralized metrics, logs, and traces.
9. Validate readiness, prediction, drift, and rollback.

## Service Mapping

| Local capability | Azure | AWS | GCP |
|---|---|---|---|
| API/Gateway | Azure Container Apps | ECS/Fargate | Cloud Run |
| Training job | Container Apps Job or Azure ML | Batch or scheduled ECS | Cloud Run Job or Vertex AI |
| Monitoring job | Container Apps Job | EventBridge plus Batch/ECS | Cloud Scheduler plus Cloud Run Job |
| MLflow metadata | Azure Database for PostgreSQL | RDS PostgreSQL | Cloud SQL PostgreSQL |
| Model artifacts | Azure Blob Storage | S3 | GCS |
| Streaming | Event Hubs Kafka endpoint | Amazon MSK | Managed Kafka or Pub/Sub adapter |
| Secrets | Key Vault | Secrets Manager | Secret Manager |
| Observability | Azure Monitor | CloudWatch | Cloud Monitoring |

## Live Demo

```powershell
Get-Content cloud_migration.md
Get-Content deploy/README.md
Get-Content deploy/azure/container-app.yaml
Get-Content deploy/aws/ecs-task-definition.json
Get-Content deploy/gcp/cloud-run.yaml
```

Validate the local contract before migration:

```powershell
python -m pytest -q
docker compose --profile observability config --quiet
python -m src.retrain --trigger scheduled --reason "Migration readiness" --dry-run
```

## Production Migration Sequence

1. Build and scan the image.
2. Push it to the cloud registry.
3. Provision PostgreSQL, object storage, secrets, networking, and messaging.
4. Configure `MLFLOW_TRACKING_URI` and `MLFLOW_REGISTRY_URI`.
5. Run training against the managed registry.
6. Verify the champion alias.
7. Deploy the private model API.
8. Deploy the authenticated gateway.
9. Configure readiness probes.
10. Schedule monitoring and retraining.
11. Configure centralized dashboards and alerts.
12. Run canary predictions.
13. Verify rollback before expanding traffic.

## Closing Takeaway

Cloud migration is primarily a boundary and operations exercise. Preserve the feature contract, model registry semantics, gateway contract, monitoring signals, and rollback process while replacing local infrastructure with managed services.
