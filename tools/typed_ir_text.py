#!/usr/bin/env python3
"""A text form of typed-IR modules and functions, with its printer and parser.

A function record holds what the inspection snapshots hold of one function's IR: its symbol,
parameters, return type, slots, blocks, check targets and loops. A module record holds what a
typed-after snapshot holds: the program's classes, the DynTypes it emits and their classes'
layouts, and its function records. `format_module` and `format_function` print a record, `parse`
reads a text back, and they are inverse: parse(format(r)) == r for every record, and
format(parse(t)) == t for every text that format printed, where format prints locations
(locations=True); without them, both hold where no instruction has a location. `to_ifn` builds
the compiler's own IFn from a function record, so a test can write IR as text, run the verifier
or a pass on it and compare the printed result; `from_ifn` is its inverse.

    python3 tools/typed_ir_text.py print typed-after.json [--function NAME] [--locations]
    python3 tools/typed_ir_text.py check FILE.tir          # parse, print again, compare
    python3 tools/typed_ir_text.py json FILE.tir           # the records, as JSON
    python3 tools/typed_ir_text.py verify FILE.tir         # verify each function, as expected

`print` writes a typed-after snapshot as a module, and the functions alone where --function
selects some or the snapshot holds no module data (typed-before.json). The other modes read a
module or functions alone. A module gives its declarations, one a line, between `module {` and
`}`, and then its functions:

    module {
      class Both base=Storage roles=[Reader] tagged fields=[" class":int value:int " Storage.0":bool " Storage.box.0":dyn] flags=[value:2] boxes=[value:3]
      class Reader overlaps=[Storage] tagged fields=[" class":int]
      dyntype @dt.Both kind=8 cls=1 flags=256 base=@dt.Storage role=@dt.Reader payload=Both
      layout Both descriptor=@dt.Both base=@dt.Storage role=@dt.Reader number=1 members=[int int bool dyn] llvm=[i64 i64 i1 ptr]
    }

    class NAME [base=CLASS] [roles=[CLASS ...]] [overlaps=[CLASS ...]] [tagged] [fields=[FIELD:TYPE ...]] [flags=[FIELD:INT ...]] [boxes=[FIELD:INT ...]]
    dyntype SYMBOL kind=INT cls=INT [flags=INT] [base=SYMBOL] [role=SYMBOL] [payload=TYPE]
    layout NAME descriptor=SYMBOL [base=SYMBOL] [role=SYMBOL] number=INT [members=[TYPE ...]] [llvm=[TYPE ...]]

A class gives its single base (a class or a builtin exception class), its fieldless secondary
bases, the unrelated classes it shares a subclass with, whether its objects begin with a class
tag, and its struct as field.addr indexes it: its fields in order with their types (a hidden
field's name begins with a space, so it is quoted), and the index of each field's "is
assigned" flag and identity box (ClassInfo.fflag and fbox). Its own flags take the indexes
after its fields and its own boxes those after its flags; a base's are among its fields
(" Storage.0" and " Storage.box.0"), as a derived class's struct begins with its base's
(flow.gen_fl_fields). A dyntype gives a DynType's kind, class number, flags, base and role
DynTypes and its boxes' payload type (dynamic.py); a layout, the struct of a class that has a
DynType, by its members' types and their LLVM types (inspect_compiler.py's classes,
dynamic_types and dynamic_layouts). Classes come first, then dyntypes, then layouts; a field
that holds its default ("", [], {}, 0 or false) is omitted.

One instruction is one line:

    [RESULT ... = ] op [OPERATOR] [NAME=VALUE ...] [(TYPE VALUE, ...)] [-> LABEL, ...] [: TYPE] [loc([FILE:]LINE)]

    %t12 = num.cmp < (int %t10, int %t11) : bool
    ~%t6 %t7 %t8 = ovf + (int %t4, int %t5) : int
    %xs.2 = slot name=xs : list[int]
    %t11 = rt entry=repr descriptor=Li (*T %t10, # @s.2) : str
    %t8 = field.addr index=1 (Point %t7) : *int
    cbr(bool %t12) -> L13, L9

A result is written as operands name it: %tN, or a slot's register (ir.slot_register). A ~
marks a temporary of the op's lowering (OP_TEMPS), which no operand names; printing and parsing
read those, and slot registers, from the compiler. The fields Ins.s, Ins.k and Ins.x follow the
op's name, in that order, each by the name its row of the operation table gives it (specs.OPS:
s:entry, k:index), but an operator, which selects the op's computation (num.cmp's <), is written
bare, first. A field that holds its default ("" or 0) is omitted, and one that the op's row
does not name is written s=, k= or x=, so that a record the verifier rejects still prints.

An instruction's location is the line of the statement it implements (Ins.line). A record
holds it as the compiler numbers lines, a file's index times diagnostics.LINES plus the line,
and 0 where it is unknown. The text holds it only where asked to, as MLIR prints locations
only with -mlir-print-debuginfo: `loc(12)` is line 12 of the program's main file, and
`loc(3:12)` line 12 of its file 3 (diagnostics.FILES[3]; a snapshot lists them as `files`).
An instruction without one reads as 0.

An atom (a type, a value, a label, a text, a name) is written bare where that is unambiguous,
else as a JSON string. The form is for tests and review. It is no stable interchange format,
and it holds no globals or runtime declarations.

`verify` runs the compiler's verifier (PYSTACHY_IRCHECK=1's) on each function, as MLIR's
-verify-diagnostics does. A comment line `; expected-error {{MESSAGE}}` in a function says that
its verification must fail with an error that contains MESSAGE, in the block the line is in
(before the first block: that block); a function without one must verify. The verifier stops
at its first error, so a function expects one at most. A module's functions are verified with
its classes (class_infos): the class view of an operand's type (specs.TYPE_VIEWS) relates them
by their bases, secondary bases and overlaps, and a field.addr addresses a member of its
operand's class's struct, of that member's declared type. A function list declares no class.
"""
import argparse
from contextlib import redirect_stderr
from io import StringIO
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent

