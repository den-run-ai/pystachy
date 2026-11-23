#!/usr/bin/env python3
"""A text form of typed-IR modules and functions, with its printer and parser.

A function record holds what the inspection snapshots hold of one function's IR: its symbol,
parameters, return type, attributes, slots, blocks, check targets and loops. A module record
holds what a typed-after snapshot holds: its attributes, the program's classes, the DynTypes it
emits and their classes' layouts, the other declarations of what LLVM lowering reads, and its
function records. `format_module` and `format_function` print a record, `parse`
reads a text back, and they are inverse: parse(format(r)) == r for every record, and
format(parse(t)) == t for every text that format printed, where format prints locations
(locations=True); without them, both hold where no instruction has a location. `to_ifn` builds
the compiler's own IFn from a function record, so a test can write IR as text, run the verifier
or a pass on it and compare the printed result; `from_ifn` is its inverse.

    python3 tools/typed_ir_text.py print typed-after.json [--function NAME] [--locations]
    python3 tools/typed_ir_text.py check FILE.tir          # parse, print again, compare
    python3 tools/typed_ir_text.py json FILE.tir           # the records, as JSON
    python3 tools/typed_ir_text.py verify FILE.tir         # verify each function, as expected
    python3 tools/typed_ir_text.py compile FILE.tir [-o OUT.ll]  # lower a module to LLVM
    python3 tools/typed_ir_text.py roundtrip PROGRAM.py ... [--jobs N] [--records FILE]

`print` writes a typed-after snapshot as a module, and the functions alone where --function
selects some or the snapshot holds no module data (typed-before.json). The other modes read a
module or functions alone. A module gives its attributes on its `module` line, as declarations
give their fields, the first its text's version (TEXT_VERSION), its declarations, one a line,
before its `}`, and then its functions:

    module version=2 complete opts=[fieldtbaa tupleret] exceptions {
      class Both base=Storage roles=[Reader] tag=1 fields=[" class":int value:int " Storage.0":bool " Storage.box.0":dyn] flags=[value:2] boxes=[value:3]
      class Reader overlaps=[Storage] tag=2 fields=[" class":int]
      dyntype @dt.Both kind=obj cls=1 flags=[role] base=@dt.Storage role=@dt.Reader payload=Both
      layout Both descriptor=@dt.Both base=@dt.Storage role=@dt.Reader number=1 members=[int int bool dyn]
    }

    class NAME [base=CLASS] [roles=[CLASS ...]] [overlaps=[CLASS ...]] [tag=INT] [fields=[FIELD:TYPE ...]] [flags=[FIELD:INT ...]] [boxes=[FIELD:INT ...]]
    dyntype SYMBOL kind=KIND cls=INT [flags=[FLAG ...]] [base=SYMBOL] [role=SYMBOL] [payload=TYPE]
    layout NAME descriptor=SYMBOL [base=SYMBOL] [role=SYMBOL] number=INT [members=[TYPE ...]]

A class gives its single base (a class or a builtin exception class), its fieldless secondary
bases, the unrelated classes it shares a subclass with, its tag (the number that its objects'
class word holds, ClassInfo.tag; 0, omitted, where its objects have none), and its struct as
field.addr indexes it: its fields in order with their types (a hidden
field's name begins with a space, so it is quoted), and the index of each field's "is
assigned" flag and identity box (ClassInfo.fflag and fbox). Its own flags take the indexes
after its fields and its own boxes those after its flags; a base's are among its fields
(" Storage.0" and " Storage.box.0"), as a derived class's struct begins with its base's
(flow.gen_fl_fields). A dyntype gives a DynType's kind and flags by runtime.c's names for them
(DYN_KINDS, DYN_FLAGS), its class number, its base and role DynTypes and its boxes' payload
type (dynamic.py); a layout, the struct of a class that has a DynType, by its members' types,
from which a record's LLVM types of them (llvm) are derived (inspect_compiler.py's classes,
dynamic_types and dynamic_layouts). Classes come first, then dyntypes, then layouts; a field
that holds its default ("", [], {}, 0 or false) is omitted.

The other declarations, and the module's and each function's attributes (MODULE_ATTRIBUTES,
FUNCTION_ATTRIBUTES), hold the rest of what LLVM lowering reads (Gen.lower_program, its
gen_lower and gen_lower_module): a typed-after snapshot's lowering record, which
lowering_state takes from the code generator once finalize_program has run (docs/typed-ir.md
lists them by what lowering reads). A class also says whether it is a class template, the
builtin exception class it derives from and its module; then come the holes' types (by number,
from 1), globals, GC roots, module data (ir.Data), runtime functions and data, extern plans
(lower_module.ExternDecl), the key kinds of holes' dicts and sets, in the compiler's order, and,
where the module has LLVM line tables (debuglines), the program's files (diagnostics.FILES, by
number from 0), which its instructions' locations and its functions' `line` attributes name:

    hole N [type=TYPE]
    global SYMBOL type=TYPE
    root VALUE
    const NAME kind=KIND [text=TEXT] [refs=[NAME ...]] [items=(TYPE VALUE, ...)]
    runtime KEY
    rtdata SYMBOL
    extern KEY symbol=SYMBOL [params=[TYPE ...]] result=TYPE [provided] [c] [csym=SYMBOL] ...
    keykind TYPE [kind=KIND] [built=KIND]
    file N path=PATH

A module with line tables also gives the directory its files' nodes name (`directory`, the
compiler's working directory), and the text prints each instruction's location.

`compile` builds a code generator that holds a module's state (gen_for_module) and runs the
compiler's own lowering on it (compile_module): a module printed from a typed-after snapshot
compiles to the LLVM module that the compiler emitted, byte for byte. It refuses (refusals) a
module that does not declare lowering's state (complete), one whose printer named what it could
not hold (unsupported), an extension module's entry points and runtime.py's module.
`roundtrip` inspects programs (tools/inspect_compiler.py), prints each one's module,
compiles it and compares the LLVM with what the compiler emitted.

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
else as a JSON string. Every block has a label, the first block's being entry. The form is for
tests, review and the WebAssembly emitter (wasm/tir_wasm.py), which compiles a module from it.
Its declarations follow the compiler's tables, so a text is read by the same compiler's tools;
its version says which form a text is in.

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
import copy
from io import StringIO
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent

# The version of the text form, a module's first attribute (version=2): what a module text means
# changes only with it, so that a reader of module texts other than this one (the WebAssembly
# emitter, wasm/tir_wasm.py) can tell a text it was not written for. parse refuses another
# version; test_typed_ir_text.py's golden module holds the form, and changing that changes this.
TEXT_VERSION = 2
# runtime.c's DynType kinds (its DK_* enum, in order: a kind is its index) and flags (DF_*), by
# the names a dyntype declaration writes them with (kind=obj, flags=[eq hash])
DYN_KINDS = ("none", "bool", "int", "float", "str", "list", "dict", "tuple", "obj", "func", "iter", "gen", "type")
DYN_FLAGS = (("eq", 1), ("cmp", 2), ("hash", 4), ("boxid", 8), ("ne", 16), ("x", 32), ("iter", 64), ("big", 128), ("role", 256))
LOOP_ATOMS = ("kind", "mode", "head", "body", "step", "exit", "counter")
LOOP_LISTS = ("tests", "indices")
# A module's declarations, by keyword, in the order a module gives them: the module record's
# table that holds them, the key of a declaration's name in its record ("" where the table maps
# names to records), and its fields in the order they are written: (key, kind, default). A field
# that holds its default is omitted (None: none, it is always written). Kinds: an atom, an int, a
# list of atoms, a list of ints, a flag, written as its bare key where it is true, a list of typed
# names (each {"name", "type"}, written NAME:TYPE), a dict of names to ints (NAME:INT), a list
# of typed values (each {"value", "type"}, written as an op's operands are: (TYPE VALUE, ...)), a
# DynType's kind (an int, written by its name in DYN_KINDS) or flags (an int, written as the list
# of its flags' names in DYN_FLAGS), or a list derived from the other fields (DERIVED), which is
# never written: parsing derives it, and printing refuses a record that holds another.
# The first three are what the verifier reads of the program's classes; the others are what
# lowering reads (gen_lower_module, gen_lower): lowering_state, docs/typed-ir.md#lowering-state.
DECLARATIONS = {
    "class": ("classes", "", (("base", "atom", ""), ("roles", "list", []), ("overlaps", "list", []),
                              ("tag", "int", 0), ("fields", "typed", []), ("flags", "indexed", {}),
                              ("boxes", "indexed", {}), ("template", "flag", False), ("exception", "atom", ""),
                              ("module", "atom", ""))),
    "dyntype": ("dynamic_types", "symbol", (("kind", "dynkind", None), ("cls", "int", None), ("flags", "dynflags", 0),
                                           ("base", "atom", ""), ("role", "atom", ""), ("payload", "atom", ""))),
    "layout": ("dynamic_layouts", "name", (("descriptor", "atom", None), ("base", "atom", ""), ("role", "atom", ""),
                                          ("number", "int", None), ("members", "list", []), ("llvm", "derived", None))),
    "hole": ("holes", "number", (("type", "atom", ""),)),
    "global": ("globals", "symbol", (("type", "atom", None),)),
    "root": ("roots", "value", ()),
    "const": ("constants", "name", (("kind", "atom", None), ("text", "atom", ""), ("refs", "list", []),
                                    ("items", "values", []))),
    "runtime": ("runtime", "key", ()),
    "rtdata": ("runtime_data", "symbol", ()),
    "extern": ("externs", "key", (("symbol", "atom", None), ("params", "list", []), ("result", "atom", None),
                                  ("provided", "flag", False), ("c", "flag", False), ("csym", "atom", ""),
                                  ("library", "atom", ""), ("ctypes", "list", []), ("cret", "atom", ""),
                                  ("at", "flag", False), ("direct", "flag", False), ("declare", "flag", False),
                                  ("dynamic", "flag", False), ("narrow", "flag", False))),
    "keykind": ("key_kinds", "type", (("kind", "atom", ""), ("built", "atom", ""))),
    "file": ("source_files", "number", (("path", "atom", None),)),
}
# The tables a typed-after snapshot holds for the verifier (inspect_compiler.py): a snapshot with
# them is printed as a module, whose other tables come from its "lowering" record, if any
SNAPSHOT_TABLES = ("classes", "dynamic_types", "dynamic_layouts")
# A module's attributes, written on its "module" line before its "{" as a declaration's fields
# are (MLIR's module attributes): the program's settings and whole-program tables that lowering
# reads. complete: the module declares all of lowering's state (it was printed at the lowering
# boundary), which compile requires; unsupported: what the printer found it cannot serialize yet
MODULE_ATTRIBUTES = (("version", "int", None), ("complete", "flag", False), ("opts", "list", []), ("exceptions", "flag", False),
                     ("protocol", "flag", False), ("dynamic", "flag", False), ("promoting", "flag", False),
                     ("extension", "atom", ""), ("rtmode", "flag", False), ("debuglines", "flag", False), ("directory", "atom", ""),
                     ("plain", "list", []), ("untracked", "list", []), ("objects", "indexed", {}),
                     ("compared", "list", []), ("hashed", "list", []), ("unequal", "list", []),
                     ("crossed", "list", []), ("unsupported", "list", []))
# A function's attributes, written in its header after its effects: what lowering reads of its
# FnInfo and IFn beyond its signature and body, and the whole-program tables' entries for it
FUNCTION_ATTRIBUTES = (("name", "atom", ""), ("class", "atom", ""), ("decorator", "atom", ""),
                       ("nullable", "flag", False), ("module", "atom", ""), ("home", "atom", "-"),
                       ("kind", "atom", "def"), ("export", "flag", False), ("pyexport", "flag", False),
                       ("extern", "flag", False), ("gret", "atom", ""), ("rdepth", "atom", ""),
                       ("casts", "ints", []), ("closed", "flag", False), ("tupleret", "int", 0),
                       ("tupleconst", "flag", False), ("tuplecalls", "list", []), ("line", "int", 0))
MODULE_KEYS = ["attributes"] + [table for table, _, _ in DECLARATIONS.values()] + ["functions"]
# the tables of a module's declarations that a typed-after snapshot's lowering record holds
LOWERING_TABLES = tuple(table for table, _, _ in DECLARATIONS.values() if table not in SNAPSHOT_TABLES)
# each kind's Python type in a record, and what a message calls a value of it
KINDS = {"atom": (str, "an atom"), "int": (int, "an int"), "list": (list, "a list"), "flag": (bool, "a flag"),
         "ints": (list, "a list of ints"), "typed": (list, "a list of names with types"),
         "indexed": (dict, "a dict of names to ints"), "values": (list, "a list of typed values"),
         "dynkind": (int, "an int"), "dynflags": (int, "an int"), "derived": (list, "a list")}


def layout_llvm(record):
    """A layout's members' LLVM types, lower_module.struct_types: what its llvm holds."""
    utils = compiler()[4]
    return [utils.lt(t) for t in record["members"]]


# The derived fields (kind "derived"), by key: what derives each from its record, and what that is
DERIVED = {"llvm": (layout_llvm, "its members' LLVM types")}
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
    attributes = record["attributes"]
    require(isinstance(attributes, dict) and sorted(attributes) == sorted(key for key, _, _ in FUNCTION_ATTRIBUTES),
            f"{record['symbol']}: its attributes must hold {', '.join(key for key, _, _ in FUNCTION_ATTRIBUTES)}")
    header += fields_text(attributes, FUNCTION_ATTRIBUTES, "function " + record["symbol"])
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
    require(text.endswith(" {") and at <= len(text) - 2, f"expected ' {{' at column {at + 1}")
    attributes = read_fields(text, at, len(text) - 2, FUNCTION_ATTRIBUTES, "function")
    return {"symbol": symbol, "parameters": parameters, "return": ret, "coroutine": coroutine,
            "effects": effects, "attributes": attributes, "slots": [], "blocks": [], "check_targets": {}, "loops": []}


def fields_text(record, fields, what):
    """The written fields of a record (FIELDS: (key, kind, default), in order), each " KEY=VALUE"
    or a flag's " KEY", but those that hold their default; what names the record in a message."""
    parts = []
    for key, kind, default in fields:
        value = record[key]
        require(type(value) is KINDS[kind][0], f"{what}: {key} must be {KINDS[kind][1]}")
        if kind == "derived":
            derive, derived = DERIVED[key]
            require(value == derive(record), f"{what}: {key} must hold {derived}")
            continue
        if value == default:
            continue
        if kind == "flag":
            parts.append(key)
        elif kind == "dynkind":
            require(0 <= value < len(DYN_KINDS), f"{what}: {key} {value} is no DynType kind")
            parts.append(f"{key}={DYN_KINDS[value]}")
        elif kind == "dynflags":
            names = [name for name, bit in DYN_FLAGS if value & bit != 0]
            require(sum(bit for _, bit in DYN_FLAGS if value & bit != 0) == value, f"{what}: {key} {value} holds no DynType flag")
            parts.append(f"{key}=[{' '.join(names)}]")
        elif kind == "list":
            parts.append(f"{key}=[{' '.join(atom(v) for v in value)}]")
        elif kind == "ints":
            require(all(type(v) is int for v in value), f"{what}: {key} must hold ints")
            parts.append(f"{key}=[{' '.join(str(v) for v in value)}]")
        elif kind == "typed":
            require(all(isinstance(v, dict) and sorted(v) == ["name", "type"] for v in value),
                    f"{what}: each of its {key} must hold a name and a type")
            parts.append(f"{key}=[{' '.join(atom(v['name'], ':') + ':' + atom(v['type']) for v in value)}]")
        elif kind == "indexed":
            require(all(type(v) is int for v in value.values()), f"{what}: {key} must map names to ints")
            parts.append(f"{key}=[{' '.join(atom(k, ':') + ':' + str(v) for k, v in value.items())}]")
        elif kind == "values":
            require(all(isinstance(v, dict) and sorted(v) == ["type", "value"] for v in value),
                    f"{what}: each of its {key} must hold a value and a type")
            parts.append(f"{key}=(" + ", ".join(operand_text(v) for v in value) + ")")
        else:
            parts.append(f"{key}={value if kind == 'int' else atom(value)}")
    return "".join(" " + part for part in parts)


