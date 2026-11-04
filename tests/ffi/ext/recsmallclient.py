# An extension imported on a 512 KiB thread derives its native stack floor from that thread.
# Modest recursion completes; deeper recursion raises and unwinds instead of overflowing the stack.
import threading

results: list[str] = []
failures: list[str] = []


def run() -> None:
    import recguard
    results.append(f"shallow recursion {recguard.depth(400)}")
    original = recguard.get_limit()
    recguard.set_limit(300000)
    try:
        recguard.climb()
    except RecursionError:
        results.append("deep recursion caught on the importing thread")
    finally:
        recguard.set_limit(original)
    results.append(f"recovered {recguard.depth(400)} {recguard.get_limit()}")


def worker_run() -> None:
    try:
        run()
    except BaseException as error:
        failures.append(f"worker failed: {type(error).__name__}: {error}")


threading.stack_size(512 * 1024)
worker = threading.Thread(target=worker_run)
worker.start()
worker.join()
print("\n".join(results))
assert not failures, failures
assert len(results) == 3, results