LOOP_ATOMS = ("kind", "mode", "head", "body", "step", "exit", "counter")
LOOP_LISTS = ("tests", "indices")
# A module's declarations, by keyword, in the order a module gives them: the module record's
# table that holds them, the key of a declaration's name in its record ("" where the table maps
# names to records), and its fields in the order they are written: (key, kind, default). A field
# that holds its default is omitted (None: none, it is always written). Kinds: an atom, an int, a
# list of atoms, a flag, written as its bare key where it is true, a list of typed names (each
# {"name", "type"}, written NAME:TYPE) or a dict of names to ints (NAME:INT).
DECLARATIONS = {
    "class": ("classes", "", (("base", "atom", ""), ("roles", "list", []), ("overlaps", "list", []),
                              ("tagged", "flag", False), ("fields", "typed", []), ("flags", "indexed", {}),
                              ("boxes", "indexed", {}))),
    "dyntype": ("dynamic_types", "symbol", (("kind", "int", None), ("cls", "int", None), ("flags", "int", 0),
                                           ("base", "atom", ""), ("role", "atom", ""), ("payload", "atom", ""))),
    "layout": ("dynamic_layouts", "name", (("descriptor", "atom", None), ("base", "atom", ""), ("role", "atom", ""),
                                          ("number", "int", None), ("members", "list", []), ("llvm", "list", []))),
}
MODULE_KEYS = [table for table, _, _ in DECLARATIONS.values()] + ["functions"]
# each kind's Python type in a record, and what a message calls a value of it
KINDS = {"atom": (str, "an atom"), "int": (int, "an int"), "list": (list, "a list"), "flag": (bool, "a flag"),
         "typed": (list, "a list of names with types"), "indexed": (dict, "a dict of names to ints")}
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


FIELD = re.compile(r" ([a-z]+)=")


def text_atom(value):
    """An op's operator, after its name: an atom, quoted where it would read as a named field or a
    separator."""
    written = atom(value)
    if written == value and (value in ("->", ":") or FIELD.match(" " + value)):
        return json.dumps(value, ensure_ascii=False)
    return written


def read_text_atom(text, at):
    """(the op's operator at `at`, the position after it), written as text_atom writes it."""
    if text.startswith('"', at):
        try:
            value, end = DECODER.raw_decode(text, at)
        except json.JSONDecodeError as error:
            raise TextError(f"invalid quoted atom: {error.msg}") from None
        require(isinstance(value, str), "a quoted atom must be a string")
    else:
        end, depth = scan_bare(text, at)
        require(end > at and depth == 0, f"expected an atom at column {at + 1}")
        value = text[at:end]
    require(text[at:end] == text_atom(value), f"operator {value!r} must be written {text_atom(value)}")
    return value, end


