"""Time warm regex and replacement-template caches, compiled or under CPython.

Usage: python3 tools/re_cache_bench.py
       pystachy build tools/re_cache_bench.py -o build/re-cache-bench
       build/re-cache-bench

Each operation reports the median CPU time per call over seven rounds of 400,000 calls.
CPU time excludes time waiting for other compiler/test processes on a shared machine.
The equal-fresh case includes allocation of a new string equal to the cached pattern.
All versions must print the same checksum; timings have no pass/fail thresholds.
"""
import re
import time

N = 400000


def main() -> None:
    pattern = "([A-Z][A-Z0-9]{1,20})"
    rx = re.compile(pattern, re.I)
    match = rx.match("CACHE123")
    assert match is not None
    match.expand(r"<\1>")
    checksum = 0
    for operation in ["compile", "equal-fresh", "expand"]:
        times: list[float] = []
        for _ in range(7):
            start = time.process_time()
            if operation == "compile":
                for _i in range(N):
                    checksum += re.compile(pattern, re.I).groups
            elif operation == "equal-fresh":
                for _i in range(N):
                    checksum += re.compile(("." + pattern)[1:], re.I).groups
            else:
                for _i in range(N):
                    checksum += len(match.expand(r"<\1>"))
            times.append((time.process_time() - start) * 1e9 / N)
        times.sort()
        print(f"{operation:12} {times[3]:.1f} ns")
    print("checksum", checksum)


if __name__ == "__main__":
    main()