def read_fields(text, at, end, fields, what):
    """The record of the fields (FIELDS) written in text[at:end], each after a space, with each
    field that is not written at its default; what names the record in a message."""
    keys = [key for key, _, _ in fields]
    record = {}
    while at < end:
        at = expect(text, at, " ")
        word = re.compile(r"[a-z]+").match(text, at)
        require(word is not None, f"expected a {what} field at column {at + 1}")
        key = word.group(0)
        require(key in keys, f"unknown {what} field {key!r}")
        require(key not in record, f"{what} field {key} is repeated")
        later = [k for k in keys[keys.index(key) + 1 :] if k in record]
        require(not later, f"{what} field {key} must come before {later[0] if later else ''}")
        _, kind, default = fields[keys.index(key)]
        require(kind != "derived", f"{what} field {key} is derived from the others, not written")
        at = word.end()
        if kind == "flag":
            require(at == end or text.startswith(" ", at), f"{what} field {key} is a flag, written bare")
            value = True
        elif kind == "int":
            number = re.compile(r"=(-?\d+)").match(text, at)
            require(number is not None and str(int(number.group(1))) == number.group(1), f"{key}= needs an integer")
            value, at = int(number.group(1)), number.end()
        elif kind == "values":
            value, at = read_operands(text, expect(text, at, "="))
        elif kind == "dynkind":
            name, at = read_atom(text, expect(text, at, "="))
            require(name in DYN_KINDS, f"{key}= needs a DynType kind: {', '.join(DYN_KINDS)}")
            value = DYN_KINDS.index(name)
        elif kind in ("list", "ints", "typed", "indexed", "dynflags"):
            at = expect(text, at, "=[")
            value = {} if kind == "indexed" else []
            while not text.startswith("]", at):
                require(at < end, f"{key}=[ has no closing ']'")
                if value:
                    at = expect(text, at, " ")
                if kind == "list" or kind == "dynflags":
                    item, at = read_atom(text, at)
                    value.append(item)
                    continue
                if kind == "ints":
                    number = re.compile(r"-?\d+").match(text, at)
                    require(number is not None and str(int(number.group(0))) == number.group(0), f"{key}=[ needs integers")
                    value.append(int(number.group(0)))
                    at = number.end()
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
                    require(item not in value, f"{what} field {key} names {item!r} twice")
                    value[item], at = int(number.group(0)), number.end()
            at += 1
            if kind == "dynflags":
                bits = dict(DYN_FLAGS)
                require(all(name in bits for name in value), f"{key}=[ needs DynType flags: {', '.join(bits)}")
                require(len(set(value)) == len(value) and value == [name for name, _ in DYN_FLAGS if name in value],
                        f"{key}=[ names each flag once, in the order {' '.join(bits)}")
                value = sum(bits[name] for name in value)
        else:
            value, at = read_atom(text, expect(text, at, "="))
        require(at <= end, f"unexpected text at column {end + 1}")
        require(value != default, f"{what} field {key} is omitted where it holds its default")
        record[key] = value
    for key, kind, default in fields:
        require(key in record or default is not None or kind == "derived", f"{what} needs {key}=")
    out = {key: record[key] if key in record else type(default)(default) if isinstance(default, (list, dict)) else default
           for key, kind, default in fields}
    for key, kind, default in fields:
        if kind == "derived":
            out[key] = DERIVED[key][0](out)
    return out


