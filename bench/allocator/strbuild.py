# medium strings: join/format/concat of 100..20000-byte strings, as text processing does
import sys
import time


def main() -> None:
    reps = int(sys.argv[1])
    t0 = time.perf_counter()
    words = [str(i) * (1 + i % 7) for i in range(1000)]
    total = 0
    for r in range(reps):
        line = ",".join(words[(r % 10):(r % 10) + 300])
        up = line.upper()
        parts = up.split(",")
        total += len(parts) + len(up)
        s = ""
        for p in parts[:60]:
            s += p + ";"
        total += len(s.replace(";", "::"))
        total += len(f"{r}:{line[:200]}:{len(s)}")
    print(total)
    print("TIME", time.perf_counter() - t0, file=sys.stderr)


main()
