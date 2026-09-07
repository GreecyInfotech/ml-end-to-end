from src.feature_store import feature_contract, feature_contract_hash


def test_feature_contract_hash_is_deterministic():
    assert feature_contract_hash("v2") == feature_contract_hash("v2")
    assert feature_contract_hash("v2") != feature_contract_hash("v3")


def test_feature_contract_contains_model_inputs():
    contract = feature_contract("v2")

    assert "arrival_hour" in contract["numeric_features"]
    assert "weather" in contract["categorical_features"]
    assert "is_peak_hour" in contract["derived_rules"]
