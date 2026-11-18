#!/usr/bin/env python3
"""A text form of typed-IR functions, with its printer and parser.

A function record holds what the inspection snapshots hold of one function's IR: its symbol,
parameters, return type, slots, blocks, check targets and loops. `format_function` prints a
record, `parse_function` reads one back, and the two are inverse: parse(format(r)) == r for
every record, and format(parse(t)) == t for every text that format printed. `to_ifn` builds
the compiler's own IFn from a record, so a test can write IR as text, run the verifier or a
pass on it and compare the printed result; `from_ifn` is its inverse.

    python3 tools/typed_ir_text.py print typed-after.json [--function NAME]
    python3 tools/typed_ir_text.py check FILE.tir          # parse, print again, compare
    python3 tools/typed_ir_text.py json FILE.tir           # the records, as JSON

One instruction is one line:

    [%N ... = ] op [s=TEXT] [k=INT] [x=DESCRIPTOR] [(TYPE VALUE, ...)] [-> LABEL, ...] [: TYPE]

    %12 = num.cmp s=< (int %t10, int %t11) : bool
    cbr(bool %t12) -> L13, L9

An atom (a type, a value, a label, a text) is written bare where that is unambiguous, else as
a JSON string. The form is for tests and review. It is no stable interchange format, and it
holds no module data, class layouts or runtime declarations.
"""
import argparse
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent

LOOP_ATOMS = ("kind", "mode", "head", "body", "step", "exit", "counter")
LOOP_LISTS = ("tests", "indices")
DECODER = json.JSONDecoder()


class TextError(ValueError):
    """Text that is no typed-IR function, with the line that shows it."""


def require(condition, message):
    if not condition:
        raise TextError(message)


def scan_bare(text, at, stops=""):
    """The end of the bare atom of text that starts at `at`."""
    depth = 0
    end = at
    while end < len(text):
        c = text[end]
        if c.isspace() or c in '"()' or c in stops:
            break
        if c == "[":
            depth += 1
        elif c == "]":
            if depth == 0:
                break
            depth -= 1
        elif c == "," and depth == 0:
            break
        end += 1
    return end, depth


def atom(value, stops=""):
    """An atom's text: itself where the parser reads that back, else a JSON string."""
    require(isinstance(value, str), f"an atom must be a string, not {value!r}")
    end, depth = scan_bare(value, 0, stops)
    if value != "" and end == len(value) and depth == 0:
        return value
    return json.dumps(value, ensure_ascii=False)


def read_atom(text, at, stops=""):
    """(the atom at `at`, the position after it)."""
    require(at < len(text), "expected an atom at the end of the line")
    if text[at] == '"':
        try:
            value, end = DECODER.raw_decode(text, at)
        except json.JSONDecodeError as error:
            raise TextError(f"invalid quoted atom: {error.msg}") from None
        require(isinstance(value, str), "a quoted atom must be a string")
        require(atom(value, stops) != value, f"atom {value!r} must be written bare")
        return value, end
    end, depth = scan_bare(text, at, stops)
    require(end > at and depth == 0, f"expected an atom at column {at + 1}")
    return text[at:end], end


def expect(text, at, token):
    require(text.startswith(token, at), f"expected {token!r} at column {at + 1}")
    return at + len(token)


def operand_text(operand):
    return atom(operand["type"]) + " " + atom(operand["value"])


def read_operand(text, at):
    t, at = read_atom(text, at)
    at = expect(text, at, " ")
    v, at = read_atom(text, at)
    return {"value": v, "type": t}, at


def read_operands(text, at):
    """The operands of "(T V, T V)" whose "(" is at `at`."""
    at = expect(text, at, "(")
    operands = []
    while True:
        operand, at = read_operand(text, at)
        operands.append(operand)
        if text.startswith(")", at):
            return operands, at + 1
        at = expect(text, at, ", ")


