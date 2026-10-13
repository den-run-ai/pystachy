"""route: send each event of a trace or log to the first destination whose rule matches its
name, and count the events per destination.

usage: python3 route.py RULES EVENTS [--no-cache | --precompiled]
       pystachy build route.py -o route && ./route RULES EVENTS

RULES holds one rule per line, "PATTERN DESTINATION", in order (# starts a comment): a pattern is
fnmatch's, shell-style and case-sensitive (fnmatchcase), matched against an event's whole name,
and the first rule that matches routes the event; an event that none matches is "unrouted".
EVENTS holds one event per line: its name, then a tab and the rest. An event's destination
depends only on its name, and names repeat (a service emits a few hundred span names millions of
times), so route() is cached: lru_cache keeps the rules of the 4,096 names seen last.

fnmatch keeps each pattern's compiled regular expression in a cache of its own, so --no-cache,
which routes each event again (route.__wrapped__), still compiles a pattern once; --precompiled
compiles each rule's pattern once, itself, and routes each event through those matchers.
"""

import re
import sys
from fnmatch import _compile_pattern, fnmatchcase, translate
from functools import lru_cache

PATTERNS: list[str] = []
DESTINATIONS: list[str] = []


def load(lines: list[str]) -> None:
    for line in lines:
        fields = line.split("#", 1)[0].split()
        if len(fields) == 2:
            PATTERNS.append(fields[0])
            DESTINATIONS.append(fields[1])


@lru_cache(maxsize=4096)
def route(name: str) -> int:
    # the index of the first rule whose pattern matches name, or -1
    for i in range(len(PATTERNS)):
        if fnmatchcase(name, PATTERNS[i]):
            return i
    return -1


def main() -> None:
    if len(sys.argv) < 3:
        print("usage: route.py RULES EVENTS [--no-cache | --precompiled]", file=sys.stderr)
        sys.exit(2)
    mode = sys.argv[3] if len(sys.argv) > 3 else ""
    with open(sys.argv[1]) as f:
        load(f.readlines())
    matchers = [re.compile(translate(p)).match for p in PATTERNS]
    counts = [0] * (len(PATTERNS) + 1)  # (the last: unrouted)
    names: dict[str, bool] = {}
    events = 0
    with open(sys.argv[2]) as f:
        for line in f:
            name = line.split("\t", 1)[0]
            events += 1
            if mode == "--precompiled":
                k = -1
                for i in range(len(matchers)):
                    if matchers[i](name) is not None:
                        k = i
                        break
            elif mode == "--no-cache":
                k = route.__wrapped__(name)
            else:
                k = route(name)
            counts[k] += 1
            names[name] = True
    print(f"{events} events, {len(names)} names, {len(PATTERNS)} rules")
    totals: dict[str, int] = {}
    for i in range(len(PATTERNS)):
        totals[DESTINATIONS[i]] = totals.get(DESTINATIONS[i], 0) + counts[i]
    totals["unrouted"] = counts[-1]
    for d in sorted(totals, key=lambda d: (-totals[d], d)):
        print(f"{totals[d]:9} {d}")
    if mode == "":
        print("route:", route.cache_info())
    if mode != "--precompiled":
        print("patterns:", _compile_pattern.cache_info())


if __name__ == "__main__":
    main()