def declaration_text(keyword, name, record):
    """The line of one declaration of a module (DECLARATIONS), without its indentation."""
    table, named, fields = DECLARATIONS[keyword]
    keys = [named] * (named != "") + [key for key, _, _ in fields]
    require(isinstance(record, dict) and sorted(record) == sorted(keys), f"{keyword} {name}: the record must hold {', '.join(keys)}")
    return keyword + " " + atom(name) + fields_text(record, fields, f"{keyword} {name}")


DECLARATION = re.compile("(" + "|".join(DECLARATIONS) + ") ")


def read_declaration(text):
    """(keyword, name, record) of the line of a declaration, without its indentation."""
    found = DECLARATION.match(text)
    require(found is not None, f"expected a declaration: {', '.join(DECLARATIONS)}")
    keyword = found.group(1)
    table, named, fields = DECLARATIONS[keyword]
    name, at = read_atom(text, found.end())
    try:
        record = read_fields(text, at, len(text), fields, keyword)
    except TextError as error:
        # (a missing field names its declaration)
        raise TextError(str(error).replace(f"{keyword} needs ", f"{keyword} {name} needs ")) from None
    return keyword, name, dict({named: name}, **record) if named else record


def format_module(module, locations=False):
    """The text of a module record: its declarations, then its functions, with each instruction's
    location where locations or the module has line tables (debuglines), which read them."""
    require(isinstance(module, dict) and sorted(module) == sorted(MODULE_KEYS), f"a module record holds {', '.join(MODULE_KEYS)}")
    attributes = module["attributes"]
    require(isinstance(attributes, dict) and sorted(attributes) == sorted(key for key, _, _ in MODULE_ATTRIBUTES),
            f"a module's attributes hold {', '.join(key for key, _, _ in MODULE_ATTRIBUTES)}")
    lines = ["module" + fields_text(attributes, MODULE_ATTRIBUTES, "module") + " {"]
    for keyword, (table, named, fields) in DECLARATIONS.items():
        entries = module[table]
        require(isinstance(entries, list if named else dict), f"a module's {table} must be a {'list' if named else 'dict'}")
        for name, record in ([(r.get(named) if isinstance(r, dict) else None, r) for r in entries] if named else entries.items()):
            lines.append("  " + declaration_text(keyword, name, record))
    lines.append("}")
    located = locations or attributes["debuglines"]
    return "\n".join(["\n".join(lines) + "\n"] + [format_function(r, located) for r in module["functions"]])


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
            elif record is None and line.startswith("module") and line.endswith(" {") and re.match(r"module[ {]", line):
                require(module is None and not records, "a module's declarations come once, before its functions")
                module = {"attributes": read_fields(line, len("module"), len(line) - 2, MODULE_ATTRIBUTES, "module")}
                version = module["attributes"]["version"]
                require(version == TEXT_VERSION, f"a module text of version {version}, where this one reads version {TEXT_VERSION}")
                module.update({table: [] if named else {} for table, named, _ in DECLARATIONS.values()})
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
    """The text of what parse returns: a module record, or function records; with each
    instruction's location where locations."""
    if isinstance(parsed, dict):
        return format_module(parsed, locations)
    return "\n".join(format_function(r, locations) for r in parsed)