def instruction_text(ins):
    require(isinstance(ins["immediate"], int) and not isinstance(ins["immediate"], bool), "an immediate must be an integer")
    require(re.fullmatch(r"[a-z]+(\.[a-z]+)?", ins["op"]) is not None, f"invalid operation name {ins['op']!r}")
    parts = []
    if ins["results"]:
        require(all(isinstance(r, int) and not isinstance(r, bool) for r in ins["results"]), "result numbers must be integers")
        parts.append(" ".join(f"%{r}" for r in ins["results"]) + " = ")
    parts.append(ins["op"])
    if ins["text"] != "":
        parts.append(" s=" + atom(ins["text"]))
    if ins["immediate"] != 0:
        parts.append(f" k={ins['immediate']}")
    if ins["descriptor"] != "":
        parts.append(" x=" + atom(ins["descriptor"]))
    if ins["operands"]:
        # (a space after a field, so that "s=<" does not run into the list)
        parts.append((" (" if len(parts) > (2 if ins["results"] else 1) else "(")
                     + ", ".join(operand_text(a) for a in ins["operands"]) + ")")
    if ins["targets"]:
        parts.append(" -> " + ", ".join(atom(label) for label in ins["targets"]))
    if ins["type"] != "":
        parts.append(" : " + atom(ins["type"]))
    return "".join(parts)


def read_instruction(text):
    at = 0
    results = []
    numbered = re.match(r"((?:%-?\d+ )+)= ", text)
    if numbered:
        results = [int(r[1:]) for r in numbered.group(1).split()]
        at = numbered.end()
    name = re.compile(r"[a-z]+(\.[a-z]+)?").match(text, at)
    require(name is not None, "expected an operation name")
    op = name.group(0)
    at = name.end()
    s = x = t = ""
    k = 0
    if text.startswith(" s=", at):
        s, at = read_atom(text, at + 3)
        require(s != "", "an empty text is omitted")
    if text.startswith(" k=", at):
        number = re.compile(r"-?\d+").match(text, at + 3)
        require(number is not None and int(number.group(0)) != 0 and str(int(number.group(0))) == number.group(0),
                "k= needs a nonzero integer")
        k, at = int(number.group(0)), number.end()
    if text.startswith(" x=", at):
        x, at = read_atom(text, at + 3)
        require(x != "", "an empty descriptor is omitted")
    operands = []
    fielded = s != "" or k != 0 or x != ""
    if text.startswith(" (" if fielded else "(", at):
        operands, at = read_operands(text, at + (1 if fielded else 0))
    targets = []
    if text.startswith(" -> ", at):
        at += 4
        while True:
            label, at = read_atom(text, at)
            targets.append(label)
            if not text.startswith(", ", at):
                break
            at += 2
    if text.startswith(" : ", at):
        t, at = read_atom(text, at + 3)
        require(t != "", "an empty type is omitted")
    require(at == len(text), f"unexpected text at column {at + 1}: {text[at:]!r}")
    return {"op": op, "type": t, "text": s, "immediate": k, "descriptor": x,
            "results": results, "operands": operands, "targets": targets}


def loop_text(loop):
    parts = ["loop"]
    for key in loop:
        value = loop[key]
        if key in LOOP_ATOMS:
            parts.append(f"{key}={atom(value)}")
        elif key in LOOP_LISTS:
            parts.append(f"{key}=[{' '.join(atom(v) for v in value)}]")
        elif key == "stop":
            parts.append(f"stop=({operand_text(value)})")
        elif key == "sequences":
            parts.append("sequences=[" + " ".join(f"({operand_text(v)})" for v in value) + "]")
        elif key == "nonnegative":
            require(isinstance(value, bool), "nonnegative must be a boolean")
            parts.append(f"nonnegative={'true' if value else 'false'}")
        else:
            raise TextError(f"unknown loop field {key!r}")
    return " ".join(parts)


