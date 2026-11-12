"""Differential fuzz of the json_repair port against pristine upstream.

Generates deterministic malformed inputs, replays them with tests/upstream/json_repair/replay.py
through pristine upstream under CPython (the oracle), the port under CPython and the port's native
build, and compares typed values, serialized text, repair logs and error messages exactly.

Input families: "mixed" mutates recorded corpus inputs and rendered random values; "long" places
quotes, escapes and structural characters at the string scanner's 64-code-point chunk boundaries;
"number" builds numeric tokens; "comment" places terminators at the comment scanner's windows.

The result is evidence for the generated inputs, not proof of parity. Exit status 1: a difference.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile

from json_repair_parity import exact_equal, normalize

ROOT = Path(__file__).resolve().parent.parent
REPLAY = ROOT / "tests/upstream/json_repair/replay.py"
MANIFEST = ROOT / "tests/upstream/json_repair/manifest.json"
CASES = ROOT / "tests/upstream/json_repair/cases.json"
FAMILIES = ("mixed", "long", "number", "comment")
CHUNKS = (64, 128, 192, 256, 320, 384)  # ends of the string scanner's chunks
WINDOWS = (64, 192, 448, 960)  # ends of the comment scanner's doubling windows
TOKENS = list('{}[](),:"\'`#/*\\ \n\t\r') + list("abntrufse019-+.eE_x") + [
    "\u201c", "\u201d", "\u2018", "\u2019", "true", "false", "null", "None", "True", "False", "NaN", "Infinity",
    "-Infinity", "undefined", "//", "/*", "*/", "```", "```json\n", "\n```", "\\n", "\\t", '\\"', "\\\\", "\\/",
    "\\u00e9", "\\ud83d\\ude00", "\\ud83d", "\\x41", "\\'", "\u00e9", "\u65e5\u672c", "\U0001f600", "...", "1e5",
    "-0", "0.5", "1.", ".5", "1_000", "0x1f", "12345678901234567890123", "1/2", "1-2", "1,", '":', '",', '"}',
    '"]', '""', "''", ': "', ', "', "{}", "[]", "\u00a0", "\ufeff", "\u2028", "\x00", "\x0b", "\x0c", "\x1f",
    "key", "value", " and ", "# c\n", "// c\n", "/* c */", "<!-- c -->", "\u2026", "\u0660\u0663", "\u00b2",
    "\u2167", "Here is the JSON: ", " Hope this helps!", '"a": 1', "'a': 'b'", "a: b", '"\\', "\\u12"]
SPECIAL = ['"', "'", "\u201c", "\u201d", "`", "\\", "\\n", "\\t", '\\"', "\\\\", "\\u00e9", "\\ud83d\\ude00", "\n",
           "\t", " ", ",", ":", "{", "}", "[", "]", "/", "//", "/*", "*/", "#", "\u00e9", "\U0001f600", "\\x",
           "\\u12", "\r\n", '",', '":', '" ', '",\n"', '": "', '"}', '"]', "\\'", "\u00a0", "\x00", "\\b\\f\\r",
           "\\n\\n\\t\\r\\b"]
ENDS = ["\n", "\r", "]", "}", ":", "*/", "*", "/", "/*", "//", "#", '"', ",", "\r\n", "*/ ", "-->"]
WORDS = ["lorem", "ipsum", "dolor", "sit", "amet", "x", "\u65e5\u672c\u8a9e", "na\u00efve", "data", "42", "true",
         "a_b", "-"]
TEXTS = ["a", "key", "na\u00efve", "\u65e5\u672c\u8a9e", "x y", "it's", 'say "hi"', "a,b", "a:b", "{x}", "[1]",
         "line\nbreak", "tab\t", "back\\slash", "\U0001f600", "", " ", "true", "12", "// no", "/* no */", "# no"]
# Every API and option that the replay program passes on.
FLAGS = [("repair_json", {"return_objects": True}),
         ("repair_json", {"return_objects": True, "skip_json_loads": True}),
         ("repair_json", {"return_objects": True, "skip_json_loads": True, "logging": True}),
         ("repair_json", {"return_objects": True, "strict": True}),
         ("repair_json", {"return_objects": True, "skip_json_loads": True, "strict": True}),
         ("repair_json", {"return_objects": True, "stream_stable": True}),
         ("repair_json", {"return_objects": True, "skip_json_loads": True, "stream_stable": True}),
         ("repair_json", {"return_objects": False, "ensure_ascii": False}),
         ("repair_json", {"return_objects": False, "skip_json_loads": True}),
         ("loads", {}),
         ("loads", {"logging": True})]


def filler(rng, length):
    chars = []
    while len(chars) < length:
        chars.extend(rng.choice(WORDS))
        if rng.randrange(3):
            chars.append(" ")
    return chars[:length]


def spliced(rng, chars, marks, pieces, lead=0):
    """chars with up to four pieces put at, or within three characters of, one of the marks."""
    for _ in range(rng.randrange(5)):
        at = rng.choice(marks) + rng.randrange(-3, 4) - lead if rng.randrange(3) else rng.randrange(len(chars) + 1)
        at = min(max(at, 0), len(chars))
        chars[at:at + rng.randrange(2)] = list(rng.choice(pieces))
    return "".join(chars)


def random_value(rng, depth):
    kind = rng.randrange(9 if depth > 0 else 6)
    if kind == 0:
        return rng.choice([True, False, None])
    if kind == 1:
        return rng.randrange(-5, 2000)
    if kind == 2:
        return rng.choice([0.5, -1.25, 1e20, 3.0, 1e-7, 123456789012345678])
    if kind < 6:
        return rng.choice(TEXTS) + (rng.choice(TEXTS) if rng.randrange(4) == 0 else "")
    if kind < 8:
        return {rng.choice(TEXTS) if rng.randrange(5) else "k%d" % i: random_value(rng, depth - 1)
                for i in range(rng.randrange(4))}
    return [random_value(rng, depth - 1) for _ in range(rng.randrange(5))]


def rendered(rng, value):
    style = rng.randrange(6)
    if style == 0:
        return json.dumps(value)
    if style == 1:
        return json.dumps(value, ensure_ascii=False, indent=rng.choice([1, 2, "\t"]))
    if style == 2:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if style == 3:
        return repr(value)
    if style == 4:
        return json.dumps(value, ensure_ascii=False).replace('"', rng.choice(["'", "\u201c", "", "`"]))
    return json.dumps(value, ensure_ascii=False).replace(",", rng.choice([", ", " ", ",,", ";", "\n"]))


def mutated(rng, text, seeds):
    for _ in range(rng.choice([0, 1, 1, 1, 2, 2, 3, 4, 6])):
        operation = rng.randrange(10)
        at = rng.randrange(len(text) + 1)
        if operation == 0:
            text = text[:at] + text[at + rng.randrange(1, 4):]
        elif operation < 4:
            text = text[:at] + rng.choice(TOKENS) + text[at:]
        elif operation == 4:
            text = text[:at] + rng.choice(TOKENS) + text[at + 1:]
        elif operation == 5:
            end = min(len(text), at + rng.randrange(1, 8))
            text = text[:end] + text[at:end] + text[end:]
        elif operation == 6:
            text = text[:at]
        elif operation == 7:
            other = rng.choice(seeds)
            text += rng.choice(["", " ", "\n", ",", " and ", "```"]) + other[:rng.randrange(len(other) + 1)]
        elif operation == 8:
            text = (rng.choice(["", "Sure: ", "```json\n", "```\n", "json ", "Result = ", "// x\n", "\ufeff"]) + text +
                    rng.choice(["", "\n```", " done.", ";", "\n", " // end", " /* end"]))
        else:
            other = rng.randrange(len(text) + 1)
            text = text[:min(at, other)] + text[max(at, other):]
    return text


def mixed_text(rng, seeds):
    pick = rng.randrange(10)
    if pick < 4:
        text = rng.choice(seeds)
    elif pick < 9:
        text = rendered(rng, random_value(rng, rng.randrange(1, 4)))
    else:
        text = "".join(rng.choice(TOKENS) for _ in range(rng.randrange(1, 14)))
    return mutated(rng, text, seeds)


def long_text(rng, seeds):
    def content():
        return spliced(rng, filler(rng, rng.choice(CHUNKS) + rng.randrange(-4, 5)), CHUNKS, SPECIAL)

    quote = rng.choice(['"', '"', '"', "'", "\u201c", "", "`"])
    close = rng.choice(["", '"', "'"]) if rng.randrange(6) == 0 else {"\u201c": "\u201d"}.get(quote, quote)
    parts = [quote + content() + close for _ in range(rng.randrange(1, 4))]
    shape = rng.randrange(8)
    if shape == 0:
        text = parts[0]
    elif shape == 1:
        text = "[" + ", ".join(parts) + rng.choice(["]", "", ",]"])
    elif shape == 2:
        text = '{"k": ' + parts[0] + rng.choice(["}", "", ', "z": 1}', "\n}"])
    elif shape == 3:
        text = "{" + parts[0] + ": " + parts[-1] + rng.choice(["}", ""])
    elif shape == 4:
        text = '{"a": [' + ", ".join(parts) + '], "b": ' + parts[0] + "}"
    elif shape == 5:
        text = rng.choice(["/* ", "// ", "# "]) + content() + rng.choice([" */", "\n", ""]) + '{"k": ' + parts[0] + "}"
    elif shape == 6:
        text = '{"k": ' + parts[0] + " " + rng.choice(["//", "/*", "#"]) + content() + rng.choice(["\n}", "*/}", ""])
    else:
        text = "Text " + content() + ' {"k": ' + parts[0] + "} " + content()
    return mutated(rng, text, seeds) if rng.randrange(3) == 0 else text


def number_text(rng, seeds):
    token = "".join(rng.choice("0123456789012345+-..eE_/, xaAn\u0660\u00b2") for _ in range(rng.randrange(1, 13)))
    if rng.randrange(5) == 0:
        token = (rng.choice(["-", "", "+"]) + rng.choice("123456789") +
                 "".join(rng.choice("0123456789") for _ in range(rng.randrange(15, 45))))
    if rng.randrange(6) == 0:
        token += rng.choice(["e400", "E-400", ".", "e", "e+", "-", "/3", ".0e3", "_000", "n", "L", "%"])
    shape = rng.randrange(9)
    if shape == 0:
        return token
    if shape == 1:
        return "[" + token + rng.choice(["]", "", ",]", " ]"])
    if shape == 2:
        return "[" + token + ", " + token[::-1] + "]"
    if shape == 3:
        return '{"a": ' + token + rng.choice(["}", "", ', "b": 2}', " }", "\n}"])
    if shape == 4:
        return "{" + token + ": " + token + "}"
    if shape == 5:
        return '{"a": [' + token + rng.choice(["]}", "", "]", "}"])
    if shape == 6:
        return token + rng.choice([" ", "\n", ","]) + token
    if shape == 7:
        return '{"a": ' + token + rng.choice([" // c\n}", "/* c */}", " # c", ","])
    return "(" + token + rng.choice([")", "", ", 1)"])


def comment_text(rng, seeds, nested=False):
    opener = rng.choice(["//", "#", "/*", "/*", "/", "<!--"])
    length = rng.choice(WINDOWS) + rng.randrange(-3, 4) if rng.randrange(4) else rng.randrange(40)
    body = spliced(rng, filler(rng, length), WINDOWS, ENDS, len(opener))
    comment = opener + body + rng.choice(["", "", "\n", "*/", "\r", " */ "])
    shape = rng.randrange(9 if nested else 10)
    if shape == 0:
        return comment
    if shape == 1:
        return comment + '{"a": 1}'
    if shape == 2:
        return "[1, " + comment + rng.choice(["2]", "]", "", ", 2]"])
    if shape == 3:
        return '{"a": 1, ' + comment + rng.choice(['"b": 2}', "}", ""])
    if shape == 4:
        return '{"a": ' + comment + rng.choice(["1}", "}", '"x"}', ""])
    if shape == 5:
        return "{" + comment + rng.choice(['"a": 1}', ": 1}", "}", ""])
    if shape == 6:
        return '{"a" ' + comment + rng.choice([": 1}", "1}", "}"])
    if shape == 7:
        return '{"a": 1} ' + comment + rng.choice(["", '{"b": 2}', "[3]"])
    if shape == 8:
        return '{"a": "x' + comment + rng.choice(['"}', "}", ""])
    return "[" + comment + comment_text(rng, seeds, True)[:300] + "]"


GENERATORS = {"mixed": mixed_text, "long": long_text, "number": number_text, "comment": comment_text}


def corpus_seeds(cases):
    return sorted({row["input"] for row in cases if "input_codepoints" not in row and len(row["input"]) <= 240})


def requests(seed, count, family, seeds):
    """count replay requests: each generated text under three API and option combinations. A text
    holds no surrogate code point, which the requests' JSON transport would not preserve."""
    rng = random.Random(f"{family}:{seed}")
    rows = []
    while len(rows) < count:
        text = GENERATORS[family](rng, seeds)
        if len(text) > (400 if family == "mixed" else 2500) or any(0xD800 <= ord(char) <= 0xDFFF for char in text):
            continue
        for api, flags in rng.sample(FLAGS, 3):
            if len(rows) < count:
                rows.append({"id": len(rows), "api": api, "input": text, "flags": flags})
    return rows