def default_attributes():
    """A function's attributes (FUNCTION_ATTRIBUTES), each at its default."""
    return {key: type(default)(default) if isinstance(default, list) else default for key, _, default in FUNCTION_ATTRIBUTES}


def from_snapshot(function, files=(), attributes=None):
    """The record of one function of an inspection snapshot (tools/inspect_compiler.py), whose
    instructions' locations name the snapshot's files (its `files`), with its attributes (a
    typed-after snapshot's lowering record has them: lowering_state), else their defaults."""
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
        "attributes": dict(default_attributes(), **(attributes or {})),
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
    record of each of its functions. A snapshot with a lowering record (lowering_state) gives the
    module's attributes, its classes' order and lowering's attributes of each, the other tables
    and its functions' attributes; one without it, a module of the verifier's tables alone."""
    lowering = snapshot.get("lowering")
    classes = snapshot["classes"]
    order = list(classes)
    extra = {}
    if lowering is not None:
        require(sorted(lowering["class_order"]) == sorted(classes), "the lowering record orders other classes than the snapshot's")
        order = lowering["class_order"]
        extra = lowering["classes"]
    # (a class's tag is the number its objects' class word holds, which the lowering record gives;
    # a snapshot without one says only whether a class has a tag, and the compiler numbers those
    # that do from 1 in its order, where it excluded none of them from a hierarchy: program.py)
    numbered = {}
    for name in order:
        if classes[name]["tagged"]:
            numbered[name] = len(numbered) + 1
    records = {}
    for name in order:
        c = classes[name]
        record = {key: c[key] for key in c if key != "tagged"}
        record.update(roles=list(c["roles"]), overlaps=list(c["overlaps"]), fields=[dict(f) for f in c["fields"]],
                      flags=dict(c["flags"]), boxes=dict(c["boxes"]))
        record.update(extra.get(name, {"template": False, "exception": "", "module": "", "tag": numbered.get(name, 0)}))
        require((record["tag"] != 0) == c["tagged"], f"class {name}: the lowering record's tag {record['tag']} and the snapshot disagree")
        records[name] = record
    module = {
        "attributes": {key: type(default)(default) if isinstance(default, (list, dict)) else default for key, _, default in MODULE_ATTRIBUTES},
        "classes": records,
        "dynamic_types": [dict(t) for t in snapshot["dynamic_types"]],
        "dynamic_layouts": [dict(t, members=list(t["members"]), llvm=list(t["llvm"])) for t in snapshot["dynamic_layouts"]],
    }
    module["attributes"]["version"] = TEXT_VERSION
    for table in LOWERING_TABLES:
        module[table] = copy.deepcopy(lowering[table]) if lowering is not None else []
    files = snapshot.get("files", [])
    attributes = lowering["functions"] if lowering is not None else {}
    module["functions"] = [from_snapshot(f, files, attributes.get(f["symbol"])) for f in snapshot["functions"]]
    if lowering is not None:
        module["attributes"].update(copy.deepcopy(lowering["attributes"]))
        if [f["symbol"] for f in snapshot["functions"]] != lowering["function_order"]:
            # (a snapshot of some functions, --function: their module does not compile)
            module["attributes"]["unsupported"].append(f"the snapshot holds {len(snapshot['functions'])} of the program's "
                                                       f"{len(lowering['function_order'])} functions")
    return module


def compiler():
    """The hosted compiler's modules, imported on first use."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from src.pystachy_compiler import ir, specs, symbols, syntax, utils
    return ir, specs, symbols, syntax, utils


