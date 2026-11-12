"""The precompiled runtime of AOT builds (#706): one optimized module, two views of it.

pystachy build linked the runtime's bitcode into each program, then optimized and compiled the
part the program needed again, which took most of a small program's build. Now the runtime,
specialized for pys_plain (runtime.c), is compiled once to machine code that executables link,
and each program is optimized against an interface of the same module: the bodies of the
functions that LLVM may inline into the program, as available_externally definitions, which
the optimizer reads and code generation never emits, and declarations of the rest.

The module's local symbols (static C functions and data, runtime.py's helpers, constants) become
hidden external symbols of the object, under the same names, so that an inlined body and the
runtime's own code name one definition: a duplicated static would split its state. An AOT
program defines only main and the pys_obj_* callbacks externally, and llvm-link renames a local
symbol of the program whose name a runtime symbol takes.
"""
from __future__ import annotations

# The interface keeps the bodies of functions of up to BODY instructions, about four times what
# -O2's inliner accepts without constant arguments (cost 225 at 5 an instruction), of functions
# that switch on a parameter, whatever their size: a call with a constant selector (an
# operator's code, a method's number) costs only the case it selects, and of alwaysinline ones
BODY = 200


def linkage(t: str) -> bool:
    return t in ["private", "internal", "available_externally", "linkonce", "weak", "common", "appending",
                 "extern_weak", "linkonce_odr", "weak_odr", "external"]


def replaceable(t: str) -> bool:
    # a definition that another may replace at link time: never inlined, never folded
    return t in ["linkonce", "weak", "common", "linkonce_odr", "weak_odr"]


def params(line: str) -> tuple[list[str], int]:
    # the parameters' names (%...) of a define line, and the index after its parameter list
    names: list[str] = []
    i = line.find("@")
    if line[i + 1 : i + 2] == '"':
        i = line.find('"', i + 2)
    i = line.find("(", i)
    depth = 0
    start = i + 1
    while i < len(line):
        c = line[i]
        if c == "(":
            depth += 1
        elif c == ")" or (c == "," and depth == 1):
            if depth == 1:
                last = line[start:i].strip().split(" ")[-1]
                if last.startswith("%"):
                    names.append(last)
                start = i + 1
            if c == ")":
                depth -= 1
                if depth == 0:
                    return (names, i + 1)
        i += 1
    return (names, len(line))


def dispatches(body: list[str], names: list[str]) -> bool:
    # a function that switches on one of its parameters (names)
    for s in body:
        t = s.strip()
        if t.startswith("switch "):
            parts = t.split(" ")
            if len(parts) > 2 and parts[2].rstrip(",") in names:
                return True
    return False


def declaration(head: str, end: int) -> str:
    # head (a define line without its linkage), from end (after its parameter list), as a
    # declaration: what only a definition carries goes (the body's brace, personality, prefix
    # data, metadata attachments such as !dbg or UBSan's !func_sanitize)
    tail = head[end:].strip().split(" ")
    kept: list[str] = []
    i = 0
    while i < len(tail):
        t = tail[i]
        if t == "{" or t == "":
            i += 1
        elif t in ["personality", "prefix", "prologue", "section", "partition"] or t.startswith("!"):
            i += 3 if t in ["personality", "prefix", "prologue"] else 2
        elif t.startswith("comdat"):
            i += 1
        else:
            kept.append(t)
            i += 1
    return "declare " + head[:end] + ("" if len(kept) == 0 else " " + " ".join(kept))


def late_root(new: str) -> str:
    # the module from which llvm-link --only-needed makes the late step's module with the
    # interface: pys_new's declaration (new; its attribute groups are the interface's, and the body
    # brings its own) and a use of it, an external one: llvm-link takes a local or
    # available_externally value only where a value it takes uses it. The late step's own llvm-link
    # --only-needed takes pys_new's body, not this use. "" where the interface has no body of it
    if new == "":
        return ""
    return " ".join([t for t in new.split(" ") if not t.startswith("#")]) + "\n@pys.late = constant ptr @pys_new"


def numbered(s: str) -> bool:
    # a global named by number (@0): unnamed, which a hidden symbol cannot be (opt's
    # name-anon-globals names them first: driver.aot_build)
    i = s.find("@")
    j = i + 1
    while j < len(s) and "0" <= s[j] <= "9":
        j += 1
    return i >= 0 and j > i + 1 and (j == len(s) or s[j] == " " or s[j] == "(")


def split(text: str, body: int) -> list[str]:
    # The runtime's module (text, as opt prints it) as [the object's module, the interface, the
    # declaration of pys_new for the late step (allocelide's: driver.LATE_INLINE), or "" where the
    # interface has no body of pys_new]; [] if data could be replaced at link time (a weak global)
    # or a definition has no name
    obj: list[str] = []
    face: list[str] = []
    new = ""
    lines = text.split("\n")
    # the attribute groups (#N) that hold alwaysinline
    forced: list[str] = []
    for s in lines:
        if s.startswith("attributes #") and s.find(" alwaysinline ") > 0:
            forced.append(s.split(" ")[1])
    i = 0
    while i < len(lines):
        s = lines[i]
        if s.startswith("define "):
            j = i + 1
            while j < len(lines) and lines[j] != "}":
                j += 1
            toks = s[7:].split(" ")
            link = toks[0] if linkage(toks[0]) else ""
            local = link == "internal" or link == "private"
            rest = toks[1:] if link != "" else toks
            if numbered(s[s.find(" @") :]):
                return []
            obj.append("define hidden " + " ".join(rest) if local else s)
            obj.extend(lines[i + 1 : j + 1])
            head = ("hidden " if local else "") + " ".join(rest)
            sig = params(head)
            n = 0
            for b in lines[i + 1 : j]:
                if b.startswith("  ") and not b.startswith("  ;"):
                    n += 1
            tail = head[sig[1] :].strip().split(" ")
            always = len([t for t in tail if t == "alwaysinline" or t in forced]) > 0
            if not replaceable(link) and (n <= body or always or dispatches(lines[i + 1 : j], sig[0])):
                # (in no comdat: the interface defines nothing the object's link could drop)
                face.append("define available_externally " + head[: sig[1]] + " " + " ".join([t for t in tail if not t.startswith("comdat")]))
                face.extend(lines[i + 1 : j + 1])
                if head.find(" @pys_new(") >= 0:
                    new = declaration(head, sig[1])
            else:
                face.append(declaration(head, sig[1]))
            i = j + 1
            continue
        if s.startswith("@") and s.find(" = ") > 0:
            k = s.find(" = ")
            toks = s[k + 3 :].split(" ")
            link = toks[0] if linkage(toks[0]) else ""
            if replaceable(link) or numbered(s[:k]):
                return []
            local = link == "internal" or link == "private"
            rest = toks[1:] if link != "" else toks
            obj.append(s[: k + 3] + "hidden " + " ".join(rest) if local else s)
            if link == "appending" or s.startswith("@llvm."):
                pass  # (constructors and llvm.used stay the object's)
            elif link == "external" or link == "extern_weak":
                face.append(s)
            else:
                g = s[: k + 3] + "available_externally " + ("hidden " if local else "") + " ".join(rest)
                c = g.find(", comdat")
                if c > 0:
                    e = g.find(",", c + 2)
                    g = g[:c] + (g[e:] if e > 0 else "")
                face.append(g)
            i += 1
            continue
        if s.startswith("$") and s.find(" = comdat ") > 0:
            obj.append(s)  # (the interface defines nothing in a comdat)
            i += 1
            continue
        obj.append(s)
        face.append(s)
        i += 1
    return ["\n".join(obj), "\n".join(face), new]