def outcome(line, ident):
    """Case ident's row of the replay program's output: a value or an error, never both."""
    if not line:
        raise ValueError(f"no outcome for case {ident}")
    row = json.loads(line)
    if type(row.get("id")) is not int or row.pop("id") != ident:
        raise ValueError(f"expected case {ident}'s outcome, not {line[:80]!r}")
    if ("value" in row) == ("error" in row):
        raise ValueError(f"case {ident} needs exactly one of a value and an error")
    if "value" in row:
        row["value"] = normalize(row["value"])
    return row


def checked(output, count):
    """How many of the output file's rows are errors. It must hold one row for each case, in order."""
    errors = 0
    with open(output) as rows:
        for ident in range(count):
            errors += "error" in outcome(rows.readline(), ident)
        if rows.readline():
            raise ValueError(f"more than {count} outcomes")
    return errors


def differing(oracle, other, count):
    """The ids of the first count cases whose outcomes differ between two output files, of which
    other holds no more, and the oracle's outcomes of the first 25 of them. The files are read a
    row at a time: a long family's outcomes take gigabytes as Python values."""
    bad = []
    kept = {}
    with open(oracle) as first, open(other) as second:
        for ident in range(count):
            expected = outcome(first.readline(), ident)
            if not exact_equal(expected, outcome(second.readline(), ident)):
                bad.append(ident)
                if len(kept) < 25:
                    kept[ident] = expected
        if second.readline():
            raise ValueError(f"more than {count} outcomes")
    return bad, kept


