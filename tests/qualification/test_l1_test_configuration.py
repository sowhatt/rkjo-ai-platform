import json
import pytest

from scripts.l1_test import dedicated_ports


def rows():
    return [
        {"Project": "rkjo-l1-ci-test", "Service": "postgres", "Health": "healthy",
         "Publishers": [{"TargetPort": 5432, "PublishedPort": 31432, "URL": "127.0.0.1"}]},
        {"Project": "rkjo-l1-ci-test", "Service": "rabbitmq", "Health": "healthy",
         "Publishers": [
             {"TargetPort": 4369, "PublishedPort": 0, "URL": ""},
             {"TargetPort": 15672, "PublishedPort": 0, "URL": ""},
             {"TargetPort": 5672, "PublishedPort": 31672, "URL": "127.0.0.1"}]},
    ]


@pytest.mark.parametrize("encoding", ["array", "ndjson"])
def test_amqp_selection_ignores_unpublished_erlang_and_management_ports(encoding):
    data = rows()
    output = json.dumps(data) if encoding == "array" else "\n".join(json.dumps(row) for row in data)
    assert dedicated_ports(output, "rkjo-l1-ci-test") == {"postgres": 31432, "rabbitmq": 31672}


def test_missing_localhost_amqp_mapping_is_rejected():
    data = rows()
    data[1]["Publishers"][-1]["URL"] = "0.0.0.0"
    with pytest.raises(ValueError, match="localhost publisher required"):
        dedicated_ports(json.dumps(data), "rkjo-l1-ci-test")