# The fields of an instruction record that an instruction writes, in order: Ins.s, Ins.k, Ins.x
FIELD_KEYS = (("s", "text"), ("k", "immediate"), ("x", "descriptor"))
# the name of the field that selects an op's computation, which an instruction writes bare
OPERATOR = "operator"
NAMED = {}


def named_fields(op):
    """The names that op's row of the operation table gives its fields ({"s": "entry"}), read on
    first use; {} for an op the table lacks."""
    if op not in NAMED:
        ops = compiler()[1].OPS
        NAMED[op] = {f[0]: f[2:] for f in ops[op].split("|")[4].split() if f != "t"} if op in ops else {}
    return NAMED[op]


def row_fields(op):
    """What op's row names, for a message: entry (s), hole (k), or none."""
    return ", ".join(f"{name} ({field})" for field, name in named_fields(op).items()) or "none"


def slot_name(text, immediate, number):
    """A slot's register, which its uses name (ir.slot_register)."""
    ir = compiler()[0]
    slot = ir.Ins("slot", "", text)
    slot.k = immediate
    slot.r = [number]
    return ir.slot_register(slot)


def result_names(ins):
    """An instruction's results as operands name them: a slot's register, else %tN, with a ~
    before each lowering temporary (OP_TEMPS), which no operand may name."""
    if ins["op"] == "slot":
        require(len(ins["results"]) == 1, "a slot has one number")
        return [slot_name(ins["text"], ins["immediate"], ins["results"][0])]
    temps = compiler()[1].OP_TEMPS.get(ins["op"], [])
    return [("~" if j in temps else "") + f"%t{r}" for j, r in enumerate(ins["results"])]


def lines_per_file():
    """diagnostics.LINES: the lines of file K are numbered from K times it."""
    compiler()
    from src.pystachy_compiler.diagnostics import LINES
    return LINES


def location_text(line):
    """An instruction's location (a nonzero line, as the compiler numbers lines) as text."""
    per = lines_per_file()
    return f"loc({line})" if line < per else f"loc({line // per}:{line % per})"


LOCATION = re.compile(r" loc\((\d+)(?::(\d+))?\)$")


def instruction_text(ins, locations=False):
    require(isinstance(ins["immediate"], int) and not isinstance(ins["immediate"], bool), "an immediate must be an integer")
    require(type(ins.get("line")) is int and ins["line"] >= 0, "a line must be a nonnegative integer")
    require(re.fullmatch(r"[a-z]+(\.[a-z]+)?", ins["op"]) is not None, f"invalid operation name {ins['op']!r}")
    parts = []
    if ins["results"]:
        require(all(isinstance(r, int) and not isinstance(r, bool) for r in ins["results"]), "result numbers must be integers")
        parts.append(" ".join(result_names(ins)) + " = ")
    parts.append(ins["op"])
    names = named_fields(ins["op"])
    fielded = False
    for field, key in FIELD_KEYS:
        value = ins[key]
        if value == (0 if field == "k" else ""):
            continue
        name = names.get(field, field)
        if name == OPERATOR:
            parts.append(" " + text_atom(value))
        else:
            parts.append(f" {name}=" + (str(value) if field == "k" else atom(value)))
        fielded = True
    if ins["operands"]:
        # (a space after a field, so that an operator such as "<" does not run into the list)
        parts.append((" (" if fielded else "(") + ", ".join(operand_text(a) for a in ins["operands"]) + ")")
    if ins["targets"]:
        parts.append(" -> " + ", ".join(atom(label) for label in ins["targets"]))
    if ins["type"] != "":
        parts.append(" : " + atom(ins["type"]))
    if locations and ins["line"] != 0:
        parts.append(" " + location_text(ins["line"]))
    return "".join(parts)


RESULT = re.compile(r"(~?)%t(-?\d+)|%(.+)\.(-?\d+)")