def check_upstream(upstream):
    """The oracle's sources must be the pinned release's, by the hashes of the corpus manifest."""
    manifest = json.loads(MANIFEST.read_text())
    for relative, expected in manifest["source_sha256"].items():
        path = upstream / relative
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"{path} is not json_repair {manifest['tag']}'s {relative}")
    return manifest["tag"]


def replayed(label, command, env, inputs, timeout):
    """The file of the replay program's output for the inputs; a failure or any stderr is an error."""
    output = inputs.with_name(inputs.stem + "-" + "".join(char if char.isalnum() else "-" for char in label) + ".out")
    with open(output, "w") as out:
        result = subprocess.run([*command, str(inputs)], env=env, stdout=out, stderr=subprocess.PIPE, text=True,
                                timeout=timeout, cwd=inputs.parent)
    if result.returncode or result.stderr:
        raise ValueError(f"{label}: exit {result.returncode}: {result.stderr[-2000:]}")
    return output


def hosted_env(package_parent):
    """CPython with exactly one json_repair on its path; the replay program's directory has none."""
    env = dict(os.environ, PYTHONPATH=str(package_parent), PYTHONHASHSEED="0")
    result = subprocess.run([sys.executable, "-c", "import json_repair; print(json_repair.__file__)"], env=env,
                            capture_output=True, text=True, cwd=REPLAY.parent)
    found = result.stdout.strip()
    if result.returncode or Path(found).resolve() != (package_parent / "json_repair/__init__.py").resolve():
        raise ValueError(f"CPython imports {found or 'no json_repair'}, not {package_parent}'s")
    return env


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--upstream", type=Path, required=True, help="pristine checkout of the pinned release")
    parser.add_argument("--compiler", type=Path, default=ROOT / "pystachy", help="built native compiler")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--cases", type=int, default=30000, help="cases of each family")
    parser.add_argument("--family", choices=FAMILIES, action="append", help="default: every family")
    parser.add_argument("--jit", action="store_true", help="also replay through the JIT")
    parser.add_argument("--gc-stress", type=int, default=0, metavar="N",
                        help="also replay each family's first N cases natively with a stressed collector, "
                             "which takes seconds for a case with long output")
    parser.add_argument("--timeout", type=int, default=1800, help="seconds for each replay")
    parser.add_argument("--report", type=Path, help="write counts and the first differing cases as JSON")
    args = parser.parse_args(argv)
    tag = check_upstream(args.upstream.resolve())
    compiler = args.compiler.resolve()
    seeds = corpus_seeds(json.loads(CASES.read_text()))
    report = {"upstream": tag, "python": sys.version.split()[0], "seed": args.seed, "families": {}}
    failed = False
    with tempfile.TemporaryDirectory(prefix="pystachy-json-repair-fuzz-") as scratch:
        scratch = Path(scratch)
        native = dict(os.environ, PYSTACHY_PATH=str(ROOT / "ports"))
        executable = scratch / "replay"
        subprocess.run([str(compiler), "build", str(REPLAY), "-o", str(executable)], env=native, check=True,
                       timeout=args.timeout)
        runs = [("port under CPython", [sys.executable, str(REPLAY)], hosted_env(ROOT / "ports")),
                ("native AOT", [str(executable)], native)]
        if args.jit:
            runs.append(("native JIT", [str(compiler), "run", str(REPLAY)], native))
        oracle_env = hosted_env(args.upstream.resolve() / "src")
        for family in args.family or FAMILIES:
            rows = requests(args.seed, args.cases, family, seeds)
            inputs = scratch / f"{family}.jsonl"
            inputs.write_text("".join(json.dumps(row) + "\n" for row in rows))
            oracle = replayed("upstream", [sys.executable, str(REPLAY)], oracle_env, inputs, args.timeout)
            entry = {"cases": len(rows), "texts": len({row["input"] for row in rows}),
                     "errors": checked(oracle, len(rows)), "differences": {}}
            report["families"][family] = entry
            checks = [(label, command, env, inputs, len(rows)) for label, command, env in runs]
            if args.gc_stress > 0:
                first = scratch / f"{family}-stress.jsonl"
                first.write_text("".join(json.dumps(row) + "\n" for row in rows[:args.gc_stress]))
                checks.append(("native AOT, stressed collector", [str(executable)], dict(native, PYSTACHY_GC_STRESS="1"),
                               first, min(args.gc_stress, len(rows))))
            for label, command, env, path, count in checks:
                try:
                    output = replayed(label, command, env, path, args.timeout)
                    bad, kept = differing(oracle, output, count)
                    output.unlink()  # (a long family's output is a gigabyte)
                except (ValueError, OSError, subprocess.SubprocessError) as error:
                    # One replay that fails or runs out of time fails the run, and the others' results stay.
                    entry["differences"][label] = {"error": str(error)[:2000]}
                    failed = True
                    print(f"{family}: {label}: no result: {str(error)[:300]}", flush=True)
                    continue
                entry["differences"][label] = [dict(rows[ident], expected=expected) for ident, expected in kept.items()]
                failed = failed or len(bad) > 0
                print(f"{family}: {label}: {count - len(bad)}/{count} match upstream {tag}", flush=True)
                for ident in bad[:5]:
                    print("  " + json.dumps(rows[ident], ensure_ascii=True))
            oracle.unlink()
    report["result"] = "fail" if failed else "pass"
    if args.report:
        args.report.write_text(json.dumps(report, ensure_ascii=True, indent=2) + "\n")
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        sys.exit(f"json-repair-fuzz: {error}")
