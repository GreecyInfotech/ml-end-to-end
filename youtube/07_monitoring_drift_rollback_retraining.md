# Episode 7: Monitoring, Drift, Troubleshooting, Rollback, and Retraining

**Duration:** 42 minutes

## Business Problem

Production data changes. The operating environment can drift, labels can mature slowly, and a model can degrade after release.

## Video Flow

1. Run the quality and drift monitor.
2. Explain PSI, missingness drift, and unavailable features.
3. Show Prometheus and Grafana runtime metrics.
4. Preview evidence-based retraining decisions.
5. Demonstrate guarded retraining.
6. Explain rollback and incident response.

## Live Demo

```powershell
python -m monitoring.monitor --reference data/raw/vessels.csv --current data/raw/vessels.csv
Get-Content data/predictions/monitoring_report.json
python -m src.retrain --trigger scheduled --reason "Weekly refresh" --dry-run
```

Observe:

- CPU
- Memory
- Throughput
- Errors
- Availability
- P50/P95/P99 latency
- Error budget
- SLO burn rate

## Retraining Triggers

- Data drift
- Model performance degradation
- Business requirement change
- New data
- Scheduled retraining
- Feature change
- Label change

## Rollback Demo

```powershell
python -c "from src.config import load_config, ROOT; from src.mlflow_registry import rollback_alias; print(rollback_alias(load_config(), ROOT, version='18', reason='Elevated false-negative rate'))"
```

## Incident Lesson

Drift is an investigation signal, not an automatic promotion decision. Preserve the monitoring report, request IDs, traces, model version, and decision reason.