def read_instruction(text):
    line = 0
    located = LOCATION.search(text)
    if located:
        # (no other part of an instruction ends so: a bare atom holds no parenthesis)
        per = lines_per_file()
        first, second = int(located.group(1)), located.group(2)
        line = first if second is None else first * per + int(second)
        require(line != 0, "an unknown location is omitted")
        require(second is None or int(second) < per, f"a location's line must be below {per}")
        require(text[located.start() + 1:] == location_text(line), f"a location must be written {location_text(line)}")
        text = text[:located.start()]
    at = 0
    results = []
    names = []
    numbered = re.match(r"((?:~?%[^\s=]+ )+)= ", text)
    if numbered:
        names = numbered.group(1).split()
        for name in names:
            found = RESULT.fullmatch(name)
            require(found is not None, f"invalid result {name!r}")
            results.append(int(found.group(2) if found.group(2) is not None else found.group(4)))
        at = numbered.end()
    found = re.compile(r"[a-z]+(\.[a-z]+)?").match(text, at)
    require(found is not None, "expected an operation name")
    op = found.group(0)
    at = found.end()
    given = named_fields(op)
    fields = {"s": "", "k": 0, "x": ""}
    read = []  # (the fields written so far, in order)
    if text.startswith(" ", at) and not text.startswith((" (", " -> ", " : "), at) and not FIELD.match(text, at):
        require(given.get("s") == OPERATOR, f"{op} has no operator to write bare: its row names {row_fields(op)}")
        fields["s"], at = read_text_atom(text, at + 1)
        require(fields["s"] != "", "an empty operator is omitted")
        read.append("s")
    while (named := FIELD.match(text, at)) is not None:
        name = named.group(1)
        field = next((f for f, n in given.items() if n == name), "")
        if field == "":
            # (a field the op's row does not name, by its letter)
            require(name in fields, f"{op} has no field {name}: its row names {row_fields(op)}")
            require(name not in given, f"{op} names its {name} {given.get(name)}: write "
                                       + ("it bare" if given.get(name) == OPERATOR else f"{given.get(name)}="))
            field = name
        require(name != OPERATOR, f"{op} writes its {OPERATOR} bare, before its other fields")
        require(field not in read, f"{op} field {name} is repeated")
        later = [f for f in read if "skx".index(f) > "skx".index(field)]
        require(not later, f"{op} field {name} must come before {given.get(later[0], later[0]) if later else ''}")
        read.append(field)
        at = named.end()
        if field == "k":
            number = re.compile(r"-?\d+").match(text, at)
            require(number is not None and int(number.group(0)) != 0 and str(int(number.group(0))) == number.group(0),
                    f"{name}= needs a nonzero integer")
            fields["k"], at = int(number.group(0)), number.end()
        else:
            fields[field], at = read_atom(text, at)
            require(fields[field] != "", f"an empty {name} is omitted")
    s, k, x = fields["s"], fields["k"], fields["x"]
    t = ""
    operands = []
    fielded = len(read) > 0
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
    ins = {"op": op, "type": t, "text": s, "immediate": k, "descriptor": x,
           "results": results, "operands": operands, "targets": targets, "line": line}
    if names:
        expected = result_names(ins)
        require(names == expected, f"results must be written {' '.join(expected)}")
    return ins


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


def format_function(record, locations=False):
    """The text of one function record, with each instruction's location where locations."""
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
        lines.append("  " + instruction_text(slot, locations))
    for block in record["blocks"]:
        head = atom(block["label"], ":") + ":"
        if block["handler"] != "":
            head += " handler=" + atom(block["handler"])
        lines.append(head)
        lines.extend("  " + instruction_text(i, locations) for i in block["operations"])
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


def declaration_text(keyword, name, record):
    """The line of one declaration of a module (DECLARATIONS), without its indentation."""
    table, named, fields = DECLARATIONS[keyword]
    keys = [named] * (named != "") + [key for key, _, _ in fields]
    require(isinstance(record, dict) and sorted(record) == sorted(keys), f"{keyword} {name}: the record must hold {', '.join(keys)}")
    parts = [keyword, atom(name)]
    for key, kind, default in fields:
        value = record[key]
        require(type(value) is KINDS[kind][0], f"{keyword} {name}: {key} must be {KINDS[kind][1]}")
        if value == default:
            continue
        if kind == "flag":
            parts.append(key)
        elif kind == "list":
            parts.append(f"{key}=[{' '.join(atom(v) for v in value)}]")
        elif kind == "typed":
            require(all(isinstance(v, dict) and sorted(v) == ["name", "type"] for v in value),
                    f"{keyword} {name}: each of its {key} must hold a name and a type")
            parts.append(f"{key}=[{' '.join(atom(v['name'], ':') + ':' + atom(v['type']) for v in value)}]")
        elif kind == "indexed":
            require(all(type(v) is int for v in value.values()), f"{keyword} {name}: {key} must map names to ints")
            parts.append(f"{key}=[{' '.join(atom(k, ':') + ':' + str(v) for k, v in value.items())}]")
        else:
            parts.append(f"{key}={value if kind == 'int' else atom(value)}")
    return " ".join(parts)


