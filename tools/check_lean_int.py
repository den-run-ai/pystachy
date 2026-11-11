#!/usr/bin/env python3
"""Check a typed-after snapshot's promoting-int fit claims with Lean (tools/lean_boundary/INT.md).

After the general pys_big_op, bigints.gen_big_arith replaces the result's digit pointer with null
under a condition that gen_big_known computes from the operands: a claim that the result fits in
64 bits. This finds each such select, reads its condition as a formula over the operands' atoms
(each fits: its digit pointer is null; each one's word is not negative) and requires the Lean
checker to accept it (PystachyInt.implies, which PystachyInt.known_fits proves sound)."""

import argparse
import concurrent.futures
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import check_lean_boundary as bridge

ROOT = bridge.ROOT
DEFAULT_CHECKER = ROOT / "tools/lean_boundary/.lake/build/bin/pystachy-int"
# bigints.BIGOPS's codes of the operators that have a fit rule
RULES = {4: "%", 9: ">>", 5: "&"}
MAX_DEPTH = 64
OUTCOMES = bridge.OUTCOMES
SEVERITY = bridge.SEVERITY
Unsupported = bridge.Unsupported
require = bridge.require
LIMITATIONS = [
    "Only null digit pointers selected after pys_big_op (gen_big_known's claims) are checked.",
    "The representation (a digit pointer is null exactly where the value fits, and the word is "
    "then the value), the runtime's operators and LLVM lowering are trusted.",
]


def definitions(fn):
    """Each result's defining operation, by its IR name (%tN)."""
    found = {}
    for block in fn["blocks"]:
        for op in block["operations"]:
            for number in op.get("results", []):
                require(type(number) is int, "invalid result number")
                found[f"%t{number}"] = op
    return found


def literal_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def operands(op):
    return [operand["value"] for operand in op.get("operands", [])]


def identity(value, defs):
    """A promoting int's identity: its IR value, or the constant a big.make of literals is."""
    op = defs.get(value)
    if op is not None and op["op"] == "big.make":
        lo, hi = operands(op)
        if literal_int(lo) is not None and hi == "null":
            return ("constant", literal_int(lo))
    return ("value", value)


def operand_identity(lo, hi, defs):
    """The identity of pys_big_op's operand passed as its word lo and digit pointer hi."""
    if literal_int(lo) is not None and hi == "null":
        return ("constant", literal_int(lo))
    lo_op, hi_op = defs.get(lo), defs.get(hi)
    if (lo_op is None or hi_op is None or lo_op["op"] != "big.lo" or hi_op["op"] != "big.hi"
            or operands(lo_op) != operands(hi_op)):
        raise Unsupported("a pys_big_op operand that is not one promoting int's word and digits")
    return identity(operands(lo_op)[0], defs)


def formula(value, x, y, defs, depth=0):
    """The condition value as a checker formula over the atoms of operands x and y."""
    if depth > MAX_DEPTH:
        raise Unsupported("a fit condition nests too deeply")
    if value in ("true", "false"):
        return value == "true"
    op = defs.get(value)
    if op is None:
        raise Unsupported(f"a fit condition that is not computed here: {value}")
    args = operands(op)
    if op["op"] == "scalar.bin" and op.get("text") in ("and", "or") and len(args) == 2:
        return {op["text"]: [formula(args[0], x, y, defs, depth + 1), formula(args[1], x, y, defs, depth + 1)]}
    if op["op"] == "scalar.cmp" and len(args) == 2 and args[1] == "0":
        source = defs.get(args[0])
        if op.get("text") == "eq" and source is not None and source["op"] == "scalar.cast" \
                and source.get("text") == "ptrtoint":
            hi = defs.get(operands(source)[0])
            if hi is not None and hi["op"] == "big.hi":
                return atom("fits", identity(operands(hi)[0], defs), x, y)
        if op.get("text") == "sge":
            if literal_int(args[0]) is not None:
                return literal_int(args[0]) >= 0
            if source is not None and source["op"] == "big.lo":
                return atom("nonneg", identity(operands(source)[0], defs), x, y)
    raise Unsupported(f"a fit condition operation outside the atoms: {op['op']} {op.get('text', '')}")