def numbers(record):
    """Every value and label number a record names, its casts' too: IFn.n bounds them."""
    found = [0] + list(record["attributes"]["casts"])
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
    """The compiler's IFn of a record: what the verifier, the passes and lowering take. Its FnInfo
    holds the record's attributes; the whole-program tables' (closed, tupleret, tupleconst,
    tuplecalls) are a module's to give the generator (gen_for_module)."""
    ir, specs, symbols, syntax, utils = compiler()
    a = record["attributes"]
    f = symbols.FnInfo(a["name"], record["symbol"], syntax.Node(a["kind"], a["name"], a["line"] if a["line"] != 0 else 1), a["class"])
    f.params = [p["name"] for p in record["parameters"]]
    f.ptypes = [p["type"] for p in record["parameters"]]
    f.ret = record["return"]
    f.deco = a["decorator"]
    f.nullable_self = a["nullable"]
    f.mod = a["module"]
    f.home = a["home"]
    f.export = a["export"]
    f.pyexport = a["pyexport"]
    f.extern = a["extern"]
    f.gret = a["gret"]
    fn = ir.IFn(f)
    # (the parameters it is passed: those not typed None, as Gen.enter numbers them; lowering_state
    # refuses a function whose IFn.ps differs)
    fn.ps = [j for j, t in enumerate(f.ptypes) if t != "None"]
    fn.coro = record["coroutine"]
    fn.rdepth = a["rdepth"]
    fn.casts = list(a["casts"])
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


def function_attributes(fn, gen=None):
    """A compiler IFn's attributes (FUNCTION_ATTRIBUTES): what lowering reads of its FnInfo and of
    it, and, given its generator, the whole-program tables' entries for it (Gen.rdpass, vrets,
    vconst, vcalls), else their defaults."""
    f = fn.f
    attributes = default_attributes()
    attributes.update({"name": f.name, "class": f.cls, "decorator": f.deco, "nullable": f.nullable_self, "module": f.mod,
                       "home": f.home, "kind": f.node.kind, "export": f.export, "pyexport": f.pyexport, "extern": f.extern,
                       "gret": f.gret, "rdepth": fn.rdepth, "casts": list(fn.casts)})
    if gen is not None:
        prefix = f.ll + " "
        attributes.update({"closed": f.ll in gen.rdpass, "tupleret": gen.vrets.get(f.ll, 0), "tupleconst": f.ll in gen.vconst,
                           "tuplecalls": [key[len(prefix):] for key in gen.vcalls if key.startswith(prefix)]})
        if gen.source_lines.enabled:
            attributes["line"] = f.node.line  # (its definition's, which its line table's scope names)
    return attributes


def from_ifn(fn, gen=None):
    """The record of a compiler IFn, with each loop's full shape, and its attributes
    (function_attributes: the whole-program tables' where gen, its generator, is given)."""
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
        "attributes": function_attributes(fn, gen),
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
        info.tag = c["tag"]
        info.exc = c["exception"]
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