def read_declaration(text):
    """(keyword, name, record) of the line of a declaration, without its indentation."""
    found = re.compile(r"(class|dyntype|layout) ").match(text)
    require(found is not None, "expected a declaration: class, dyntype or layout")
    keyword = found.group(1)
    table, named, fields = DECLARATIONS[keyword]
    name, at = read_atom(text, found.end())
    keys = [key for key, _, _ in fields]
    record = {}
    while at < len(text):
        at = expect(text, at, " ")
        word = re.compile(r"[a-z]+").match(text, at)
        require(word is not None, f"expected a {keyword} field at column {at + 1}")
        key = word.group(0)
        require(key in keys, f"unknown {keyword} field {key!r}")
        require(key not in record, f"{keyword} field {key} is repeated")
        later = [k for k in keys[keys.index(key) + 1 :] if k in record]
        require(not later, f"{keyword} field {key} must come before {later[0] if later else ''}")
        _, kind, default = fields[keys.index(key)]
        at = word.end()
        if kind == "flag":
            value = True
        elif kind == "int":
            number = re.compile(r"=(-?\d+)").match(text, at)
            require(number is not None and str(int(number.group(1))) == number.group(1), f"{key}= needs an integer")
            value, at = int(number.group(1)), number.end()
        elif kind in ("list", "typed", "indexed"):
            at = expect(text, at, "=[")
            value = {} if kind == "indexed" else []
            while not text.startswith("]", at):
                require(at < len(text), f"{key}=[ has no closing ']'")
                if value:
                    at = expect(text, at, " ")
                if kind == "list":
                    item, at = read_atom(text, at)
                    value.append(item)
                    continue
                # (NAME:TYPE or NAME:INT, the name quoted where it holds a colon)
                item, at = read_atom(text, at, ":")
                at = expect(text, at, ":")
                if kind == "typed":
                    t, at = read_atom(text, at)
                    value.append({"name": item, "type": t})
                else:
                    number = re.compile(r"-?\d+").match(text, at)
                    require(number is not None and str(int(number.group(0))) == number.group(0),
                            f"{key}=[ needs an integer after {atom(item, ':')}:")
                    require(item not in value, f"{keyword} field {key} names {item!r} twice")
                    value[item], at = int(number.group(0)), number.end()
            at += 1
        else:
            value, at = read_atom(text, expect(text, at, "="))
        require(value != default, f"{keyword} field {key} is omitted where it holds its default")
        record[key] = value
    for key, kind, default in fields:
        require(key in record or default is not None, f"{keyword} {name} needs {key}=")
    record = {key: record[key] if key in record else type(default)(default) if isinstance(default, (list, dict)) else default
              for key, kind, default in fields}
    return keyword, name, dict({named: name}, **record) if named else record


def format_module(module, locations=False):
    """The text of a module record: its declarations, then its functions, with each
    instruction's location where locations."""
    require(isinstance(module, dict) and sorted(module) == sorted(MODULE_KEYS), f"a module record holds {', '.join(MODULE_KEYS)}")
    lines = ["module {"]
    for keyword, (table, named, fields) in DECLARATIONS.items():
        entries = module[table]
        require(isinstance(entries, list if named else dict), f"a module's {table} must be a {'list' if named else 'dict'}")
        for name, record in ([(r.get(named) if isinstance(r, dict) else None, r) for r in entries] if named else entries.items()):
            lines.append("  " + declaration_text(keyword, name, record))
    lines.append("}")
    return "\n".join(["\n".join(lines) + "\n"] + [format_function(r, locations) for r in module["functions"]])


def parse(text):
    """The records of a text: a module record where it starts with a module's declarations, else
    the function records it holds, in order. A full-line `;` comment and a blank line are skipped."""
    module = None
    declaring = False  # between "module {" and its "}"
    names = {keyword: set() for keyword in DECLARATIONS}
    records = []
    record = None
    block = None
    tail = False  # after the first cold or loop line, no block follows
    for number, line in enumerate(text.split("\n"), 1):
        try:
            if line.strip() == "" or line.lstrip().startswith(";"):
                continue
            require(line == line.rstrip(), "trailing whitespace")
            if declaring:
                if line == "}":
                    declaring = False
                    continue
                require(line.startswith("  "), "expected a declaration, indented by two spaces, or the module's '}'")
                keyword, name, declared = read_declaration(line[2:])
                table, named, fields = DECLARATIONS[keyword]
                later = [k for k in list(DECLARATIONS)[list(DECLARATIONS).index(keyword) + 1 :] if names[k]]
                require(not later, f"a {keyword} after the {later[-1] if later else ''}s")
                require(name not in names[keyword], f"{keyword} {name} is declared twice")
                names[keyword].add(name)
                if named:
                    module[table].append(declared)
                else:
                    module[table][name] = declared
            elif record is None and line == "module {":
                require(module is None and not records, "a module's declarations come once, before its functions")
                module = {table: [] if named else {} for table, named, _ in DECLARATIONS.values()}
                module["functions"] = records
                declaring = True
            elif record is None:
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
    require(not declaring, "the module's declarations have no closing brace")
    require(record is None, "the last function has no closing brace")
    return module if module is not None else records


