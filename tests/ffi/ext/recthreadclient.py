# An extension module imported by a thread other than the main one (#1015): the runtime takes the
# native stack's floor from the importing thread's own stack, the only one that may call it, so a
# recursion that this 4 MiB stack cannot hold raises RecursionError (CPython's twin reaches the
# limit) instead of overflowing it.
import threading

results: list[str] = []


def run() -> None:
    import recguard
    original = recguard.get_limit()
    recguard.set_limit(300000)
    try:
        recguard.climb()
    except RecursionError:
        results.append("deep recursion caught on the importing thread")
    finally:
        recguard.set_limit(original)
    results.append(f"recovered {recguard.depth(10)} {recguard.get_limit()}")


threading.stack_size(4 * 1024 * 1024)
worker = threading.Thread(target=run)
worker.start()
worker.join()
print("\n".join(results))