def lowering_state(gen):
    """What lowering reads of a code generator at the lowering boundary, once finalize_program has
    run (LOWERING in docs/typed-ir.md), as a typed-after snapshot's "lowering" record: the module's
    attributes, the order of its classes and lowering's attributes of each, the tables of the
    other declarations (LOWERING_TABLES) and each function's attributes. What the record cannot
    hold yet is named in the attributes' unsupported, which compile refuses."""
    ir, specs, symbols, syntax, utils = compiler()
    from src.pystachy_compiler import diagnostics
    unsupported = []
    for fn in gen.fns:
        # (state that to_ifn derives from the record: refuse what it would derive otherwise)
        if fn.ps != [j for j, t in enumerate(fn.f.ptypes) if t != "None"]:
            unsupported.append(f"function {fn.f.ll}: the parameters it is passed are not those not typed None")
        if fn.pads != any(i.op == "landing" for b in fn.blocks for i in b.code):
            unsupported.append(f"function {fn.f.ll}: whether it has landing pads is not whether it has landing ops")
    tuples = {d.name: d for d in gen.consts if d.name.startswith("@tc.")}
    if list(tuples) != list(gen.tconstdata) or any(gen.tconstdata[name] is not d for name, d in tuples.items()):
        unsupported.append("the constant tuples that lowering reads (Gen.tconstdata) are not the module's @tc. constants")
    for name, ci in gen.classes.items():
        own = [len([k for k in table.values() if k >= len(ci.fields)]) for table in (ci.fflag, ci.fbox)]
        if own != [ci.nflag, ci.nbox]:
            unsupported.append(f"class {name}: its struct's flags and boxes are not those its fields name")
    lowered = {fn.f.ll for fn in gen.fns}
    for table, keys in (("rdpass", list(gen.rdpass)), ("vrets", list(gen.vrets)), ("vconst", list(gen.vconst)),
                        ("vcalls", [key[: key.find(" ")] for key in gen.vcalls])):
        if any(key not in lowered for key in keys):
            unsupported.append(f"Gen.{table} names a function the program does not lower")
    attributes = {
        "complete": True, "opts": list(gen.opts), "exceptions": gen.eh, "protocol": gen.gproto,
        "dynamic": diagnostics.dynamic_program(), "promoting": diagnostics.int_program(), "extension": gen.ext,
        "rtmode": gen.rtmode, "debuglines": gen.source_lines.enabled, "plain": list(gen.genplain),
        "directory": os.getcwd() if gen.source_lines.enabled else "",
        "untracked": list(gen.idoff), "objects": dict(gen.ocls), "compared": list(gen.ocmp), "hashed": list(gen.hcls),
        "unequal": list(gen.one), "crossed": list(gen.xobj), "unsupported": unsupported,
    }
    kinds = list(gen.keykinds) + [t for t in gen.builtkinds if t not in gen.keykinds]
    return {
        "attributes": attributes,
        "class_order": list(gen.classes),
        "classes": {name: {"template": name in gen.tmpl, "exception": ci.exc, "module": ci.mod, "tag": ci.tag} for name, ci in gen.classes.items()},
        "source_files": [{"number": str(k), "path": path} for k, path in enumerate(diagnostics.FILES)] if gen.source_lines.enabled else [],
        "holes": [{"number": str(k), "type": gen.holes[k]} for k in range(1, len(gen.holes))],
        "globals": [{"symbol": g.v, "type": g.t} for g in gen.globs],
        "roots": [{"value": r} for r in gen.gcroots],
        "constants": [{"name": d.name, "kind": d.kind, "text": d.text, "refs": list(d.refs),
                       "items": [{"value": v.v, "type": v.t} for v in d.items]} for d in gen.consts],
        "runtime": [{"key": k} for k in gen.rtfns],
        "runtime_data": [{"symbol": s} for s in gen.rtdatas],
        "externs": [{"key": key, "symbol": p.symbol, "params": list(p.params), "result": p.result, "provided": p.provided,
                     "c": p.c, "csym": p.csym, "library": p.library, "ctypes": list(p.ctypes), "cret": p.cret, "at": p.at,
                     "direct": p.direct, "declare": p.declare, "dynamic": p.dynamic, "narrow": p.narrow}
                    for key, p in gen.externs.items()],
        "key_kinds": [{"type": t, "kind": gen.keykinds.get(t, ""), "built": gen.builtkinds.get(t, "")} for t in kinds],
        "functions": {fn.f.ll: function_attributes(fn, gen) for fn in gen.fns},
        "function_order": [fn.f.ll for fn in gen.fns],
    }


def refusals(module):
    """Why a module record cannot be compiled yet, or []: compile fails closed on what its text
    does not hold."""
    a = module["attributes"]
    found = []
    if not a["complete"]:
        found.append("the module does not declare the state that lowering reads: print it from a typed-after "
                      "snapshot (tools/inspect_compiler.py), taken at the lowering boundary")
    if a["extension"] != "":
        found.append(f"the entry points of extension module {a['extension']} (pystachy ext: Gen.funcs, gen_pyext) are not serializable yet")
    if a["rtmode"]:
        found.append("runtime.py's module (pystachy rt: Gen.rtdefs) is not serializable yet")
    if a["debuglines"] and (len(module["source_files"]) == 0 or a["directory"] == ""):
        found.append("the module has LLVM line tables (PYSTACHY_DEBUG_LINES), but no files or directory for them to name")
    return found + list(a["unsupported"])


