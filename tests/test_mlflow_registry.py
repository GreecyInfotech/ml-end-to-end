from src.mlflow_registry import MLFLOW_AVAILABLE, registry_enabled, tracking_uri


def test_mlflow_enabled_environment_override(monkeypatch):
    cfg = {"mlflow": {"enabled": True}}

    monkeypatch.setenv("MLFLOW_ENABLED", "false")
    assert registry_enabled(cfg) is False

    monkeypatch.setenv("MLFLOW_ENABLED", "true")
    assert registry_enabled(cfg) is MLFLOW_AVAILABLE


def test_tracking_uri_environment_override(monkeypatch, tmp_path):
    cfg = {"mlflow": {"tracking_uri": "sqlite:///configured.db"}}
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "https://mlflow.example.test")

    assert tracking_uri(cfg, tmp_path) == "https://mlflow.example.test"