def read_loop(text):
    at = len("loop")
    loop = {}
    while at < len(text):
        at = expect(text, at, " ")
        key = re.compile(r"[a-z]+=").match(text, at)
        require(key is not None, f"expected a loop field at column {at + 1}")
        name = key.group(0)[:-1]
        require(name not in loop, f"loop field {name} is repeated")
        at = key.end()
        if name in LOOP_ATOMS:
            loop[name], at = read_atom(text, at)
        elif name in LOOP_LISTS:
            at = expect(text, at, "[")
            values = []
            while not text.startswith("]", at):
                if values:
                    at = expect(text, at, " ")
                value, at = read_atom(text, at)
                values.append(value)
            loop[name], at = values, at + 1
        elif name == "stop":
            operands, at = read_operands(text, at)
            require(len(operands) == 1, "stop is one operand")
            loop[name] = operands[0]
        elif name == "sequences":
            at = expect(text, at, "[")
            values = []
            while not text.startswith("]", at):
                if values:
                    at = expect(text, at, " ")
                operands, at = read_operands(text, at)
                require(len(operands) == 1, "a sequence is one operand")
                values.append(operands[0])
            loop[name], at = values, at + 1
        elif name == "nonnegative":
            word = re.compile(r"true|false").match(text, at)
            require(word is not None, "nonnegative is true or false")
            loop[name], at = word.group(0) == "true", word.end()
        else:
            raise TextError(f"unknown loop field {name!r}")
    return loop


def format_function(record):
    """The text of one function record."""
    header = "function " + atom(record["symbol"])
    header += "(" + ", ".join(atom(p["name"], ":") + ": " + atom(p["type"]) for p in record["parameters"]) + ")"
    header += " -> " + atom(record["return"])
    require(isinstance(record["coroutine"], bool), "coroutine must be a boolean")
    if record["coroutine"]:
        header += " coroutine"
    if record["effects"] is not None:
        header += " effects=" + atom(record["effects"])
    lines = [header + " {"]
    for slot in record["slots"]:
        lines.append("  " + instruction_text(slot))
    for block in record["blocks"]:
        head = atom(block["label"], ":") + ":"
        if block["handler"] != "":
            head += " handler=" + atom(block["handler"])
        lines.append(head)
        lines.extend("  " + instruction_text(i) for i in block["operations"])
    for key in record["check_targets"]:
        lines.append(f"cold {atom(key)} -> {atom(record['check_targets'][key])}")
    for loop in record["loops"]:
        lines.append(loop_text(loop))
    lines.append("}")
    return "\n".join(lines) + "\n"


def read_header(text):
    at = expect(text, 0, "function ")
    symbol, at = read_atom(text, at)
    at = expect(text, at, "(")
    parameters = []
    while not text.startswith(")", at):
        if parameters:
            at = expect(text, at, ", ")
        name, at = read_atom(text, at, ":")
        at = expect(text, at, ": ")
        t, at = read_atom(text, at)
        parameters.append({"name": name, "type": t})
    at = expect(text, at + 1, " -> ")
    ret, at = read_atom(text, at)
    coroutine = text.startswith(" coroutine", at)
    if coroutine:
        at += len(" coroutine")
    effects = None
    if text.startswith(" effects=", at):
        effects, at = read_atom(text, at + len(" effects="))
    require(text[at:] == " {", f"expected ' {{' at column {at + 1}")
    return {"symbol": symbol, "parameters": parameters, "return": ret, "coroutine": coroutine,
            "effects": effects, "slots": [], "blocks": [], "check_targets": {}, "loops": []}


def parse_functions(text):
    """The function records of a text, in order. A full-line `;` comment and a blank line are skipped."""
    records = []
    record = None
    block = None
    tail = False  # after the first cold or loop line, no block follows
    for number, line in enumerate(text.split("\n"), 1):
        try:
            if line.strip() == "" or line.lstrip().startswith(";"):
                continue
            require(line == line.rstrip(), "trailing whitespace")
            if record is None:
                record, block, tail = read_header(line), None, False
            elif line == "}":
                records.append(record)
                record = None
            elif line.startswith("  "):
                require(not tail, "an instruction after the check targets or loops")
                ins = read_instruction(line[2:])
                if block is None:
                    require(ins["op"] == "slot", "an instruction before the first block must be a slot")
                    record["slots"].append(ins)
                else:
                    block["operations"].append(ins)
            elif line.startswith("cold "):
                tail = True
                key, at = read_atom(line, 5)
                at = expect(line, at, " -> ")
                label, at = read_atom(line, at)
                require(at == len(line), "unexpected text after a check target")
                require(key not in record["check_targets"], f"check target {key!r} is repeated")
                record["check_targets"][key] = label
            elif line.startswith("loop ") or line == "loop":
                tail = True
                record["loops"].append(read_loop(line))
            else:
                require(not tail, "a block after the check targets or loops")
                label, at = read_atom(line, 0, ":")
                at = expect(line, at, ":")
                handler = ""
                if line.startswith(" handler=", at):
                    handler, at = read_atom(line, at + len(" handler="))
                    require(handler != "", "an empty handler is omitted")
                require(at == len(line), "unexpected text after a block label")
                block = {"label": label, "handler": handler, "operations": []}
                record["blocks"].append(block)
        except TextError as error:
            raise TextError(f"line {number}: {error}: {line!r}") from None
    require(record is None, "the last function has no closing brace")
    return records