def atom(kind, which, x, y):
    if which == x:
        return kind + "X"
    if which == y:
        return kind + "Y"
    raise Unsupported(f"a fit condition about a value other than the operands: {which[1]}")


def result_projection(value, kind, defs):
    """The big.op result whose low word or digits this value projects, if any."""
    projection = defs.get(value)
    if projection is None or projection["op"] != kind:
        return None
    args = operands(projection)
    require(len(args) == 1, f"{kind} takes one operand")
    call = defs.get(args[0])
    return args[0] if call is not None and call["op"] == "rt" and call.get("text") == "big.op" else None


def result_word(value, defs):
    """Trace gen_big_arith's result word through either operand of its AND masks.

    A second inventory starts at reconstruction, rather than at a particular
    select shape, so removing or changing that select cannot erase its claim.
    Other arithmetic and general value provenance remain outside this checker.
    """
    pending, seen, sources = [(value, 0)], set(), set()
    while pending:
        value, depth = pending.pop()
        if depth >= MAX_DEPTH:
            raise Unsupported("a result word's AND masks nest too deeply")
        if value in seen:
            continue
        seen.add(value)
        if len(seen) > bridge.MAX_INSTRUCTIONS:
            raise Unsupported("a result word's AND masks exceed the instruction bound")
        result = result_projection(value, "big.lo", defs)
        if result is not None:
            sources.add(result)
            if len(sources) > 1:
                raise Unsupported("a result word's AND masks mix multiple pys_big_op results")
            continue
        op = defs.get(value)
        if op is None or op["op"] != "scalar.bin" or op.get("text") != "and":
            continue
        args = operands(op)
        require(len(args) == 2, "an AND mask takes two operands")
        pending.extend((arg, depth + 1) for arg in args)
    return next(iter(sources)) if sources else None


def supported_replacement(value, result, defs):
    """Only the true arm may discard this result's digits in the proved form."""
    op = defs.get(value)
    args = operands(op) if op is not None else []
    return (op is not None and op["op"] == "select" and op.get("type") == "%ptr"
            and len(args) == 3 and args[1] == "null"
            and result_projection(args[2], "big.hi", defs) == result)


def known_claims(fn):
    """(block, claim) for each null digit pointer selected for a pys_big_op result."""
    defs = definitions(fn)
    claims = []
    # Inventory reconstructions independently of select recognition. Otherwise
    # a direct null, swapped arms or a changed source silently removes a claim.
    for block in fn["blocks"]:
        for op in block["operations"]:
            if op["op"] != "big.make":
                continue
            args = operands(op)
            require(len(args) == 2, "big.make takes two operands")
            result = result_word(args[0], defs)
            if result is not None and result_projection(args[1], "big.hi", defs) != result \
                    and not supported_replacement(args[1], result, defs):
                raise Unsupported("unrecognized digit replacement while reconstructing a pys_big_op result")
    for block in fn["blocks"]:
        for op in block["operations"]:
            args = operands(op)
            if op["op"] != "select" or op.get("type") != "%ptr" or len(args) != 3:
                continue
            if args[2] == "null" and result_projection(args[1], "big.hi", defs) is not None:
                raise Unsupported("a pys_big_op digit replacement selects null on its false arm")
            if args[1] != "null":
                continue
            hi = defs.get(args[2])
            if hi is None or hi["op"] != "big.hi":
                continue
            call = defs.get(operands(hi)[0])
            if call is None or call["op"] != "rt" or call.get("text") != "big.op":
                continue
            values = operands(call)
            require(len(values) == 5, "pys_big_op takes five operands")
            code = literal_int(values[4])
            if code not in RULES:
                raise Unsupported(f"a null digit pointer selected for operator code {values[4]}")
            x = operand_identity(values[0], values[1], defs)
            y = operand_identity(values[2], values[3], defs)
            claims.append((block["label"], {"op": RULES[code], "cond": formula(args[0], x, y, defs)}))
    return claims