def parse_functions(text):
    """The function records of a text, a module's or functions alone, in order."""
    parsed = parse(text)
    return parsed["functions"] if isinstance(parsed, dict) else parsed


def parse_function(text):
    records = parse_functions(text)
    require(len(records) == 1, f"expected one function, found {len(records)}")
    return records[0]


def parse_module(text):
    parsed = parse(text)
    require(isinstance(parsed, dict), "expected a module, found functions alone")
    return parsed


def format_text(parsed, locations=False):
    """The text of what parse returns: a module record, or function records, with each
    instruction's location where locations."""
    return format_module(parsed, locations) if isinstance(parsed, dict) else "\n".join(format_function(r, locations) for r in parsed)


def from_snapshot(function, files=()):
    """The record of one function of an inspection snapshot (tools/inspect_compiler.py), whose
    instructions' locations name the snapshot's files (its `files`)."""
    def instruction(ins):
        record = {key: ins[key] for key in ("op", "type", "text", "immediate", "descriptor", "results", "targets")}
        record["operands"] = [dict(a) for a in ins["operands"]]
        location = ins.get("location")
        record["line"] = 0
        if location is not None:
            require(location["file"] in files, f"a location in {location['file']}, which the snapshot's files do not list")
            record["line"] = list(files).index(location["file"]) * lines_per_file() + location["line"]
        return record

    return {
        "symbol": function["symbol"],
        "parameters": [{"name": p["name"], "type": p["representation"]} for p in function["parameters"]],
        "return": function["return_representation"],
        "coroutine": function["recursion"]["coroutine"],
        "effects": function["effects"],
        "slots": [instruction(i) for i in function["slots"]],
        "blocks": [{"label": b["label"], "handler": b["handler"],
                    "operations": [instruction(i) for i in b["operations"]]}
                   for b in function["blocks"]],
        "check_targets": dict(function["check_targets"]),
        "loops": [{"kind": lp["kind"], "mode": lp["mode"], "head": lp["head"], "body": lp["body"],
                   "step": lp["step"], "exit": lp["exit"], "tests": list(lp["tests"]),
                   "indices": list(lp["indices"])} for lp in function["loops"]],
    }


def module_from_snapshot(snapshot):
    """The module record of a typed-after inspection snapshot: its tables as they are, and the
    record of each of its functions."""
    return {
        "classes": {name: dict(c, roles=list(c["roles"]), overlaps=list(c["overlaps"]), fields=[dict(f) for f in c["fields"]],
                               flags=dict(c["flags"]), boxes=dict(c["boxes"]))
                    for name, c in snapshot["classes"].items()},
        "dynamic_types": [dict(t) for t in snapshot["dynamic_types"]],
        "dynamic_layouts": [dict(t, members=list(t["members"]), llvm=list(t["llvm"])) for t in snapshot["dynamic_layouts"]],
        "functions": [from_snapshot(f, snapshot.get("files", [])) for f in snapshot["functions"]],
    }


def compiler():
    """The hosted compiler's modules, imported on first use."""
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
        i.line = ins["line"]
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
                "operands": [{"value": a.v, "type": a.t} for a in i.a], "targets": list(i.b), "line": i.line}

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


# what a class's struct holds besides its fields: an "is assigned" flag and an identity box, each
# by its name, its class record's key and its member type
MEMBERS = (("flag", "flags", "bool"), ("box", "boxes", "dyn"))


