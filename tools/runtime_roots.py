"""Check the runtime's static pointer inventory and explicit collector roots.

Clang's -femit-all-decls keeps unused declarations in the inventory, including a
new static that no runtime function reads yet. LLVM resolves pointer typedefs and
aggregate fields for us. Unions are conservatively classified even when their
selected LLVM storage member has no pointer type. This is an inventory/scan check,
not a proof that each scan's bounds or the documented non-root reasons are sound.
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


def scan_roots(ir):
    """(Global, dereference depth) used as the base of both scan endpoints.

    Scanning the slot holding a managed pointer must not be confused with scanning
    the pointed-to object: only the former marks that object itself. Malloc-backed
    root tables instead require a scan of their contents, after one pointer load.
    """
    m = re.search(r"^define [^\n]*@mark_roots\([^\n]*\) [^\n]*\{\n(.*?)^}", ir, re.M | re.S)
    if not m:
        return set()
    provenance = {}
    expressions = {}

    def origins(value):
        found = {(name, 0) for name in re.findall(r"@([\w.]+)", value)}
        for value_name in re.findall(r"%[\w.]+", value):
            found.update(provenance.get(value_name, set()))
        return found

    scanned = set()
    for line in m[1].splitlines():
        # Do not let control predicates or unrelated integer arithmetic establish
        # pointer provenance. These are the pointer expressions mark_roots uses.
        assign = re.match(r"\s*(%[\w.]+) = (load ptr, ptr |getelementptr (?:inbounds )?[^,]+, ptr |bitcast ptr |addrspacecast ptr )(.*)", line)
        if assign:
            base = assign[3].split(",", 1)[0]
            provenance[assign[1]] = origins(base)
            if assign[2].startswith("load "):
                provenance[assign[1]] = {(name, depth + 1) for name, depth in provenance[assign[1]]}
            expressions[assign[1]] = line.split(" = ", 1)[1].rsplit(", align ", 1)[0]
        call = re.search(r"\bcall void @scan\((.*)\)", line)
        if call:
            # Constant GEP operands contain commas inside parentheses.
            depth = 0
            for i, c in enumerate(call[1]):
                depth += c in "([{"
                depth -= c in ")]}"
                if c == "," and depth == 0:
                    start, end = call[1][:i].strip(), call[1][i + 1:].strip()
                    # A repeated endpoint (including two loads of the same static)
                    # scans nothing and cannot satisfy an annotated root.
                    start_expr = expressions.get(start.split()[-1], start)
                    end_expr = expressions.get(end.split()[-1], end)
                    if start_expr != end_expr:
                        scanned.update(origins(start) & origins(end))
                    break
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
