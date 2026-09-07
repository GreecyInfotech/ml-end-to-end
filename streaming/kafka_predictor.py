from __future__ import annotations

import json
import os
from typing import Any, Callable

try:
    from confluent_kafka import Consumer, Producer
except ImportError:  # pragma: no cover
    Consumer = None
    Producer = None


def require_kafka() -> None:
    if Consumer is None or Producer is None:
        raise RuntimeError("Install confluent-kafka to enable Kafka streaming")


def predict_event(predict_fn: Callable[[dict[str, Any]], dict[str, Any]], raw_value: bytes) -> bytes:
    event = json.loads(raw_value.decode("utf-8"))
    result = predict_fn(event)
    return json.dumps({"input": event, "prediction": result}).encode("utf-8")


def run_consumer(
    predict_fn: Callable[[dict[str, Any]], dict[str, Any]],
    input_topic: str,
    output_topic: str,
    bootstrap_servers: str | None = None,
    group_id: str = "vessel-delay-predictor",
) -> None:
    require_kafka()
    consumer = Consumer({
        "bootstrap.servers": bootstrap_servers or os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
        "group.id": group_id,
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
    })
    producer = Producer({"bootstrap.servers": bootstrap_servers or os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")})
    consumer.subscribe([input_topic])
    try:
        while True:
            message = consumer.poll(1.0)
            if message is None:
                continue
            if message.error():
                raise RuntimeError(str(message.error()))
            producer.produce(output_topic, value=predict_event(predict_fn, message.value()))
            producer.flush()
            consumer.commit(message=message)
    finally:
        consumer.close()