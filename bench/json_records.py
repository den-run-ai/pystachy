"""Recursive JSON consumer; CPython and PyPy use their stdlib, Pystachy its native overlay.

The handguarded mode is a source-written control, NOT compiler specialization.
Input generation and file I/O are outside the in-process measurements. A
predecoded run decodes once, outside the timed region, so processing is timed
without parser allocation or garbage; it also times rebuild(), which copies the
decoded containers: a floor for any decoder (binary formats included) that
builds the same values.
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


def rebuild(value: json.JSONValue) -> json.JSONValue:
    # New containers for the same scalars and strings: no text scanning, number
    # conversion or string decoding, as any decoder of these values still allocates.
    if isinstance(value, list):
        items: list[json.JSONValue] = []
        for item in value:
            items.append(rebuild(item))
        return items
    if isinstance(value, dict):
        fields: dict[str, json.JSONValue] = {}
        for key in value:
            fields[key] = rebuild(value[key])
        return fields
    return value


def warm(source: str, value: json.JSONValue, handguarded: bool, predecoded: bool,
         expected: int, warmup_ns: int) -> None:
    # Run the measured operations for warmup_ns (at least once) before sampling,
    # so tiers that compile while running (PyPy) report steady-state samples.
    start = perf_counter_ns()
    rounds = 0
    while rounds == 0 or perf_counter_ns() - start < warmup_ns:
        if predecoded:
            ok = process(value, handguarded) == expected and process(rebuild(value), False) == expected
        else:
            ok = process(json.loads(source), handguarded) == expected
        if not ok:
            raise ValueError("warmup result changed")
        rounds += 1
    print("JSON_WARMUP", rounds, perf_counter_ns() - start)


def run_predecoded(value: json.JSONValue, handguarded: bool, iterations: int, samples: int,
                   expected: int) -> None:
    for sample in range(samples):
        start = perf_counter_ns()
        processed = 0
        for iteration in range(iterations):
            processed += process(value, handguarded)
        process_ns = perf_counter_ns() - start

        start = perf_counter_ns()
        copy = value
        for iteration in range(iterations):
            copy = rebuild(value)
        rebuild_ns = perf_counter_ns() - start
        if processed != expected * iterations or process(copy, False) != expected:
            raise ValueError("processing result changed")
        print("JSON_PREDECODED", sample, processed, process_ns, rebuild_ns)


def run(path: str, handguarded: bool, iterations: int, samples: int, warmup_ns: int,
        predecoded: bool) -> None:
    with open(path) as stream:
        source = stream.read()
    value = json.loads(source)
    expected = process(value, False)
    if process(value, True) != expected:
        raise ValueError("handguarded control disagrees with generic processing")
    warm(source, value, handguarded, predecoded, expected, warmup_ns)
    if predecoded:
        run_predecoded(value, handguarded, iterations, samples, expected)
        return
    # Timings do not include validation or printing.
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
        # PATH ALGORITHM ITERATIONS SAMPLES WARMUP_MS PHASES (all or predecoded)
        run(sys.argv[1], sys.argv[2] == "handguarded", int(sys.argv[3]), int(sys.argv[4]),
            int(sys.argv[5]) * 1000000, sys.argv[6] == "predecoded")
