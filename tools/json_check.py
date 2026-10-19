#!/usr/bin/env python3
"""Differential checks for the bounded native JSON prototype against CPython.

Run with the pinned CPython, optionally exercising the hosted compiler's JIT/AOT:
  python3.13 tools/json_check.py --native --gc-stress
The deterministic corpus includes recursive mixed values, Unicode/surrogates,
malformed text and exact JSONDecodeError locations. No timings are collected.
"""

import argparse
import importlib.util
import json
import os
from pathlib import Path
import random
import shlex
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
DRIVER = '''import json


def main() -> None:
    while True:
        try:
            transport = input()
        except EOFError:
            break
        # Decimal code points, not a JSON string: a JSON-escaped pair of lone
        # surrogates would arrive as the one character it encodes.
        chars: list[str] = []
        for code in transport.split():
            chars.append(chr(int(code)))
        source = "".join(chars)
        try:
            value = json.loads(source)
            print("V", json.dumps(value),
                  json.dumps(value, sort_keys=True, separators=(",", ":")),
                  ascii(json.dumps(value, ensure_ascii=False)))
        except json.JSONDecodeError as exc:
            print("E", exc.pos, exc.lineno, exc.colno, json.dumps(exc.msg))


main()
'''


def generated_value(rng: random.Random, depth: int):
    kind = rng.randrange(7 if depth else 5)
    if kind == 0:
        return None
    if kind == 1:
        return bool(rng.randrange(2))
    if kind == 2:
        return rng.randrange(-(2**63), 2**63)
    if kind == 3:
        return rng.uniform(-1e20, 1e20)
    if kind == 4:
        return "".join(rng.choice('aé日本🚀\n\x00"\\\ud800\udc00') for _ in range(rng.randrange(10)))
    if kind == 5:
        return [generated_value(rng, depth - 1) for _ in range(rng.randrange(5))]
    return {str(i): generated_value(rng, depth - 1) for i in range(rng.randrange(5))}


def unicode_sources(rng: random.Random, invalid: int) -> list[str]:
    """Texts whose character positions differ from their UTF-8 offsets.

    Covers raw non-ASCII text, lone surrogates (which a str may hold), escapes
    after multibyte characters and object keys that repeat or share a length and
    first character. Surrogates and backslashes are built from code points here.
    """
    bs, high, low = chr(92), chr(0xD83D), chr(0xDE80)
    sources = [
        '"' + "\u00e9\u96ea" + chr(0x1F680) + chr(1) + '"', '["\u00e9", tru]', '{"\u00e9": 1,}', "\u00e9",
        '"' + bs + "u12\u00e9" + '"', '"\u00e9' + bs + "ud83d" + bs + 'u12"', '"\u00e9' + bs + 'x"',
        '"' + chr(0xD800) + '"', '"' + high + low + '"', '"' + high + bs + "ude80" + low + '"',
        '{"' + chr(0xD800) + '": [1, "' + low + '"], "' + chr(0xD800) + '": 2}',
        "[1, 2" + chr(0xDC00) + "]", '"' + chr(0xDC00) + "\u00e9" + bs + 'q"',
        '{"ab": 1, "ac": 2, "ab": 3, "": 4, "b": 5, "": 6, "ba": 7}',
        '[{"a' + bs + '"b": 1}, {"a' + bs + '"b": 2}, {"a' + bs + 'u0062": 3}, {"ab": 4}]',
        '{"\u00e9": 1, "e": 2, "\u00e9": 3, "\u00e9\u00e9": 4}', '{"' + chr(0x1F680) + '": "' + chr(0x1F680) + '"}',
        '{"k' + chr(31) + '": 1}', '{"k": 1, "k' + chr(10) + '": 2}', '{"' + "\u00e9\u96ea" + '": "unterminated}',
        "[" + "\u00e9" * 3 + "]", '"' + "\u96ea" * 4 + bs + 'u00"', "\u00a0[1]", "[1]" + chr(0x3000),
        '{"\u00e9":' + chr(0x85) + "1}", '{"a": 1}' + chr(0xFEFF),
        # one key cache slot, one prefix: lengths 2 and 66 differ by 64
        '[{"aa": 1, "' + "a" * 66 + '": 2}, {"' + "a" * 66 + '": 3, "aa": 4}]',
    ]
    keys = ["", "a", "b", "ab", "ac", "ba", "abc", "\u00e9", "e" + "\u00e9", "\u96ea\u00e9", chr(0x1F680),
            chr(0xD800), high + low, 'q"', "q" + bs, "\t", chr(0x7F), "0", "1", "id", "di"]
    for _ in range(200):
        record = {rng.choice(keys): generated_value(rng, 2) for _ in range(rng.randrange(6))}
        rows = [record, {rng.choice(keys): rng.randrange(3) for _ in range(3)}, record]
        sources.append(json.dumps(rows, ensure_ascii=False))
        sources.append(json.dumps(rows))
    alphabet = '[]{}:,"' + bs + "u01239afnrt-+.eE \n" + "\u00e9\u96ea" + chr(0x1F680) + chr(0xD800) + chr(0xDC00) + high + low + chr(0x10) + chr(0x7F)
    for _ in range(invalid):
        sources.append("".join(rng.choice(alphabet) for _ in range(rng.randrange(30))))
    return sources


def outcome(module, source: str) -> str:
    try:
        value = module.loads(source)
        return "V " + module.dumps(value) + " " + module.dumps(
            value, sort_keys=True, separators=(",", ":")
        ) + " " + ascii(module.dumps(value, ensure_ascii=False))
    except module.JSONDecodeError as exc:
        return f"E {exc.pos} {exc.lineno} {exc.colno} {module.dumps(exc.msg)}"