def class_struct(name, c, info):
    """Give ClassInfo info the struct that class record c declares, as flow.gen_fl_fields lays it
    out (lower_module.struct_types): its fields, then a bool for each of its own flags and then a
    dyn for each of its own identity boxes. A flag or box at a field's index is a base's, which a
    derived class's struct begins with: a bool or a dyn field. Declared data that no ClassInfo
    holds, or that lays out no struct, is a TextError."""
    for field in c["fields"]:
        require(field["name"] not in info.ftypes, f"class {name}: field {field['name']!r} is declared twice")
        info.fpos[field["name"]] = len(info.fields)
        info.fields.append(field["name"])
        info.ftypes[field["name"]] = field["type"]
    first = len(info.fields)
    taken = {}  # (each index a flag or box takes -> which)
    own = {}
    for what, key, member in MEMBERS:
        own[key] = len([k for k in c[key].values() if k >= len(info.fields)])
        span = (f"{first}" if own[key] == 1 else f"{first} to {first + own[key] - 1}") + ", after its fields"
        span += " and own flags" if key == "boxes" else ""
        for field, k in c[key].items():
            require(field in info.ftypes, f"class {name}: {field!r} has a {what}, but is no field of it")
            require(k >= 0, f"class {name}: the {what} of {field!r} is at {k}, which is no index")
            if k < len(info.fields):
                t = info.ftypes[info.fields[k]]
                require(t == member, f"class {name}: the {what} of {field!r} is at {k}, field {info.fields[k]!r} "
                                     f"of type {t}, where a base's {what} is a {member} field")
            else:
                require(first <= k < first + own[key], f"class {name}: the {what} of {field!r} is at {k}, where its own {key} are at {span}")
            require(k not in taken, f"class {name}: the {taken.get(k)} and the {what} of {field!r} are both at {k}")
            taken[k] = f"{what} of {field!r}"
        first += own[key]
    info.fflag = dict(c["flags"])
    info.fbox = dict(c["boxes"])
    info.nflag = own["flags"]
    info.nbox = own["boxes"]


def class_infos(module):
    """The compiler's ClassInfo of each class a module declares, with what the verifier reads of
    it: its base, secondary bases and overlaps, which the class view relates (ircheck.related,
    Gen.derives), and its struct, which field.addr indexes (class_struct)."""
    ir, specs, symbols, syntax, utils = compiler()
    declared = module["classes"]
    infos = {}
    for name, c in declared.items():
        require(c["base"] == "" or c["base"] in declared or c["base"] in specs.EXCBASES,
                f"class {name}: its base {c['base']} is neither a declared class nor a builtin exception class")
        for other in c["roles"] + c["overlaps"]:
            require(other in declared, f"class {name}: {other} is no declared class")
        chain = [name]
        while chain[-1] in declared and declared[chain[-1]]["base"] != "":
            require(declared[chain[-1]]["base"] not in chain, f"class {name} derives from itself")
            chain.append(declared[chain[-1]]["base"])
        info = symbols.ClassInfo(name, syntax.Node("class", name, 1))
        info.base = c["base"]
        info.roles = list(c["roles"])
        info.overlaps = list(c["overlaps"])
        class_struct(name, c, info)
        infos[name] = info
    return infos


def gen_for(fn, classes=None):
    """A fresh code generator that has declared the runtime functions fn calls and knows the
    classes of its module (class_infos), if any."""
    ir, specs, symbols, syntax, utils = compiler()
    from src.pystachy_compiler.gen import Gen
    g = Gen()
    g.classes.update(classes or {})
    for block in fn.blocks:
        for i in block.code:
            if i.op == "rt":
                require(i.s in specs.RUNTIME, f"no RUNTIME entry for {i.s}")
                g.runtime(specs.RUNTIME[i.s].split("|")[2] or "pys_" + i.s.replace(".", "_"))
    return g


EXPECTED = re.compile(r"; expected-error \{\{(.+?)\}\}")
REPORTED = re.compile(r"bad IR in (\S+), block (.*?): (.*)")


def expectations(text):
    """Each function's expected errors, in the order of the functions: {"message", "block",
    "line"}, where block is the label of the block the annotation is in (None before the first)."""
    found = []
    expected = None
    block = None
    for number, line in enumerate(text.split("\n"), 1):
        mark = EXPECTED.fullmatch(line.strip())
        if expected is None:
            require(mark is None, f"line {number}: an expected error outside a function")
            if line.startswith("function "):
                expected, block = [], None
        elif line == "}":
            found.append(expected)
            expected = None
        elif mark is not None:
            expected.append({"message": mark.group(1), "block": block, "line": number})
        elif line != "" and not line.startswith(("  ", ";", "cold ", "loop")):
            block = read_atom(line, 0, ":")[0]
    return found


