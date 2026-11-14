"""Time schema-free repair calls from a normal CPython application.

MODULE API MIX ROUNDS [BATCHES WARMUPS] [--cases FILE]. MODULE is json_repair or
pystachy_json_repair; API is text, objects or logs; MIX is mixed or malformed.
The mixed workload has 16 valid and four malformed requests per round. This
constructed 80/20 mix is not an estimate of production failure frequencies.
All malformed requests are exercised equally. The malformed control has four
requests per round. Inputs and complete tagged expectations are pinned to
pristine upstream 0.64.9 in companion_cases.json.

Only the API calls and identical result/checksum bookkeeping are timed. Input
creation, imports, full-output validation and witness formatting are outside
the timer. Malformed object/log results include the companion's JSON transport
and CPython decoding cost. This is neither a pure native-loop benchmark nor
schema validation; the companion holds the GIL on its importing thread.
"""
import argparse
import importlib
from importlib.machinery import ExtensionFileLoader
import json
from pathlib import Path
from time import perf_counter


CASES = Path(__file__).with_name("companion_cases.json")


def tagged(value):
    """Retain exact types, dictionary order, string code points and float bits."""
    if value is None:
        return ["none"]
    if type(value) is bool:
        return ["bool", value]
    if type(value) is int:
        return ["int", str(value)]
    if type(value) is float:
        return ["float", value.hex()]
    if type(value) is str:
        return ["str", value]
    if type(value) is list:
        return ["list", [tagged(item) for item in value]]
    if type(value) is tuple:
        return ["tuple", [tagged(item) for item in value]]
    if type(value) is dict:
        return ["dict", [[tagged(key), tagged(item)] for key, item in value.items()]]
    raise TypeError(f"unexpected result type: {type(value).__name__}")


def validate(results, expected):
    actual = [tagged(result) for result in results]
    if actual != expected:
        raise ValueError("complete typed result, key order or repair logs differ from upstream")


def select_cases(document, mix):
    rows = document["cases"]
    valid = [row for row in rows if row["valid"]]
    malformed = [row for row in rows if not row["valid"]]
    if len(valid) != 4 or len(malformed) != 4:
        raise ValueError("expected four valid and four malformed source records")
    if mix == "malformed":
        return malformed
    # Each group ends with a different malformed record; no stochastic mix.
    return [row for bad in malformed for row in [*valid, bad]]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("module", choices=("json_repair", "pystachy_json_repair"))
    parser.add_argument("api", choices=("text", "objects", "logs"))
    parser.add_argument("mix", choices=("mixed", "malformed"))
    parser.add_argument("rounds", type=int)
    parser.add_argument("batches", type=int, nargs="?", default=1)
    parser.add_argument("warmups", type=int, nargs="?", default=0)
    # Pass this explicitly in benchmark configurations so command_identity()
    # fingerprints the oracle fixture before and after the campaign.
    parser.add_argument("--cases", type=Path, default=CASES)
    args = parser.parse_args()
    if args.rounds < 0 or args.batches < 1 or args.warmups < 0:
        parser.error("rounds/warmups must be nonnegative and batches positive")
    module = importlib.import_module(args.module)
    if args.module == "pystachy_json_repair":
        if not isinstance(module._native.__spec__.loader, ExtensionFileLoader):
            raise ValueError("the companion must load a real compiled extension")
    call = module.repair_json if args.api == "text" else module.loads
    flags = {"logging": True} if args.api == "logs" else {}
    document = json.loads(args.cases.read_text())
    cases = select_cases(document, args.mix)
    sources = [case["input"] for case in cases]
    expected = [case["expected"][args.api] for case in cases]
    results = [call(source, **flags) for source in sources]
    validate(results, expected)
    per_round = sum(len(result) for result in results)
    # Print each unique complete result once; repetitions are identified by IDs.
    print("outputs", json.dumps([[case["id"], case["expected"][args.api]]
                                for case in document["cases"]], ensure_ascii=True))
    print("witness before", args.api, args.mix, [case["id"] for case in cases], per_round, "exact")
    print("rounds", args.rounds)
    for batch in range(args.warmups + args.batches):
        checksum = 0
        start = perf_counter()
        for _ in range(args.rounds):
            for index, source in enumerate(sources):
                result = call(source, **flags)
                results[index] = result
                checksum += len(result)
        elapsed = perf_counter() - start
        if checksum != args.rounds * per_round:
            raise ValueError("iteration checksum changed")
        validate(results, expected)
        print("witness after", batch, args.api, args.mix, len(results), checksum, "exact")
        print("warmup_seconds" if batch < args.warmups else "seconds", elapsed)


if __name__ == "__main__":
    main()
