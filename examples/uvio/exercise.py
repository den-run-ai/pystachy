"""Exercise an owned libuv loop against the independent peer in check.py."""

import sys
from uvio import Completion, Loop, uvio_step


def collect(loop: Loop, count: int) -> list[Completion]:
    results: list[Completion] = []
    while len(results) < count:
        results.extend(loop.run_once())
    assert len(results) == count
    return results


def exchange(port: int, payload: bytes) -> bytes:
    with Loop(byte_limit=65536) as loop:
        request = loop.submit("127.0.0.1", port, payload)
        event = collect(loop, 1)[0]
        assert event.request_id == request
        assert event.status == 0, event.error_name()
        return event.data


def main() -> None:
    port = int(sys.argv[1])
    refused = int(sys.argv[2])
    repetitions = int(sys.argv[3])
    for _ in range(repetitions):
        # Requests use temporary managed storage; callbacks may run after its collection.
        assert exchange(port, b"E" + bytes([0, 255, 65, 0, 66])) == bytes([0, 255, 65, 0, 66])
        assert exchange(port, b"") == b""
        assert exchange(port, b"E" + b"x" * 32768) == b"x" * 32768
    print("binary, empty, fragmented replies", repetitions)

    with Loop(capacity=2, byte_limit=64) as loop:
        slow = loop.submit("127.0.0.1", port, b"hold", 3000)
        fast = loop.submit("127.0.0.1", port, b"Efast", 3000)
        first = collect(loop, 1)[0]
        assert first.request_id == fast and first.data == b"fast" and first.status == 0
        release = loop.submit("127.0.0.1", port, b"release", 3000)
        rest = collect(loop, 2)
        for event in rest:
            assert event.status == 0
            if event.request_id == slow:
                assert event.data == b"slow"
            else:
                assert event.request_id == release and event.data == b"released"
    print("completion order follows readiness")

    with Loop(capacity=2, byte_limit=64) as loop:
        canceled = loop.submit("127.0.0.1", port, b"wait", 3000)
        assert loop.cancel(canceled)
        assert not loop.cancel(canceled)
        deadline = loop.submit("127.0.0.1", port, b"wait", 50)
        try:
            loop.submit("127.0.0.1", port, b"Efull")
            raise AssertionError("capacity must include closing requests")
        except OSError as error:
            assert str(error) == "EBUSY"
        for event in collect(loop, 2):
            if event.request_id == canceled:
                assert event.error_name() == "ECANCELED"
            else:
                assert event.request_id == deadline and event.error_name() == "ETIMEDOUT"
        try:
            loop.cancel(canceled)
            raise AssertionError("a consumed ID must not refer to a reused slot")
        except OSError as error:
            assert str(error) == "ENOENT"
    print("cancellation, deadlines, admission limits, stale IDs")

    with Loop(capacity=1, byte_limit=16) as loop:
        exact = loop.submit("127.0.0.1", port, b"limit")
        event = collect(loop, 1)[0]
        assert event.request_id == exact and event.status == 0 and event.data == b"x" * 16
        overflow = loop.submit("127.0.0.1", port, b"overflow")
        # Completed but unconsumed results also retain their admission slot.
        while uvio_step(loop._open(), 1) == 0:
            pass
        try:
            loop.submit("127.0.0.1", port, b"Efull")
            raise AssertionError("queued results must retain capacity")
        except OSError as error:
            assert str(error) == "EBUSY"
        event = collect(loop, 1)[0]
        assert event.request_id == overflow and event.error_name() == "ENOBUFS"
        assert event.data == b"x" * 16
        failed = loop.submit("127.0.0.1", refused, b"Erefused")
        event = collect(loop, 1)[0]
        assert event.request_id == failed and event.error_name() == "ECONNREFUSED"
    print("response limits, queued-result pressure, connection errors")

    for _ in range(repetitions):
        loop = Loop(capacity=2)
        loop.submit("127.0.0.1", port, b"wait", 60000)
        loop.submit("127.0.0.1", port, b"Eclosing", 60000)
        loop.close()
        loop.close()
        try:
            loop.run_once(False)
            raise AssertionError("a closed loop must reject operations")
        except ValueError as error:
            assert str(error) == "loop is closed"
    print("active close and idempotent cleanup", repetitions)

    with Loop(byte_limit=16) as loop:
        for timeout in [0, -1, 60001]:
            try:
                loop.submit("127.0.0.1", port, b"E", timeout)
                raise AssertionError("invalid deadline accepted")
            except ValueError:
                pass
        for bad_port in [-1, 0, 65536, 4294967297]:
            try:
                loop.submit("127.0.0.1", bad_port, b"E")
                raise AssertionError("invalid port accepted")
            except ValueError:
                pass
        try:
            loop.submit("127.0.0.1", port, b"x" * 17)
            raise AssertionError("large input accepted")
        except ValueError:
            pass
        try:
            loop.submit("localhost", port, b"E")
            raise AssertionError("DNS must not silently enter this numeric-address prototype")
        except OSError:
            pass
        assert loop.run_once(False) == []
    print("input validation and idle polling")


if __name__ == "__main__":
    main()