def check_limits(module) -> int:
    checks = 0
    for source in ("9223372036854775808", "-9223372036854775809"):
        try:
            module.loads(source)
        except OverflowError as exc:
            assert str(exc) == "JSON integer exceeds signed 64-bit range"
        else:
            raise AssertionError("accepted out-of-range integer: " + source)
        checks += 1
    # The module's explicit budget is independent of CPython's incidental Python
    # call-stack budget. Raise that budget for this hosted implementation check.
    old_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(max(old_limit, 5000))
    try:
        accepted = "[" * 256 + "0" + "]" * 256
        assert module.dumps(module.loads(accepted), separators=(",", ":")) == accepted
        try:
            module.loads("[" * 257 + "0" + "]" * 257)
        except RecursionError as exc:
            assert str(exc) == "maximum JSON nesting depth exceeded"
        else:
            raise AssertionError("accepted excess JSON nesting")
        value = module.loads(accepted)
        try:
            module.dumps([value])
        except RecursionError as exc:
            assert str(exc) == "maximum JSON nesting depth exceeded"
        else:
            raise AssertionError("encoded excess JSON nesting")
    finally:
        sys.setrecursionlimit(old_limit)
    return checks + 3


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=int, default=1000)
    parser.add_argument("--invalid", type=int, default=10000)
    parser.add_argument("--unicode-invalid", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=391)
    parser.add_argument("--native", action="store_true")
    parser.add_argument("--gc-stress", action="store_true")
    parser.add_argument("--compiler", default=shlex.join([sys.executable, "-m", "pystachy"]))
    args = parser.parse_args()
    if args.cases < 0 or args.invalid < 0 or args.unicode_invalid < 0:
        parser.error("case counts must be nonnegative")
    expected_version = (ROOT / ".python-version").read_text().strip()
    actual_version = ".".join(str(x) for x in sys.version_info[:3])
    if expected_version != actual_version:
        parser.error(f"use pinned CPython {expected_version}; got {actual_version}")
    spec = importlib.util.spec_from_file_location("_json_under_test", ROOT / "lib/json.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rng = random.Random(args.seed)
    sources = [
        "null", "true", "false", "0", "-0", "-0.0", "1e400", "-1e400", "NaN", "Infinity",
        "-Infinity", '{"a":1,"a":[false,null]}', r'"\ud83d\ude80\ud800x\udc00"',
        "[1,]", '{"a":1,}', "\ufeffnull", '{\n "é": [1,]\n}',
    ]
    raw_sources = []
    checks = 0
    for _ in range(args.cases):
        value = generated_value(rng, 4)
        for ascii_only in (False, True):
            for sorted_keys in (False, True):
                for separators in (None, (",", ":")):
                    expected = json.dumps(value, ensure_ascii=ascii_only,
                                          sort_keys=sorted_keys, separators=separators)
                    actual = module.dumps(value, ensure_ascii=ascii_only,
                                          sort_keys=sorted_keys, separators=separators)
                    assert actual == expected, (value, actual, expected)
                    assert json.dumps(module.loads(expected)) == json.dumps(value)
                    checks += 1
        sources.append(json.dumps(value))
        raw_sources.append(json.dumps(value, ensure_ascii=False))
    for _ in range(args.invalid):
        sources.append("".join(rng.choice('[]{}:,"\\u01239afnrt-+.eE \n')
                               for _ in range(rng.randrange(30))))
    # Appended after the original corpus, from a separate generator, so the
    # sources above stay those of earlier runs with the same seed.
    sources.extend(raw_sources)
    sources.extend(unicode_sources(random.Random(args.seed + 1), args.unicode_invalid))
    expected_lines = []
    for source in sources:
        expected = outcome(json, source)
        actual = outcome(module, source)
        assert expected == actual, (source, actual, expected)
        expected_lines.append(expected)
        checks += 1
    checks += check_limits(module)
    print(f"hosted JSON differential/limit checks: {checks} passed (seed {args.seed})")
    if not args.native:
        return
    compiler = shlex.split(args.compiler)
    if not compiler:
        parser.error("--compiler must not be empty")
    env = os.environ.copy()
    if args.gc_stress:
        env["PYSTACHY_GC_STRESS_PROGRAM"] = "1"
    payload = "".join(" ".join(str(ord(c)) for c in source) + "\n" for source in sources)
    expected_output = "\n".join(expected_lines) + "\n"
    with tempfile.TemporaryDirectory(prefix="pystachy-json-check-") as temp:
        source_path = Path(temp) / "check_json.py"
        output_path = Path(temp) / "check_json"
        source_path.write_text(DRIVER)
        subprocess.run(compiler + ["build", str(source_path), "-o", str(output_path)],
                       cwd=ROOT, env=env, check=True, timeout=120)
        for mode, cmd in (("jit", compiler + ["run", str(source_path)]),
                          ("aot", [str(output_path)])):
            run_env = dict(env, PYSTACHY_GC_STRESS="1") if mode == "aot" and args.gc_stress else env
            result = subprocess.run(cmd, cwd=ROOT, env=run_env, input=payload, text=True,
                                    capture_output=True, timeout=120, check=False)
            if result.returncode != 0 or result.stderr:
                raise AssertionError((mode, result.returncode, result.stderr))
            if result.stdout != expected_output:
                actual_lines = result.stdout.splitlines()
                for i, expected in enumerate(expected_lines):
                    actual = actual_lines[i] if i < len(actual_lines) else "<missing>"
                    if actual != expected:
                        raise AssertionError((mode, i, sources[i], actual, expected))
                raise AssertionError((mode, "unexpected trailing output"))
            print(f"{mode} JSON differential cases: {len(sources)} passed"
                  + (" (GC every allocation)" if args.gc_stress else ""))


if __name__ == "__main__":
    main()
