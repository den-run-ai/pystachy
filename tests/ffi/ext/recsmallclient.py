# An extension module imported by a thread with a small stack (512 KiB): the runtime takes the
# native stack's floor and the depth that the stack holds (the trip's safe depth, a few dozen
# levels here) from the importing thread's stack, so a recursion past that depth which the stack
# holds completes, its entries looking at the stack pointer, and one that the stack cannot hold
# raises RecursionError (CPython's twin reaches the limit) instead of overflowing it.
import threading

results: list[str] = []


def run() -> None:
    import recguard
    results.append(f"past the safe depth {recguard.depth(400)}")
    original = recguard.get_limit()
    recguard.set_limit(300000)
    try:
        recguard.climb()
    except RecursionError:
        results.append("deep recursion caught on the importing thread")
    finally:
        recguard.set_limit(original)
    results.append(f"recovered {recguard.depth(400)} {recguard.get_limit()}")


threading.stack_size(512 * 1024)
worker = threading.Thread(target=run)
worker.start()
worker.join()
print("\n".join(results))
