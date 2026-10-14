"""Regex capture ingestion with runtime-sized tuples and a fixed-shape control.

Usage: regex_capture_tuples.py MODE [repeats=200] [records=64]
Modes: check, endtoend, static, consumer, concrete, render, render-static.
The ordinary Match.groups() implementation supplies log-field normalization.
The fixed controls' only consumer change is their tuple annotations. Their
producer uses Match.group(1, 2, 3), so end-to-end timings also include different
capture construction. Consumer/concrete isolate a lightweight field signature;
they construct captures before the CPU timer and exclude regex matching.
"""
import re
import sys
import time


def capture_score(groups: tuple[str | None, ...]) -> int:
    score = 0
    position = 1
    for value in groups:
        if value is None:
            score += position
        else:
            # A lightweight field signature used when classifying parsed logs.
            score += len(value) * position + value.count("/")
        position += 1
    return score


def concrete_score(groups: tuple[str | None, str | None, str | None]) -> int:
    score = 0
    position = 1
    for value in groups:
        if value is None:
            score += position
        else:
            # A lightweight field signature used when classifying parsed logs.
            score += len(value) * position + value.count("/")
        position += 1
    return score


def render_record(groups: tuple[str | None, ...]) -> str:
    if len(groups) == 3:
        user = groups[0]
        method = groups[1]
        target = groups[2]
        return ("-" if user is None else user.strip().lower()) + "\t" + ("-" if method is None else method.strip().lower()) + "\t" + ("-" if target is None else target.strip().lower())
    row = ""
    position = 0
    for value in groups:
        if position != 0:
            row += "\t"
        if value is None:
            row += "-"
        else:
            row += value.strip().lower()
        position += 1
    return row


def concrete_render(groups: tuple[str | None, str | None, str | None]) -> str:
    if len(groups) == 3:
        user = groups[0]
        method = groups[1]
        target = groups[2]
        return ("-" if user is None else user.strip().lower()) + "\t" + ("-" if method is None else method.strip().lower()) + "\t" + ("-" if target is None else target.strip().lower())
    row = ""
    position = 0
    for value in groups:
        if position != 0:
            row += "\t"
        if value is None:
            row += "-"
        else:
            row += value.strip().lower()
        position += 1
    return row


mode = sys.argv[1] if len(sys.argv) > 1 else "endtoend"
repeats = int(sys.argv[2]) if len(sys.argv) > 2 else 200
record_count = int(sys.argv[3]) if len(sys.argv) > 3 else 64
assert mode in ["check", "endtoend", "static", "consumer", "concrete", "render", "render-static"]
assert repeats > 0 and record_count > 0
methods = ["GET", "POST", "DELETE"]
records: list[str] = ["user" + str(i % 17) + " " + methods[i % 3] + " /api/v" + str(i % 4) + "/records/" + str(i) for i in range(record_count)]
pattern = re.compile(r"^(user[0-9]+) ([A-Z]+) (/[^ ]+)$")
checksum = 0

if mode == "check":
    # Multiple capture arities, optional captures, defaults, and Unicode
    # must preserve the ordinary regex API. Unicode checks compare text, since
    # the existing string port counts UTF-8 bytes in len().
    cases: list[tuple[str, str, list[str | None], str | None]] = [
        (r"^plain$", "plain", [], None),
        (r"^(alpha)$", "alpha", ["alpha"], None),
        (r"^(alpha):([0-9]+)$", "alpha:42", ["alpha", "42"], None),
        (r"^(alice) ([A-Z]+) (/[^ ]+)$", "alice GET /docs", ["alice", "GET", "/docs"], None),
        (r"^(alice) ([A-Z]+) (/[^ ]+) ([0-9]+)$", "alice GET /docs 200", ["alice", "GET", "/docs", "200"], None),
        (r"^(a)(b)(c)(d)(e)(f)(g)(h)(i)(j)$", "abcdefghij", ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j"], None),
        (r"^(name)(?::([a-z]+))?(?::([a-z]+))?$", "name:thing", ["name", "thing", None], None),
        (r"^(name)(?::([a-z]+))?(?::([a-z]+))?$", "name:thing", ["name", "thing", ""], ""),
        (r"^([^:]+):([^:]+)$", "café:東京", ["café", "東京"], None),
    ]
    for expression, text, expected, default in cases:
        match = re.match(expression, text)
        assert match is not None
        groups = match.groups(default)
        assert len(groups) == len(expected)
        index = 0
        for value in groups:
            assert value == expected[index]
            index += 1
        expected_row = ""
        index = 0
        for value in expected:
            if index != 0:
                expected_row += "\t"
            expected_row += "-" if value is None else value.strip().lower()
            index += 1
        assert render_record(groups) == expected_row
        if text != "café:東京":
            checksum += capture_score(groups)
    assert re.match(r"^(missing)$", "present") is None
    print("check", len(cases), checksum)
else:
    captures: list[tuple[str | None, ...]] = []
    fixed_captures: list[tuple[str | None, str | None, str | None]] = []
    if mode in ["consumer", "concrete", "render", "render-static"]:
        for record in records:
            match = pattern.match(record)
            assert match is not None
            if mode == "consumer" or mode == "render":
                captures.append(match.groups())
            else:
                fixed_captures.append(match.group(1, 2, 3))
    start = time.process_time()
    for _ in range(repeats):
        if mode == "consumer":
            for groups in captures:
                checksum += capture_score(groups)
        elif mode == "concrete":
            for fixed_groups in fixed_captures:
                checksum += concrete_score(fixed_groups)
        elif mode == "render":
            for groups in captures:
                checksum += len(render_record(groups))
        elif mode == "render-static":
            for fixed_groups in fixed_captures:
                checksum += len(concrete_render(fixed_groups))
        else:
            for record in records:
                match = pattern.match(record)
                assert match is not None
                if mode == "static":
                    checksum += len(concrete_render(match.group(1, 2, 3)))
                else:
                    checksum += len(render_record(match.groups()))
    elapsed = time.process_time() - start
    print(mode, checksum, elapsed)
