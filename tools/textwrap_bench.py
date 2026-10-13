"""Reproducible textwrap and fnmatch timings, including warm result-cache hits.

usage: python3 tools/textwrap_bench.py [--time] [--cpu]
       pystachy build tools/textwrap_bench.py -o textwrap_bench && ./textwrap_bench --time

--cpu uses process CPU time, excluding time spent waiting for other processes on a busy host.
The inputs are tools/re_bench.py's 200 ASCII paragraphs and indented blocks. The checksum
must match CPython's. Timings are the median of five rounds, per call; cache warming is
outside the timed region. cached_fill demonstrates caching immutable results with a bounded
working set: it holds these 200 paragraphs at one width, and reports its hit/miss counts.
fnmatch's cache holds compiled patterns rather than match results. The no-cache comparison
bypasses fnmatch's _compile_pattern wrapper. Both implementations' re.compile caches may still
reuse a translated regular expression; this measures translation and the re cache lookup, not
fresh regex compilation.
"""
import sys
import time
from fnmatch import _compile_pattern, fnmatchcase
from functools import lru_cache
from textwrap import dedent, fill, indent, shorten, wrap

from re_bench import inputs

PATTERNS = ["auth.*", "*.failed", "http.request.[45]??", "db.*.slow", "*", "a?c",
            "[!a-z]*", "[]]", "[a-cx-z]", "prefix*suffix"]
NAMES = ["auth.login", "payments.failed", "http.request.404", "db.query.slow", "anything",
         "abc", "123", "]", "b", "prefix.middle.suffix"]


@lru_cache(maxsize=256)
def cached_fill(text: str, width: int) -> str:
    return fill(text, width)


def main() -> None:
    paras, blocks = inputs(200)
    check = 0
    for text in paras:
        check += len(wrap(text, 70)) + len(fill(text, 70)) + len(shorten(text, 70))
        check += len(cached_fill(text, 70))
    for text in blocks:
        check += len(dedent(text)) + len(indent(text, "> "))
    for name in NAMES:
        for pattern in PATTERNS:
            check += int(fnmatchcase(name, pattern))
            check += int(_compile_pattern.__wrapped__(pattern)(name) is not None)
    print("checksum", check)
    if "--time" not in sys.argv:
        return
    cpu = "--cpu" in sys.argv
    for operation in ["wrap", "fill", "shorten", "dedent", "indent", "cached_fill.hit",
                      "fnmatchcase.hit", "fnmatchcase.no-cache"]:
        rounds: list[float] = []
        for _ in range(5):
            t = time.process_time() if cpu else time.perf_counter()
            if operation == "wrap":
                for text in paras:
                    wrap(text, 70)
            elif operation == "fill":
                for text in paras:
                    fill(text, 70)
            elif operation == "shorten":
                for text in paras:
                    shorten(text, 70)
            elif operation == "dedent":
                for text in blocks:
                    dedent(text)
            elif operation == "indent":
                for text in blocks:
                    indent(text, "> ")
            elif operation == "cached_fill.hit":
                for _ in range(100):
                    for text in paras:
                        cached_fill(text, 70)
            elif operation == "fnmatchcase.hit":
                for _ in range(20):
                    for name in NAMES:
                        for pattern in PATTERNS:
                            fnmatchcase(name, pattern)
            else:
                for _ in range(20):
                    for name in NAMES:
                        for pattern in PATTERNS:
                            _compile_pattern.__wrapped__(pattern)(name)
            calls = 20000 if operation == "cached_fill.hit" else 2000 if operation.startswith("fnmatchcase") else 200
            elapsed = (time.process_time() if cpu else time.perf_counter()) - t
            rounds.append(elapsed / calls * 1e6)
        rounds.sort()
        print(f"{operation:30} {rounds[2]:8.3f} us")
    print("cached_fill:", cached_fill.cache_info())


if __name__ == "__main__":
    main()