def parse_function(text):
    records = parse_functions(text)
    require(len(records) == 1, f"expected one function, found {len(records)}")
    return records[0]


def from_snapshot(function):
    """The record of one function of an inspection snapshot (tools/inspect_compiler.py)."""
    return {
        "symbol": function["symbol"],
        "parameters": [{"name": p["name"], "type": p["representation"]} for p in function["parameters"]],
        "return": function["return_representation"],
        "coroutine": function["recursion"]["coroutine"],
        "effects": function["effects"],
        "slots": [dict(i, operands=[dict(a) for a in i["operands"]]) for i in function["slots"]],
        "blocks": [{"label": b["label"], "handler": b["handler"],
                    "operations": [dict(i, operands=[dict(a) for a in i["operands"]]) for i in b["operations"]]}
                   for b in function["blocks"]],
        "check_targets": dict(function["check_targets"]),
        "loops": [{"kind": lp["kind"], "mode": lp["mode"], "head": lp["head"], "body": lp["body"],
                   "step": lp["step"], "exit": lp["exit"], "tests": list(lp["tests"]),
                   "indices": list(lp["indices"])} for lp in function["loops"]],
    }


def compiler():
    """The hosted compiler's modules, imported on first use: text handling needs none of them."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from src.pystachy_compiler import ir, specs, symbols, syntax, utils
    return ir, specs, symbols, syntax, utils


def numbers(record):
    """Every value and label number a record names: IFn.n bounds them."""
    found = [0]
    for ins in record["slots"] + [i for b in record["blocks"] for i in b["operations"]]:
        found.extend(ins["results"])
        for value in [a["value"] for a in ins["operands"]] + ins["targets"]:
            match = re.fullmatch(r"%t(\d+)|L(\d+)|%.*\.(\d+)", value)
            if match:
                found.append(int(next(g for g in match.groups() if g is not None)))
    for block in record["blocks"]:
        match = re.fullmatch(r"L(\d+)", block["label"])
        if match:
            found.append(int(match.group(1)))
    return found


def to_ifn(record):
    """The compiler's IFn of a record: what the verifier, the passes and lowering take."""
    ir, specs, symbols, syntax, utils = compiler()
    name = record["symbol"].lstrip("@")
    f = symbols.FnInfo(name, record["symbol"], syntax.Node("def", name, 1), "")
    f.params = [p["name"] for p in record["parameters"]]
    f.ptypes = [p["type"] for p in record["parameters"]]
    f.ret = record["return"]
    fn = ir.IFn(f)
    fn.ps = [j for j, t in enumerate(f.ptypes) if t != "None"]
    fn.coro = record["coroutine"]
    if record["effects"] is not None:
        fn.fx = utils.fxmask(record["effects"])

    def instruction(ins):
        i = ir.Ins(ins["op"], ins["type"], ins["text"])
        i.k = ins["immediate"]
        i.x = ins["descriptor"]
        i.r = list(ins["results"])
        i.a = [ir.Val(a["value"], a["type"]) for a in ins["operands"]]
        i.b = list(ins["targets"])
        return i

    fn.slots = [instruction(i) for i in record["slots"]]
    fn.blocks = []
    for block in record["blocks"]:
        b = ir.Blk(block["label"])
        b.handler = block["handler"]
        b.code = [instruction(i) for i in block["operations"]]
        fn.blocks.append(b)
        for i in b.code:
            if i.op == "field.addr" and len(i.r) == 1:
                fn.fa[ir.tmpname(i.r[0])] = True
            fn.pads = fn.pads or i.op == "landing"
    fn.cold = dict(record["check_targets"])
    for loop in record["loops"]:
        lp = ir.Loop(loop["kind"], loop["head"], loop["body"], loop["step"], loop["exit"])
        lp.mode = loop["mode"]
        lp.tests = list(loop["tests"])
        lp.idx = list(loop["indices"])
        lp.ctr = loop.get("counter", "")
        stop = loop.get("stop", {"value": "", "type": ""})
        lp.stop = ir.Val(stop["value"], stop["type"])
        lp.seqs = [ir.Val(s["value"], s["type"]) for s in loop.get("sequences", [])]
        lp.nonnegative = loop.get("nonnegative", False)
        fn.loops.append(lp)
    fn.n = max(numbers(record))
    return fn


