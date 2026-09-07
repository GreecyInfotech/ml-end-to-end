import json

import pytest

from streaming.kafka_predictor import predict_event


def test_predict_event_wraps_json_prediction():
    payload = json.dumps({"arrival_hour": 8}).encode("utf-8")

    output = json.loads(predict_event(lambda event: {"status": "DELAYED"}, payload))

    assert output == {"input": {"arrival_hour": 8}, "prediction": {"status": "DELAYED"}}


def test_predict_event_rejects_invalid_json():
    with pytest.raises(json.JSONDecodeError):
        predict_event(lambda event: {}, b"not-json")