def gen_for_module(module):
    """A fresh code generator that holds what lowering reads, as a module record declares it
    (lowering_state): its settings, classes, constants, globals, runtime and extern declarations,
    holes and their key kinds, dispatch tables and functions, at the lowering boundary."""
    problems = refusals(module)
    require(not problems, "cannot compile the module: " + "; ".join(problems))
    ir, specs, symbols, syntax, utils = compiler()
    from src.pystachy_compiler.gen import Gen
    from src.pystachy_compiler.lower_module import ExternDecl
    from src.pystachy_compiler.source_lines import SourceLines
    a = module["attributes"]
    g = Gen()
    # (whatever PYSTACHY_DEBUG_LINES says: the module's line tables, if it has them, name its files
    # in its directory, which compile_module gives diagnostics.FILES)
    g.source_lines = SourceLines(a["debuglines"])
    g.source_lines.directory = a["directory"]
    require([x["number"] for x in module["source_files"]] == [str(k) for k in range(len(module["source_files"]))],
            "files are numbered from 0, in order")
    g.opts = {o: True for o in a["opts"]}
    g.eh = a["exceptions"]
    g.gproto = a["protocol"]
    g.genplain = {t: True for t in a["plain"]}
    g.idoff = {m: True for m in a["untracked"]}
    g.ocls = dict(a["objects"])
    g.ocmp = {c: True for c in a["compared"]}
    g.hcls = {c: True for c in a["hashed"]}
    g.one = {c: True for c in a["unequal"]}
    g.xobj = {c: True for c in a["crossed"]}
    infos = class_infos(module)
    for name, c in module["classes"].items():
        infos[name].exc = c["exception"]
        infos[name].mod = c["module"]
        if c["template"]:
            g.tmpl[name] = True
    g.classes.update(infos)
    require([h["number"] for h in module["holes"]] == [str(k) for k in range(1, len(module["holes"]) + 1)],
            "holes are numbered from 1, in order")
    g.holes = [""] + [h["type"] for h in module["holes"]]
    g.globs = [ir.Val(x["symbol"], x["type"]) for x in module["globals"]]
    g.gcroots = [x["value"] for x in module["roots"]]
    for c in module["constants"]:
        d = ir.Data(c["kind"], c["name"])
        d.text = c["text"]
        d.refs = list(c["refs"])
        d.items = [ir.Val(v["value"], v["type"]) for v in c["items"]]
        g.consts.append(d)
        if d.name.startswith("@tc."):
            g.tconstdata[d.name] = d
    for x in module["runtime"]:
        require(x["key"] in specs.RUNTIME, f"runtime {x['key']}: no RUNTIME entry")
        g.rtfns[x["key"]] = utils.RtFn(x["key"])
    for x in module["runtime_data"]:
        require(x["symbol"] in specs.RTDATA, f"rtdata {x['symbol']}: no RTDATA entry")
        g.rtdatas[x["symbol"]] = True
    for x in module["externs"]:
        plan = ExternDecl(symbols.FnInfo("", x["symbol"], syntax.Node("def", "", 1), ""))
        for field, key in (("params", "params"), ("result", "result"), ("provided", "provided"), ("c", "c"),
                           ("csym", "csym"), ("library", "library"), ("ctypes", "ctypes"), ("cret", "cret"), ("at", "at"),
                           ("direct", "direct"), ("declare", "declare"), ("dynamic", "dynamic"), ("narrow", "narrow")):
            setattr(plan, field, copy.copy(x[key]))
        g.externs[x["key"]] = plan
    for x in module["key_kinds"]:
        if x["kind"] != "":
            g.keykinds[x["type"]] = x["kind"]
        if x["built"] != "":
            g.builtkinds[x["type"]] = x["built"]
    for record in module["functions"]:
        fa = record["attributes"]
        symbol = record["symbol"]
        for ins in [i for b in record["blocks"] for i in b["operations"] if i["op"] == "rt"]:
            # (each runtime function an op calls is one the module declares, as the frontend
            # declares it where it makes the op: Gen.runtime)
            require(ins["text"] in g.rtfns, f"{symbol}: rt entry={ins['text']} calls a runtime function the module does not declare")
        g.fns.append(to_ifn(record))
        if fa["closed"]:
            g.rdpass[symbol] = True
        if fa["tupleret"] != 0:
            g.vrets[symbol] = fa["tupleret"]
        if fa["tupleconst"]:
            g.vconst[symbol] = True
        for v in fa["tuplecalls"]:
            g.vcalls[f"{symbol} {v}"] = True
    # (the typed program is final: lowering is the next stage, pipeline.py)
    g.pipeline.stage = "finalize"
    g.pipeline.history = ["prepare", "discover", "analyze", "optimize", "finalize"]
    return g


def compile_module(module):
    """The LLVM module that the compiler's own lowering (Gen.lower_program) prints for a module
    record, with the program's opt-ins (dynamic Any, promoting ints) set as it reads them."""
    compiler()
    from src.pystachy_compiler import diagnostics
    g = gen_for_module(module)
    a = module["attributes"]
    saved = (dict(diagnostics.DYNFILES), dict(diagnostics.INTFILES), list(diagnostics.FILES))
    diagnostics.FILES[:] = [x["path"] for x in module["source_files"]]  # (the files its line tables name)
    diagnostics.DYNFILES.clear()
    diagnostics.INTFILES.clear()
    if a["dynamic"]:
        diagnostics.DYNFILES[0] = True
    if a["promoting"]:
        diagnostics.INTFILES[0] = True
    errors = StringIO()
    try:
        with redirect_stderr(errors):
            lowered = g.lower_program()
    except SystemExit:
        raise TextError(f"lowering failed: {errors.getvalue().strip()}") from None
    except (KeyError, IndexError, ValueError, AttributeError) as error:
        # (a module whose declarations do not hold what its functions name)
        raise TextError(f"lowering failed: {type(error).__name__}: {error}") from None
    finally:
        diagnostics.DYNFILES.clear()
        diagnostics.DYNFILES.update(saved[0])
        diagnostics.INTFILES.clear()
        diagnostics.INTFILES.update(saved[1])
        diagnostics.FILES[:] = saved[2]
    sys.stderr.write(errors.getvalue())
    return lowered


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
        # (the verifier names a block without a label "(unnamed)", where the text writes it "")
        got = "" if reported is not None and reported.group(2) == "(unnamed)" else reported.group(2) if reported is not None else None
        if reported is None:
            problems.append(f"{name}: line {want['line']}: expected error {{{{{want['message']}}}}} was not reported")
        elif want["message"] not in reported.group(3) or got != block:
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


def inspected(program, directory, timeout=300.0):
    """(report, typed-after snapshot or None, LLVM text or None) of a program, inspected in a
    new directory under directory (tools/inspect_compiler.py, typed-after only), with the
    PYSTACHY_PATH that tests/run.sh gives it where it has a NAME.path."""
    output = Path(directory) / "inspect"
    env = dict(os.environ)
    program = Path(program).resolve()
    if program.with_suffix(".path").exists():
        prepared = subprocess.run(["sh", str(ROOT / "tests/prepare_path.sh"), str(program), str(directory)], cwd=ROOT,
                                  capture_output=True, text=True, check=True)
        env["PYSTACHY_PATH"] = str((ROOT / prepared.stdout.strip()).resolve())
    subprocess.run([sys.executable, str(ROOT / "tools/inspect_compiler.py"), str(program), "--output", str(output),
                    "--typed-after-only", "--timeout", str(timeout)], cwd=ROOT, env=env, capture_output=True, check=False)
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    snapshot = json.loads((output / "typed-after.json").read_text(encoding="utf-8")) if (output / "typed-after.json").exists() else None
    llvm = (output / "llvm.ll").read_text(encoding="latin-1") if (output / "llvm.ll").exists() else None
    return report, snapshot, llvm


