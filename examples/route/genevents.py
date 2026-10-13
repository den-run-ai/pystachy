"""genevents: a synthetic trace for route.py, the same on every run.

usage: python3 genevents.py N MODE > EVENTS
Each line is an event: its name, a tab, a timestamp and a duration. A name is
SERVICE.OPERATION.OUTCOME, the services and operations drawn with skewed weights (a few are hot),
so a long trace repeats a few hundred names; MODE "unique" appends a request number to each
operation (auth.login-17.failed), so that no two events share a name.
"""
import sys

SERVICES = ["auth", "payments", "billing", "tool", "http", "db", "cache", "queue", "search", "gc",
            "frontend", "worker"]
OPERATIONS = ["login", "logout", "refresh", "charge", "refund", "invoice", "search", "read",
              "write", "edit", "request", "query", "get", "set", "publish", "consume", "debug",
              "render", "sync", "upload"]
OUTCOMES = ["started", "completed", "completed", "completed", "failed", "retried", "timeout",
            "miss", "200", "404", "503", "locked", "slow"]

seed = 20261013


def rand(n: int) -> int:
    # an int in [0, n): a 31-bit linear congruential generator (glibc's constants), whose products
    # stay in 64 bits, as Pystachy's ints do
    global seed
    seed = (seed * 1103515245 + 12345) % 2147483648
    return (seed >> 8) % n


def skewed(n: int) -> int:
    # an index in [0, n), small ones far more likely: the least of three draws
    return min(rand(n), rand(n), rand(n))


def event(i: int, unique: bool) -> str:
    # the name of event i
    service = SERVICES[skewed(len(SERVICES))]
    operation = OPERATIONS[skewed(len(OPERATIONS))] + (f"-{i}" if unique else "")
    return f"{service}.{operation}.{OUTCOMES[rand(len(OUTCOMES))]}"


def main() -> None:
    n = int(sys.argv[1])
    unique = len(sys.argv) > 2 and sys.argv[2] == "unique"
    for i in range(n):
        name = event(i, unique)
        print(f"{name}\t{1760000000 + i}\t{rand(5000)}")


if __name__ == "__main__":
    main()