def from_ifn(fn):
    """The record of a compiler IFn, with each loop's full shape."""
    ir, specs, symbols, syntax, utils = compiler()

    def instruction(i):
        return {"op": i.op, "type": i.t, "text": i.s, "immediate": i.k, "descriptor": i.x, "results": list(i.r),
                "operands": [{"value": a.v, "type": a.t} for a in i.a], "targets": list(i.b)}

    f = fn.f
    return {
        "symbol": f.ll,
        "parameters": [{"name": name, "type": t} for name, t in zip(f.params, f.ptypes, strict=True)],
        "return": f.ret, "coroutine": fn.coro,
        "effects": utils.fxs(fn.fx),
        "slots": [instruction(i) for i in fn.slots],
        "blocks": [{"label": b.label, "handler": b.handler, "operations": [instruction(i) for i in b.code]}
                   for b in fn.blocks],
        "check_targets": dict(fn.cold),
        "loops": [{"kind": lp.kind, "mode": lp.mode, "head": lp.head, "body": lp.body, "step": lp.step,
                   "exit": lp.exit, "tests": list(lp.tests), "indices": list(lp.idx), "counter": lp.ctr,
                   "stop": {"value": lp.stop.v, "type": lp.stop.t},
                   "sequences": [{"value": s.v, "type": s.t} for s in lp.seqs],
                   "nonnegative": lp.nonnegative} for lp in fn.loops],
    }


def gen_for(fn):
    """A fresh code generator that has declared the runtime functions fn calls."""
    ir, specs, symbols, syntax, utils = compiler()
    from src.pystachy_compiler.gen import Gen
    g = Gen()
    for block in fn.blocks:
        for i in block.code:
            if i.op == "rt":
                require(i.s in specs.RUNTIME, f"no RUNTIME entry for {i.s}")
                g.runtime(specs.RUNTIME[i.s].split("|")[2] or "pys_" + i.s.replace(".", "_"))
    return g


def roundtrip_errors(record):
    """Why a record does not survive print and parse, or []."""
    try:
        text = format_function(record)
        parsed = parse_function(text)
    except TextError as error:
        return [f"{record.get('symbol', '?')}: {error}"]
    if parsed != record:
        return [f"{record['symbol']}: the parsed record differs from the printed one"]
    if format_function(parsed) != text:
        return [f"{record['symbol']}: printing the parsed record gives another text"]
    return []


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("mode", choices=("print", "check", "json"))
    parser.add_argument("path", type=Path)
    parser.add_argument("--function", default="", help="print: only functions whose symbol contains this")
    args = parser.parse_args()
    try:
        source = args.path.read_text(encoding="utf-8")
        if args.mode == "print":
            snapshot = json.loads(source)
            records = [from_snapshot(f) for f in snapshot["functions"] if args.function in f["symbol"]]
            problems = [e for r in records for e in roundtrip_errors(r)]
            if problems:
                print("\n".join(problems), file=sys.stderr)
                return 1
            sys.stdout.write("\n".join(format_function(r) for r in records))
            return 0
        records = parse_functions(source)
        if args.mode == "json":
            print(json.dumps(records, indent=1))
            return 0
        printed = "\n".join(format_function(r) for r in records)
        if printed != source:
            print(f"typed_ir_text: {args.path} is not in the printed form", file=sys.stderr)
            return 1
        print(f"typed_ir_text: {len(records)} functions parse and print unchanged")
        return 0
    except (OSError, KeyError, TypeError, ValueError) as error:
        print(f"typed_ir_text: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