def run_checker(checker, claims):
    """The Lean checker's verdict on each claim."""
    encoded = json.dumps({"claims": claims}, sort_keys=True, separators=(",", ":")) + "\n"
    require(len(encoded.encode()) <= bridge.MAX_BYTES, "claims exceed the checker input bound")
    completed = subprocess.run([str(Path(checker).resolve())], input=encoded, capture_output=True,
                               text=True, timeout=60)
    result = json.loads(completed.stdout, object_pairs_hook=bridge.unique_object)
    require(isinstance(result, dict) and isinstance(result.get("results"), list)
            and len(result["results"]) == len(claims)
            and all(type(verdict) is bool for verdict in result["results"]),
            "checker did not return a verdict for each claim")
    require(completed.returncode == (0 if all(result["results"]) else 1), "checker result/exit status mismatch")
    return result["results"]


def check_all(snapshot, checker=DEFAULT_CHECKER):
    """Check every fit claim of the snapshot. The report's fields and the worst result's exit code."""
    bridge.check_header(snapshot)
    functions = snapshot.get("functions")
    require(isinstance(functions, list), "invalid functions list")
    records = []
    pending = []
    for fn in functions:
        require(isinstance(fn, dict) and isinstance(fn.get("blocks"), list), "invalid function record")
        symbol = bridge.name(fn.get("symbol"), "function symbol")
        try:
            claims = known_claims(fn)
        except Unsupported as error:
            records.append({"function": symbol, "status": "unsupported", "message": str(error)})
            continue
        if claims:
            records.append({"function": symbol, "status": "accepted", "claims": len(claims)})
            pending += [(records[-1], block, claim) for block, claim in claims]
    if pending:
        verdicts = run_checker(checker, [claim for _, _, claim in pending])
        for (record, block, claim), verdict in zip(pending, verdicts, strict=True):
            if not verdict:
                record["status"] = "rejected"
                record.setdefault("unproved", []).append(dict(claim, block=block))
    worst = max((record["status"] for record in records), key=SEVERITY.index, default="accepted")
    totals = {"functions": len(functions), "claim_functions": sum("claims" in record for record in records),
              "claims": len(pending),
              "proved_claims": sum(record.get("claims", 0) for record in records if record["status"] == "accepted"),
              **{status: sum(record["status"] == status for record in records) for status in SEVERITY}}
    return {"status": worst, "functions": records, "totals": totals, "limitations": LIMITATIONS}, OUTCOMES[worst]


def evaluate(checker, items):
    """The model's values of x op y (None where Python raises), for comparison with CPython's."""
    encoded = json.dumps({"eval": [{"op": op, "x": str(x), "y": str(y)} for op, x, y in items]}) + "\n"
    completed = subprocess.run([str(Path(checker).resolve())], input=encoded, capture_output=True,
                               text=True, timeout=60)
    require(completed.returncode == 0, f"checker failed: {completed.stdout}{completed.stderr}")
    values = json.loads(completed.stdout)["values"]
    require(len(values) == len(items), "checker did not evaluate each item")
    return [None if value is None else int(value) for value in values]


PRAGMA = "# pystachy: python-int"


def corpus():
    """Every differential test program and deviation of a module that opts in to promoting ints."""
    found = sorted(path for pattern in ("tests/programs/*/*.py", "tests/deviations/*.py")
                   for path in ROOT.glob(pattern)
                   if PRAGMA.encode() in (line.strip() for line in path.read_bytes().splitlines()))
    require(found, "no program opts in to promoting ints")
    return found


