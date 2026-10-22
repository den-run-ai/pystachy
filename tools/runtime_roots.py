"""Check the runtime's static pointer inventory and explicit collector roots.

Clang's -femit-all-decls keeps unused declarations in the inventory, including a
new static that no runtime function reads yet. LLVM resolves pointer typedefs and
aggregate fields for us. Unions are conservatively classified even when their
selected LLVM storage member has no pointer type. Static roots must be scanned in
full. Dynamic active-range bounds and the documented non-root reasons still need
review; this is not a proof of collector correctness.
"""
import os
from pathlib import Path
import re
import subprocess
import sys


def llvm_type(text):
    """The initial LLVM type, without its value or global attributes."""
    if text.startswith(("[", "{", "<")):
        depth = 0
        for i, c in enumerate(text):
            depth += c in "[{<"
            depth -= c in "]}>"
            if depth == 0:
                return text[:i + 1]
        raise ValueError("unterminated LLVM aggregate type")
    return text.split()[0]


def pointer_statics(ir):
    types = dict(re.findall(r"^(%[\w.]+) = type (.+)$", ir, re.M))

    def holds_pointer(t, seen):
        if re.search(r"\bptr\b|%union\.", t):
            return True
        for name in re.findall(r"%[\w.]+", t):
            if name not in seen:
                if name not in types:
                    raise ValueError(f"unknown LLVM storage type {name}")
                if holds_pointer(types[name], seen | {name}):
                    return True
        return False

    result = set()
    for name, declaration in re.findall(r"^@([\w.]+) = (?:internal|private) (.+)$", ir, re.M):
        if name.startswith("."):
            continue  # compiler-created string constants, not C declarations
        if name.startswith("__const.") and declaration.startswith("unnamed_addr constant "):
            continue  # clang's initializer template for an automatic local array
        m = re.search(r"\b(?:global|constant) (.+)", declaration)
        if m and holds_pointer(llvm_type(m[1]), set()):
            result.add(name)
    return result


def operands(text):
    """Split LLVM operands without splitting aggregate types or constant GEPs."""
    result = []
    depth = 0
    start = 0
    for i, c in enumerate(text):
        depth += c in "([{<"
        depth -= c in ")]}>"
        if c == "," and depth == 0:
            result.append(text[start:i].strip())
            start = i + 1
    result.append(text[start:].strip())
    return result