def verify_errors(text, eh=False):
    """Why the functions of a text do not verify as their expected errors say, or []. A module's
    are verified with its classes."""
    parsed = parse(text)
    records = parsed["functions"] if isinstance(parsed, dict) else parsed
    classes = class_infos(parsed) if isinstance(parsed, dict) else {}
    problems = []
    for record, expected in zip(records, expectations(text), strict=True):
        name = record["symbol"]
        if len(expected) > 1:
            problems.append(f"{name}: expects {len(expected)} errors, where the verifier reports its first alone")
            continue
        fn = to_ifn(record)
        errors = StringIO()
        try:
            with redirect_stderr(errors):
                gen_for(fn, classes).verify(fn, eh)
            reported = None
        except SystemExit:
            reported = REPORTED.search(errors.getvalue())
            if reported is None:
                problems.append(f"{name}: the verifier failed without a bad IR report: {errors.getvalue().strip()}")
                continue
        if not expected:
            if reported is not None:
                problems.append(f"{name}: unexpected error in block {reported.group(2)}: {reported.group(3)}")
            continue
        want = expected[0]
        block = want["block"] if want["block"] is not None else record["blocks"][0]["label"]
        if reported is None:
            problems.append(f"{name}: line {want['line']}: expected error {{{{{want['message']}}}}} was not reported")
        elif want["message"] not in reported.group(3) or reported.group(2) != block:
            problems.append(f"{name}: line {want['line']}: expected error {{{{{want['message']}}}}} in block {block}, "
                            f"got in block {reported.group(2)}: {reported.group(3)}")
    return problems


def roundtrip_errors(record):
    """Why a record, its locations too, does not survive print and parse, or []."""
    try:
        text = format_function(record, True)
        parsed = parse_function(text)
    except TextError as error:
        return [f"{record.get('symbol', '?')}: {error}"]
    if parsed != record:
        return [f"{record['symbol']}: the parsed record differs from the printed one"]
    if format_function(parsed, True) != text:
        return [f"{record['symbol']}: printing the parsed record gives another text"]
    return []


def module_roundtrip_errors(module):
    """Why a module record, its locations too, does not survive print and parse, or []."""
    problems = [e for record in module["functions"] for e in roundtrip_errors(record)]
    if problems:
        return problems
    try:
        text = format_module(module, True)
        parsed = parse_module(text)
    except TextError as error:
        return [f"module: {error}"]
    if parsed != module:
        return ["module: the parsed record differs from the printed one"]
    if format_module(parsed, True) != text:
        return ["module: printing the parsed record gives another text"]
    return []


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("mode", choices=("print", "check", "json", "verify"))
    parser.add_argument("path", type=Path)
    parser.add_argument("--function", default="", help="print: only functions whose symbol contains this, without the module")
    parser.add_argument("--locations", action="store_true", help="print: each instruction's source location")
    args = parser.parse_args()
    try:
        source = args.path.read_text(encoding="utf-8")
        if args.mode == "print":
            snapshot = json.loads(source)
            if args.function == "" and all(table in snapshot for table in MODULE_KEYS):
                parsed = module_from_snapshot(snapshot)
                problems = module_roundtrip_errors(parsed)
            else:
                parsed = [from_snapshot(f, snapshot.get("files", [])) for f in snapshot["functions"] if args.function in f["symbol"]]
                problems = [e for r in parsed for e in roundtrip_errors(r)]
            if problems:
                print("\n".join(problems), file=sys.stderr)
                return 1
            sys.stdout.write(format_text(parsed, args.locations))
            return 0
        parsed = parse(source)
        records = parsed["functions"] if isinstance(parsed, dict) else parsed
        if args.mode == "verify":
            problems = verify_errors(source)
            if problems:
                print("\n".join(problems), file=sys.stderr)
                return 1
            print(f"typed_ir_text: {len(records)} functions verify as expected")
            return 0
        if args.mode == "json":
            print(json.dumps(parsed, indent=1))
            return 0
        if format_text(parsed, True) != source:
            print(f"typed_ir_text: {args.path} is not in the printed form", file=sys.stderr)
            return 1
        if isinstance(parsed, dict):
            declared = sum(len(parsed[table]) for table, _, _ in DECLARATIONS.values())
            print(f"typed_ir_text: a module of {declared} declarations and {len(records)} functions parses and prints unchanged")
        else:
            print(f"typed_ir_text: {len(records)} functions parse and print unchanged")
        return 0
    except (OSError, KeyError, TypeError, ValueError) as error:
        print(f"typed_ir_text: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
