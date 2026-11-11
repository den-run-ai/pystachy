"""Request parsing and timeout ownership without process-output capture."""
import latency


def test_timeouts_count_status_but_do_not_add_latency():
    endpoints: dict[str, latency.Endpoint] = {}
    skipped = latency.parse([
        "now GET /api 200 2.5 10", "now GET /api 504 - 0",
        "invalid", "now GET /api invalid 1 2",
    ], endpoints)
    assert skipped == 2
    assert len(endpoints) == 1
    endpoint = endpoints["GET /api"]
    assert endpoint.statuses == [200, 504]
    assert endpoint.latencies == [2.5]
    assert endpoint.sizes == [10]
    assert endpoint.timeouts == 1


def test_endpoint_lists_are_independent():
    endpoints: dict[str, latency.Endpoint] = {}
    assert latency.parse(["now GET /a 200 1 2", "now POST /b 500 3 4"], endpoints) == 0
    endpoints["GET /a"].latencies.append(9.0)
    assert endpoints["POST /b"].latencies == [3.0]
