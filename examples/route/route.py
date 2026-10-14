"""route: send each event of a trace or log to the first destination whose rule matches its
name, and count the events per destination.

usage: python3 route.py RULES EVENTS [--no-cache | --fnmatch] [--names] [--in-memory]
       pystachy build route.py -o route && ./route RULES EVENTS

RULES holds one rule per line, "PATTERN DESTINATION", in order (# starts a comment): a pattern is
fnmatch's, shell-style and case-sensitive (fnmatchcase), matched against an event's whole name,
and the first rule that matches routes the event; an event that none matches is "unrouted".
EVENTS holds one event per line: its name, then a tab and the rest. An event's destination
depends only on its name, and names repeat (a service emits a few hundred span names millions of
times), so route() is cached: lru_cache keeps the rules of the 4,096 names seen last, and a name
it has not seen goes through the rules' patterns, each compiled once as the rules load.

--no-cache routes each event through the compiled patterns again (route.__wrapped__); --fnmatch
routes each event through fnmatchcase(), as a program that matches with fnmatch does, which looks
each pattern up in fnmatch's own cache of compiled patterns. --names also counts the distinct
names, which takes memory for each of them: without it, what the router keeps is bounded by its
cache. --in-memory reads the whole trace first, and reports on stderr how long the routing alone
took.
"""

import re
import sys
import time
from fnmatch import _compile_pattern, fnmatchcase, translate
from functools import lru_cache
from typing import Callable

PATTERNS: list[str] = []
DESTINATIONS: list[str] = []
MATCHERS: list[Callable[[str], re.Match | None]] = []  # (each pattern's, compiled once)


def load(lines: list[str]) -> None:
    # the rules of lines, in place of any loaded before
    PATTERNS.clear()
    DESTINATIONS.clear()
    MATCHERS.clear()
    route.cache_clear()
    for line in lines:
        fields = line.split("#", 1)[0].split()
        if len(fields) == 2:
            PATTERNS.append(fields[0])
            DESTINATIONS.append(fields[1])
            MATCHERS.append(re.compile(translate(fields[0])).match)


@lru_cache(maxsize=4096)
def route(name: str) -> int:
    # the index of the first rule whose pattern matches name, or -1
    for i in range(len(MATCHERS)):
        if MATCHERS[i](name) is not None:
            return i
    return -1


def route_fnmatch(name: str) -> int:
    # route() through fnmatchcase(), which compiles a pattern once too, in its own cache
    for i in range(len(PATTERNS)):
        if fnmatchcase(name, PATTERNS[i]):
            return i
    return -1


def run(rules: str, trace: str, opts: list[str]) -> None:
    # route the events of the file trace by the rules of the file rules, and print the report
    mode = 1 if "--no-cache" in opts else 2 if "--fnmatch" in opts else 0
    with open(rules) as f:
        load(f.readlines())
    counts = [0] * (len(PATTERNS) + 1)  # (the last: unrouted)
    names: dict[str, bool] = {}
    keep = "--names" in opts
    events = 0
    with open(trace) as f:
        if "--in-memory" in opts:
            batch = [line[: line.find("\t")] if "\t" in line else line for line in f]
            t = time.perf_counter()
            for name in batch:
                if mode == 0:
                    counts[route(name)] += 1
                elif mode == 1:
                    counts[route.__wrapped__(name)] += 1
                else:
                    counts[route_fnmatch(name)] += 1
            t = time.perf_counter() - t
            events = len(batch)
            if not events:
                t = 0.0  # An empty batch did no routing; keep its report deterministic.
            per_event = t * 1e9 / events if events else 0.0
            print(f"routing: {t:.4f} s, {per_event:.1f} ns per event", file=sys.stderr)
            if keep:
                for name in batch:
                    names[name] = True
        else:
            for line in f:
                # the name, up to the first tab: found, not split, which would make a list and
                # a str of the rest of the line
                tab = line.find("\t")
                name = line[:tab] if tab >= 0 else line
                events += 1
                if mode == 0:
                    counts[route(name)] += 1
                elif mode == 1:
                    counts[route.__wrapped__(name)] += 1
                else:
                    counts[route_fnmatch(name)] += 1
                if keep:
                    names[name] = True
    print(f"{events} events, " + (f"{len(names)} names, " if keep else "") + f"{len(PATTERNS)} rules")
    totals: dict[str, int] = {}
    for i in range(len(PATTERNS)):
        totals[DESTINATIONS[i]] = totals.get(DESTINATIONS[i], 0) + counts[i]
    totals["unrouted"] = totals.get("unrouted", 0) + counts[-1]  # (a rule may send events there too)
    for d in sorted(totals, key=lambda d: (-totals[d], d)):
        print(f"{totals[d]:9} {d}")
    if mode == 0:
        print("route:", route.cache_info())
    if mode == 2:
        print("patterns:", _compile_pattern.cache_info())


def main() -> None:
    opts = sys.argv[3:]
    if len(sys.argv) < 3 or ("--no-cache" in opts and "--fnmatch" in opts):
        print("usage: route.py RULES EVENTS [--no-cache | --fnmatch] [--names] [--in-memory]", file=sys.stderr)
        sys.exit(2)
    run(sys.argv[1], sys.argv[2], opts)


if __name__ == "__main__":
    main()
