"""gentable: a synthetic table for column.py, the same on every run.

usage: python3 gentable.py N [SEP] > TABLE
Each of the N lines is a row of 7 fields separated by SEP (a tab by default): an id, a date, a
host, a request path, a status code, a byte count and a duration in ms, of varied widths.
"""
import sys

HOSTS = ["db1", "cache-eu-west-2", "web7", "auth", "search-replica-03", "queue", "api-gateway"]
PATHS = ["/", "/login", "/api/v2/items", "/static/app.js", "/search?q=pystachy", "/health",
         "/api/v2/items/48151623/history", "/favicon.ico", "/admin/reports/2026/10"]

seed = 20261013


def rand(n: int) -> int:
    # an int in [0, n): a 31-bit linear congruential generator (glibc's constants), whose products
    # stay in 64 bits, as Pystachy's ints do
    global seed
    seed = (seed * 1103515245 + 12345) % 2147483648
    return (seed >> 8) % n


def row(i: int, sep: str) -> str:
    fields = [str(i), f"2026-10-{1 + rand(28):02d}", HOSTS[rand(len(HOSTS))], PATHS[rand(len(PATHS))],
              str([200, 200, 200, 304, 404, 500][rand(6)]), str(rand(10) ** rand(6)), f"{rand(100000) / 100:.2f}"]
    return sep.join(fields)


def main() -> None:
    n = int(sys.argv[1])
    sep = sys.argv[2] if len(sys.argv) > 2 else "\t"
    for i in range(n):
        print(row(i, sep))


if __name__ == "__main__":
    main()