def first_difference(want, got):
    """The first line at which LLVM text got differs from want, for a message."""
    left, right = want.split("\n"), got.split("\n")
    for k in range(min(len(left), len(right))):
        if left[k] != right[k]:
            return f"line {k + 1}: the compiler's {left[k][:120]!r}, the text's {right[k][:120]!r}"
    return f"the compiler's LLVM has {len(left)} lines, the text's {len(right)}"


def roundtrip_program(program, timeout=300.0):
    """(status, detail) of a program's round trip: its typed-after module printed, parsed back and
    compiled (compile_module), the LLVM compared byte for byte with what the compiler emitted in
    the same inspection. status: ok; differs (detail: where); refused (detail: what the module
    cannot hold yet, refusals); rejected (the compiler rejects the program); error."""
    with tempfile.TemporaryDirectory(prefix=".typed-ir-roundtrip-") as directory:
        try:
            report, snapshot, llvm = inspected(program, directory, timeout)
        except (OSError, ValueError, subprocess.CalledProcessError) as error:
            return "error", f"inspection failed: {error}"
    if report["status"] != "ok" or snapshot is None or llvm is None:
        diagnostics = report.get("diagnostics") or [{}]
        status = "rejected" if report["status"] == "rejected" else "error"
        return status, f"inspection {report['status']}: {diagnostics[0].get('message', '')}"
    try:
        module = module_from_snapshot(snapshot)
        problems = refusals(module)
        if problems:
            return "refused", problems[0]
        written = format_module(module)
        parsed = parse_module(written)
        if format_module(parsed) != written:
            return "error", "the printed module does not print again as it was"
        lowered = compile_module(parsed)
    except TextError as error:
        return "error", str(error)
    if lowered != llvm:
        return "differs", first_difference(llvm, lowered)
    return "ok", ""


def roundtrip_worker(job):
    program, timeout = job
    try:
        return program, roundtrip_program(program, timeout)
    except Exception as error:  # (a measurement records every program, as an error)
        return program, ("error", f"{type(error).__name__}: {error}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("mode", choices=("print", "check", "json", "verify", "compile", "roundtrip"))
    parser.add_argument("path", type=Path, nargs="+")
    parser.add_argument("--function", default="", help="print: only functions whose symbol contains this, without the module")
    parser.add_argument("--locations", action="store_true", help="print: each instruction's source location")
    parser.add_argument("-o", dest="output", type=Path, help="compile: the LLVM module's file (default: standard output)")
    parser.add_argument("--jobs", type=int, default=1, help="roundtrip: programs inspected at once (default: 1)")
    parser.add_argument("--timeout", type=float, default=300.0, help="roundtrip: each inspection's deadline in seconds")
    parser.add_argument("--records", type=Path, help="roundtrip: write each program's result here, as JSON lines")
    args = parser.parse_args()
    if args.mode != "roundtrip" and len(args.path) != 1:
        parser.error(f"{args.mode} takes one file")
    path = args.path[0]
    try:
        if args.mode == "roundtrip":
            return roundtrip_main(args)
        source = path.read_text(encoding="utf-8")
        if args.mode == "print":
            snapshot = json.loads(source)
            attributes = snapshot["lowering"]["functions"] if "lowering" in snapshot else {}
            if args.function == "" and all(table in snapshot for table in SNAPSHOT_TABLES):
                parsed = module_from_snapshot(snapshot)
                problems = module_roundtrip_errors(parsed)
            else:
                parsed = [from_snapshot(f, snapshot.get("files", []), attributes.get(f["symbol"]))
                          for f in snapshot["functions"] if args.function in f["symbol"]]
                problems = [e for r in parsed for e in roundtrip_errors(r)]
            if problems:
                print("\n".join(problems), file=sys.stderr)
                return 1
            sys.stdout.write(format_text(parsed, args.locations))
            return 0
        parsed = parse(source)
        records = parsed["functions"] if isinstance(parsed, dict) else parsed
        if args.mode == "compile":
            require(isinstance(parsed, dict), "compile takes a module, not functions alone")
            lowered = compile_module(parsed)
            if args.output is None:
                sys.stdout.write(lowered)
            else:
                args.output.write_text(lowered, encoding="latin-1")
            return 0
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
            print(f"typed_ir_text: {path} is not in the printed form", file=sys.stderr)
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


def roundtrip_main(args):
    """roundtrip: each program's result (roundtrip_program), then the count of each status and
    the most common reasons of the programs that do not round-trip."""
    from collections import Counter
    from concurrent.futures import ProcessPoolExecutor
    jobs = [(str(p), args.timeout) for p in args.path]
    results = {}
    out = args.records.open("w", encoding="utf-8") if args.records is not None else None
    try:
        with ProcessPoolExecutor(max_workers=max(1, args.jobs)) as pool:
            for program, (status, detail) in pool.map(roundtrip_worker, jobs):
                results[program] = (status, detail)
                print(f"{status}: {program}" + (f": {detail}" if detail else ""), flush=True)
                if out is not None:
                    out.write(json.dumps({"program": program, "status": status, "detail": detail}) + "\n")
                    out.flush()
    finally:
        if out is not None:
            out.close()
    counts = Counter(status for status, _ in results.values())
    compiled = len(results) - counts["rejected"]
    print(f"typed_ir_text: {counts['ok']} of {compiled} programs that compile round-trip"
          f" ({', '.join(f'{n} {s}' for s, n in sorted(counts.items()))})")
    reasons = Counter(re.sub(r"@[\w.$<>-]+|\b\d+\b", "_", detail) for status, detail in results.values() if status in ("differs", "refused", "error"))
    for reason, n in reasons.most_common(10):
        print(f"  {n}: {reason}")
    return 0 if counts["ok"] == compiled else 1


if __name__ == "__main__":
    sys.exit(main())
