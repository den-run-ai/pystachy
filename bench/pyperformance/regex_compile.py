
"""Benchmark how quickly Python's regex implementation can compile regexes.

We bring in all the regexes used by the other regex benchmarks, capture them by
stubbing out the re module, then compile those regexes repeatedly. We muck with
the re module's caching to force it to recompile every regex we give it.
"""

# Python imports
import re
import time  # Pystachy port: time.perf_counter() is pyperf.perf_counter(); pyperf is not imported

TIMED: list[float] = []  # Pystachy port: the seconds of each timed part


# Pystachy port: the capture is read from a record. Upstream replaces re.compile(),
# re.search() and re.sub() with functions that note their regexes, and runs its copies of
# the regex_effbot and regex_v8 benchmarks; a module's functions cannot be replaced.
# data/regex_compile.txt holds what upstream captures, in order: each line is "s", the
# flags and a regex's text, or "p", a compiled pattern's flags and text where the regex
# captured was a compiled pattern, which is compiled here once and given to the loop.
def capture_regexes(path):
    regexes: list[tuple[str, int, re.Pattern | None]] = []
    with open(path, encoding="utf-8") as record:
        for line in record:
            fields = line.rstrip("\n").split("\t", 2)
            if fields[0] == "p":
                regexes.append((fields[2], 0, re.compile(fields[2], int(fields[1]))))
            else:
                regexes.append((fields[2], int(fields[1]), None))
    return regexes


def bench_regex_compile(loops, regexes):
    range_it = range(loops)
    t0 = time.perf_counter()  # Pystachy port: time.perf_counter() is pyperf.perf_counter()

    for _ in range_it:
        # Pystachy port: a captured compiled pattern is the entry's third item
        for regex, flags, compiled in regexes:
            re.purge()
            # ignore result (compiled regex)
            if compiled is None:
                re.compile(regex, flags)
            else:
                re.compile(compiled, flags)

    TIMED.append(time.perf_counter() - t0)  # Pystachy port: the seconds, which upstream returns


if __name__ == "__main__":
    # Pystachy port: a deterministic main replaces pyperf.Runner: argv[1] is the
    # number of loops, argv[2] how many of the captured regexes to compile (all 4,267
    # by default) and argv[3] the record (bench/pyperformance/data/regex_compile.txt from
    # the repository root by default). What each compilation gives is summed outside the
    # timer, and the time goes to stderr.
    import sys
    loops = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    path = sys.argv[3] if len(sys.argv) > 3 else "bench/pyperformance/data/regex_compile.txt"
    regexes = capture_regexes(path)
    if len(sys.argv) > 2:
        regexes = regexes[:int(sys.argv[2])]
    bench_regex_compile(loops, regexes)
    print("seconds", sum(TIMED), file=sys.stderr)
    groups = 0
    flags_seen = 0
    same = 0
    chars = 0
    for regex, flags, compiled in regexes:
        re.purge()
        if compiled is None:
            pattern = re.compile(regex, flags)
        else:
            pattern = re.compile(compiled, flags)
            if pattern is compiled:
                same += 1
        groups += pattern.groups
        flags_seen += pattern.flags
        chars += len(pattern.pattern)
    print("regex_compile", loops, len(regexes), same, groups, flags_seen, chars)