class StorageLayout:
    """Sizes needed by root GEPs; unfamiliar LLVM types fail closed."""
    def __init__(self, ir):
        self.types = dict(re.findall(r"^(%[\w.]+) = type (.+)$", ir, re.M))
        self.globals = {name: llvm_type(value) for name, value in
                        re.findall(r"^@([\w.]+) = .*?\b(?:global|constant) (.+)$", ir, re.M)}
        self.global_alignments = {name: int(alignment) for name, alignment in
                                  re.findall(r"^@([\w.]+) = .*?, align (\d+)(?:,|$)", ir, re.M)}
        layout = re.search(r'^target datalayout = "([^"]+)"', ir, re.M)
        layout = layout[1] if layout else ""
        pointer = re.search(r"(?:^|-)p(?:0)?:(\d+):(\d+)", layout)
        self.pointer = (int(pointer[1]) // 8, int(pointer[2]) // 8) if pointer else (8, 8)
        self.alignments = {"i1": 1, "i8": 1, "i16": 2, "i32": 4, "i64": 4,
                           "f16": 2, "f32": 4, "f64": 8, "f128": 16}
        for kind, bits, alignment in re.findall(r"(?:^|-)([if])(\d+):(\d+)", layout):
            self.alignments[kind + bits] = int(alignment) // 8

    def fields(self, t):
        t = self.types.get(t, t)
        if t.startswith("{"):
            return operands(t[1:-1]), False
        if t.startswith("<{"):
            return operands(t[2:-2]), True
        return None

    def size_align(self, t):
        if t in self.types:
            return self.size_align(self.types[t])
        if t == "ptr":
            return self.pointer
        scalar = {"half": "f16", "float": "f32", "double": "f64", "fp128": "f128"}.get(t, t)
        if scalar in self.alignments:
            size = (int(scalar[1:]) + 7) // 8
            align = self.alignments[scalar]
            return (size + align - 1) // align * align, align
        array = re.fullmatch(r"\[(\d+) x (.+)\]", t)
        if array:
            size, align = self.size_align(array[2])
            return int(array[1]) * size, align
        fields = self.fields(t)
        if fields:
            size = 0
            alignment = 1
            for field in fields[0]:
                field_size, align = self.size_align(field)
                align = 1 if fields[1] else align
                size = (size + align - 1) // align * align + field_size
                alignment = max(alignment, align)
            return (size + alignment - 1) // alignment * alignment, alignment
        raise ValueError(f"unsupported root storage type {t}")

    def packed(self, t):
        t = self.types.get(t, t)
        array = re.fullmatch(r"\[\d+ x (.+)\]", t)
        if array:
            return self.packed(array[1])
        fields = self.fields(t)
        return bool(fields and (fields[1] or any(self.packed(field) for field in fields[0])))

    def static_extent(self, name):
        t = self.globals[name]
        size, align = self.size_align(t)
        # scan reads aligned pointer-sized words. Packed nested aggregates can
        # hide a pointer between those words even when the outer struct is aligned.
        if self.packed(t) or size % self.pointer[0] or self.global_alignments.get(name, align) < self.pointer[1]:
            return None
        return size


def add_offset(a, b, scale=1):
    """Byte offsets are affine expressions; zero coefficients cancel exactly."""
    result = dict(a)
    for key, value in b.items():
        result[key] = result.get(key, 0) + value * scale
        if result[key] == 0:
            del result[key]
    return result


def scan_roots(ir):
    """(Global, dereference depth) covered by a correctly directed scan.

    Scanning the slot holding a managed pointer must not be confused with scanning
    the pointed-to object: only the former marks that object itself. Malloc-backed
    root tables instead require a scan of their contents, after one pointer load.
    """
    m = re.search(r"^define [^\n]*@mark_roots\([^\n]*\) [^\n]*\{\n(.*?)^}", ir, re.M | re.S)
    if not m:
        return set()
    layout = StorageLayout(ir)
    pointers = {}
    integers = {}
    excluded = set()
    for line in m[1].splitlines():
        names = set(re.findall(r"@([\w.]+)", line))
        direct = re.match(r"\s*%[\w.]+ = load i\d+, ptr @([\w.]+)(?:,|$)", line)
        if direct:
            names.discard(direct[1])
        # A write or address escape can launder an unknown value through a
        # global. Current root counters are used only by direct integer loads.
        excluded.update(names)

    def integer(value):
        token = value.split()[-1]
        if re.fullmatch(r"-?\d+", token):
            return {} if int(token) == 0 else {"": int(token)}
        # Unknown arithmetic is not an independent symbolic input: two different
        # expressions can denote the same offset or reverse an apparent range.
        return integers.get(token)

    def pointer(value):
        gep = re.search(r"getelementptr (?:inbounds )?(.*)", value)
        if gep:
            args = gep[1].strip()
            args = operands(args[1:-1] if args.startswith("(") else args)
            base = pointer(args[1])
            if base is None:
                return None
            name, depth, offset, constant = base
            t = args[0]
            for n, index in enumerate(args[2:]):
                amount = integer(index)
                if amount is None:
                    return None
                constant = constant and bool(re.fullmatch(r"i\d+ -?\d+", index))
                if n == 0:
                    offset = add_offset(offset, amount, layout.size_align(t)[0])
                    continue
                array = re.fullmatch(r"\[(\d+) x (.+)\]", layout.types.get(t, t))
                if array:
                    t = array[2]
                    offset = add_offset(offset, amount, layout.size_align(t)[0])
                    continue
                fields = layout.fields(t)
                if fields is None or not re.fullmatch(r"i\d+ \d+", index):
                    return None
                at = int(index.split()[-1])
                if at >= len(fields[0]):
                    return None
                position = 0
                for field in fields[0][:at + 1]:
                    size, align = layout.size_align(field)
                    align = 1 if fields[1] else align
                    position = (position + align - 1) // align * align
                    position += size
                t = fields[0][at]
                offset = add_offset(offset, {"": position - layout.size_align(t)[0]})
            return name, depth, offset, constant
        token = re.search(r"([@%][\w.]+)$", value.strip())
        if not token:
            return None
        token = token[1]
        return (token[1:], 0, {}, True) if token.startswith("@") else pointers.get(token)

    scanned = set()
    for line in m[1].splitlines():
        # Do not let control predicates or unrelated integer arithmetic establish
        # pointer provenance. These are the pointer expressions mark_roots uses.
        assign = re.match(r"\s*(%[\w.]+) = (.*)", line)
        if assign:
            name, expression = assign.groups()
            load = re.match(r"load (ptr|i\d+), (.*)", expression)
            if load:
                source = operands(load[2])[0]
                base = pointer(source)
                if load[1] == "ptr" and base is not None and not base[2] and base[3]:
                    pointers[name] = base[0], base[1] + 1, {}, base[3]
                elif load[1].startswith("i"):
                    # Only declared global counters are symbolic inputs. Reloading
                    # an untracked local must not hide unsupported arithmetic.
                    global_ = re.fullmatch(r"ptr @([\w.]+)", source)
                    if global_ and global_[1] not in excluded and re.fullmatch(r"i\d+", layout.globals.get(global_[1], "")):
                        integers[name] = {"load:" + source: 1}
            elif expression.startswith("getelementptr "):
                pointers[name] = pointer(expression)
            elif expression.startswith(("bitcast ptr ", "addrspacecast ptr ")):
                pointers[name] = pointer(expression.split(" to ", 1)[0])
            else:
                arithmetic = re.fullmatch(r"(add|sub)(?: n[us]w)* i\d+ (.*)", expression)
                if arithmetic:
                    left, right = [integer(value) for value in operands(arithmetic[2])]
                    if left is not None and right is not None:
                        integers[name] = add_offset(left, right, 1 if arithmetic[1] == "add" else -1)
        call = re.search(r"\bcall void @scan\((.*)\)", line)
        if call:
            start, end = [pointer(value) for value in operands(call[1])]
            if start is None or end is None or start[:2] != end[:2]:
                continue
            name, depth, first, constant = start
            last = end[2]
            if depth == 0:
                if constant and end[3] and name in layout.globals and not first and last == {"": layout.static_extent(name)}:
                    scanned.add((name, depth))
            elif depth == 1 and layout.globals.get(name) == "ptr":
                distance = add_offset(last, first, -1)
                # Active dynamic subranges remain a reviewed contract (wr_fired).
                # Reject constant/affine empty, backward, negative or unaligned
                # ranges, including separate loads of the same bound.
                if not distance or (set(distance) <= {""} and distance.get("", 0) <= 0):
                    continue
                if any(set(offset) <= {""} and offset.get("", 0) < 0 for offset in [first, last]):
                    continue
                if any(value % layout.pointer[0] for offset in [first, last] for value in offset.values()):
                    continue
                scanned.add((name, depth))
    return scanned


def check_roots(source, ir):
    annotations = {}
    bad = []
    for kind, names, reason in re.findall(r"/\*\s*GC_(ROOT|ROOT_RANGE|NO_ROOT)\(([^)]+)\):([^*]*)\*/", source):
        for name in names.split(","):
            name = name.strip()
            if not re.fullmatch(r"[A-Za-z_]\w*(?:\.\w+)*", name) or not reason.strip():
                bad.append(f"GC roots: malformed annotation for {name!r}")
            if name in annotations:
                bad.append(f"GC roots: duplicate annotation for {name}")
            annotations[name] = kind
    pointers = pointer_statics(ir)
    for name in sorted(pointers - annotations.keys()):
        bad.append(f"GC roots: unclassified static pointer storage {name}")
    for name in sorted(annotations.keys() - pointers):
        bad.append(f"GC roots: annotation names no static pointer storage: {name}")
    scanned = scan_roots(ir)
    for name, kind in annotations.items():
        if kind in {"ROOT", "ROOT_RANGE"} and (name, int(kind == "ROOT_RANGE")) not in scanned:
            bad.append(f"GC roots: {name} is not scanned by mark_roots with {kind} storage semantics")
    return bad


def compile_inventory(source):
    clang = str(Path(os.environ["PYSTACHY_LLVM"]) / "clang") if os.environ.get("PYSTACHY_LLVM") else "clang"
    result = subprocess.run([clang, "-O0", "-S", "-emit-llvm", "-femit-all-decls", str(source), "-o", "-"],
                            capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr.strip())
    return result.stdout


def main():
    path = Path(__file__).resolve().parents[1] / "runtime.c"
    try:
        ir = compile_inventory(path)
        bad = check_roots(path.read_text(), ir)
    except (OSError, ValueError, RuntimeError) as exc:
        sys.exit(f"GC roots: {exc}")
    for problem in bad:
        print(problem)
    print(f"{len(pointer_statics(ir))} static pointer stores: {len(bad)} GC root problems")
    return bool(bad)


if __name__ == "__main__":
    sys.exit(main())
