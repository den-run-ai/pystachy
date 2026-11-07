"""CPython-only wrapper lifetime regressions; check.py supplies the bridge and peer."""

import sys
import threading

import uvio


def main():
    port = int(sys.argv[1])
    loop = uvio.Loop(capacity=1)
    failures = []

    def foreign():
        for action in [lambda: loop.run_once(False), lambda: loop.cancel(1),
                       lambda: loop.submit("127.0.0.1", port, b"Ewrong"), loop.close]:
            try:
                action()
            except RuntimeError as error:
                failures.append(str(error))
            else:
                failures.append("owner check missing")

    thread = threading.Thread(target=foreign)
    thread.start()
    thread.join(3)
    assert not thread.is_alive()
    assert failures == ["loop belongs to another thread"] * 4
    assert loop.run_once(False) == []

    original_close = uvio.uvio_close

    def interrupted(handle):
        assert original_close(handle) == 0
        raise KeyboardInterrupt("signal on foreign-call return")

    uvio.uvio_close = interrupted
    try:
        try:
            loop.close()
        except KeyboardInterrupt:
            pass
        else:
            raise AssertionError("expected injected signal")
        # Never dereference a stale handle, even when testing a broken implementation.
        handle = loop._handle
        loop._handle = 0
        assert handle == 0, "freed loop handle survived the signal"
    finally:
        uvio.uvio_close = original_close
    loop.close()

    with uvio.Loop(capacity=1) as loop:
        original_step = uvio.uvio_step

        def reentrant(handle, block):
            try:
                loop.close()
            except RuntimeError as error:
                assert str(error) == "loop operation is already in progress"
            else:
                raise AssertionError("reentrant close was allowed")
            return original_step(handle, block)

        uvio.uvio_step = reentrant
        try:
            assert loop.run_once(False) == []
        finally:
            uvio.uvio_step = original_step

        loop.submit("127.0.0.1", port, b"Ecopy")
        original_copy = uvio.bytes_at

        def failed_copy(address, size):
            raise MemoryError("injected copy failure")

        uvio.bytes_at = failed_copy
        try:
            while True:
                try:
                    loop.run_once()
                except MemoryError:
                    break
        finally:
            uvio.bytes_at = original_copy
        # The finally block releases capacity even when bytes_at raises.
        request = loop.submit("127.0.0.1", port, b"Ereused")
        results = []
        while not results:
            results = loop.run_once()
        assert [(event.request_id, event.status, event.data) for event in results] == [(request, 0, b"reused")]
    print("hosted owner-thread, interrupted close, reentrancy and copy-failure cleanup passed")


if __name__ == "__main__":
    main()
