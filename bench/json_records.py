"""Recursive JSON consumer; CPython uses its stdlib, Pystachy its native overlay.

The handguarded mode is a source-written control, NOT compiler specialization.
Input generation and file I/O are outside the in-process measurements.
"""
from __future__ import annotations

import json
import sys
from time import perf_counter_ns


def amount_score(value: json.JSONValue) -> int:
    # Quarter units are exact in this fixture. Distinguish bool from int, and
    # retain rare alternatives in the checksum instead of dropping those rows.
    if isinstance(value, bool):
        return 3 if value else 5
    if isinstance(value, int):
        return value * 4 + 7
    if isinstance(value, float):
        return int(value * 4.0) + 11
    if isinstance(value, str):
        return len(value) * 13 + 17
    if value is None:
        return 19
    if isinstance(value, list):
        return len(value) * 23
    return len(value) * 29


def details_score(record: dict[str, json.JSONValue]) -> int:
    score = 0
    identifier = record.get("id")
    if isinstance(identifier, int):
        score += identifier * 31
    details = record.get("details")
    if isinstance(details, dict):
        name = details.get("name")
        if isinstance(name, str):
            score += len(name) * 37
        tags = details.get("tags")
        if isinstance(tags, list):
            for tag in tags:
                if isinstance(tag, str):
                    score += len(tag) * 41
    return score


def process(value: json.JSONValue, handguarded: bool) -> int:
    if not isinstance(value, list):
        raise ValueError("expected a JSON array")
    score = 0
    for record in value:
        if not isinstance(record, dict):
            raise ValueError("expected JSON objects")
        amount = record.get("amount")
        # A guarded fast path remains correct when the distribution changes.
        # It still observes the original shared object; no copied schema view.
        if handguarded and not isinstance(amount, bool) and isinstance(amount, int):
            score += amount * 4 + 7
        else:
            score += amount_score(amount)
        score += details_score(record)
    return score


def run(path: str, handguarded: bool, iterations: int, samples: int) -> None:
    with open(path) as stream:
        source = stream.read()
    value = json.loads(source)
    expected = process(value, False)
    if process(value, True) != expected:
        raise ValueError("handguarded control disagrees with generic processing")
    # Warm the processing paths; timings do not include validation or printing.
    for sample in range(samples):
        start = perf_counter_ns()
        parsed_count = 0
        for iteration in range(iterations):
            value = json.loads(source)
            if not isinstance(value, list):
                raise ValueError("expected a JSON array")
            parsed_count += len(value)
        parse_ns = perf_counter_ns() - start
        if process(value, False) != expected:
            raise ValueError("parse result changed")

        start = perf_counter_ns()
        processed = 0
        for iteration in range(iterations):
            processed += process(value, handguarded)
        process_ns = perf_counter_ns() - start

        start = perf_counter_ns()
        combined = 0
        for iteration in range(iterations):
            combined += process(json.loads(source), handguarded)
        combined_ns = perf_counter_ns() - start
        if processed != expected * iterations or combined != processed:
            raise ValueError("processing result changed")
        print("JSON_SAMPLE", sample, parsed_count, processed, combined,
              parse_ns, process_ns, combined_ns)


def smoke() -> None:
    # bench/run.sh and the verification matrix execute every bench/*.py with
    # no arguments and compare exact stdout. Keep their small fixture embedded
    # and deterministic; the separate controller owns measurement and datasets.
    source = ('[{"id":1,"amount":10,"details":{"name":"é雪🚀","tags":["api","地域"]}},'
              '{"id":2,"amount":1.25},{"id":3,"amount":null},{"id":4},'
              '{"id":5,"amount":"pending"},{"id":6,"amount":true},'
              '{"id":7,"amount":false},{"id":8,"amount":[1,null]},'
              '{"id":9,"amount":{"units":2}}]')
    total = 0
    for iteration in range(64):
        value = json.loads(source)
        generic = process(value, False)
        guarded = process(value, True)
        if generic != guarded:
            raise ValueError("handguarded control disagrees with generic processing")
        total += generic + guarded
    print("json_records", total)


if __name__ == "__main__":
    if len(sys.argv) == 1:
        smoke()
    else:
        run(sys.argv[1], sys.argv[2] == "handguarded", int(sys.argv[3]), int(sys.argv[4]))