def check_program(path, checker):
    """Compile one program with the hosted compiler and check its snapshot's fit claims."""
    env = {key: value for key, value in os.environ.items() if not key.startswith("PYSTACHY_")}
    env["PYSTACHY_HOME"] = str(ROOT)
    if path.with_suffix(".path").is_file():
        env["PYSTACHY_PATH"] = path.with_suffix(".path").read_text().strip()
    record = {"program": str(path.relative_to(ROOT))}
    with tempfile.TemporaryDirectory(prefix="pystachy-lean-int-") as directory:
        output = Path(directory) / "inspection"
        subprocess.run([sys.executable, str(ROOT / "tools/inspect_compiler.py"), str(path), "--output", str(output),
                        "--typed-after-only", "--timeout", "600"], cwd=ROOT, env=env, capture_output=True,
                       text=True, timeout=700)
        try:
            inspection = json.loads((output / "report.json").read_text())
            require(inspection.get("status") == "ok", f"inspection {inspection.get('status')}")
            snapshot, digest = bridge.read_snapshot(output / "typed-after.json", bridge.MAX_PROGRAM_BYTES)
            fields, _ = check_all(snapshot, checker)
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            return dict(record, status="error", message=str(error))
    return dict(record, status=fields["status"], snapshot_sha256=digest, totals=fields["totals"],
                failures=[item for item in fields["functions"] if item["status"] != "accepted"])


def check_corpus(checker, jobs):
    started = time.monotonic()
    programs = corpus()
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
        records = list(pool.map(lambda path: check_program(path, checker), programs))
    worst = max((record["status"] for record in records), key=SEVERITY.index)
    totals = {key: sum(record.get("totals", {}).get(key, 0) for record in records)
              for key in ("claim_functions", "claims", "proved_claims")}
    totals.update(programs=len(records), claim_programs=sum(bool(record.get("totals", {}).get("claims"))
                                                             for record in records),
                  failed_programs=sum(record["status"] != "accepted" for record in records))
    if worst == "accepted" and totals["claims"] == 0:
        worst = "unsupported"  # (no claim found: the adapter no longer recognizes the compiler's)
    return {"status": worst, "totals": totals, "programs": records, "limitations": LIMITATIONS,
            "seconds": round(time.monotonic() - started, 1)}, OUTCOMES[worst]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--snapshot", type=Path)
    selection.add_argument("--corpus", action="store_true",
                           help="compile and check every test program that opts in to promoting ints")
    parser.add_argument("--checker", type=Path, default=DEFAULT_CHECKER)
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--report", type=Path, help="write the corpus report here")
    args = parser.parse_args(argv)
    if args.corpus:
        report, code = check_corpus(args.checker, max(1, args.jobs))
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(report, sort_keys=True, indent=1) + "\n")
        totals = report["totals"]
        print(f"check_lean_int: {report['status']}: {totals['programs']} programs, {totals['claim_programs']} "
              f"with fit claims, {totals['proved_claims']} of {totals['claims']} claims proved "
              f"({report['seconds']} s)")
        for record in report["programs"]:
            if record["status"] != "accepted":
                print(f"  {record['status']}: {record['program']}: "
                      f"{record.get('message') or record.get('failures')}")
        return code
    report = {}
    try:
        snapshot, digest = bridge.read_snapshot(args.snapshot, bridge.MAX_PROGRAM_BYTES)
        report["snapshot_sha256"] = digest
        fields, code = check_all(snapshot, args.checker)
        report.update(fields)
    except Unsupported as error:
        report.update(status="unsupported", message=str(error))
        code = OUTCOMES["unsupported"]
    except (OSError, ValueError, subprocess.SubprocessError, RecursionError) as error:
        report.update(status="error", message=str(error))
        code = OUTCOMES["error"]
    print(json.dumps(report, sort_keys=True))
    return code


if __name__ == "__main__":
    sys.exit(main())
