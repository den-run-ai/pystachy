"""Small runtime functions inlined into the JIT tier's code (#705).

The JIT tier calls the precompiled runtime, whose code LLVM cannot inline into the program: a read
of a list[float], a float division or a call of math.sqrt() stays a call in each iteration of a
loop, where an AOT build, which optimizes the program and the runtime as one module, inlines it.
prepare() makes, once per runtime build, from the runtime's optimized IR, the text of
available_externally copies of its small functions: LLVM may inline such a copy, and a call it does
not inline reaches the runtime's own function, so the program behaves as before. splice() puts
those that a program declares into its module, before the JIT's optimizations.

A copy takes with it private copies of the constants (messages) and local functions (cold failure
paths) that it uses, renamed rtj.*, and declarations of the runtime's other functions and globals;
the runtime's named struct types are spelled as their literal types, of the same layout (a named
type must be defined before an instruction of a module uses it, and copies lie among the program's
functions).
A function that reaches a local variable of the runtime (state that a copy would split), uses the
stack's or frame's address, handles exceptions itself or has metadata operands is not copied.
Copies carry their attributes in line and no metadata (alias tags only add facts).

A copy is spliced only for a function that a call which may run many times makes (hot_calls(): in a
loop, or in a function that such a call, the runtime or a recursion may reach), and the program's
other calls of it are marked noinline: code that runs once is not made larger, nor slower to
compile, by copies that cannot pay for themselves (PYSTACHY_OPT=-jitloops inlines them all).
"""
from __future__ import annotations

# the most instructions of a copied function, and of the local functions it takes with it
MOST = 40
LOCAL_MOST = 80
# the scalar types a copied function's signature may hold (splice() compares signatures by them)
SCALARS = ["void", "i1", "i8", "i16", "i32", "i64", "ptr", "float", "double"]
# what a copied function or its local functions may not contain
BARRED = [" invoke ", "personality", "metadata ", " asm ", "@llvm.frameaddress", "@llvm.stacksave",
          "@llvm.stackrestore", "@llvm.returnaddress", "@llvm.eh.", "@llvm.localescape", "blockaddress",
          "indirectbr", "musttail", "returns_twice", "thread_local", " callbr ", "@llvm.va_start",
          "@llvm.coro."]
# functions the program calls only off an inline fast path of its own (listfast reads a bytes' byte
# in line, and calls the runtime for an index past its end or negative): a copy would put that cold
# path into each loop, which made json_loads' loop 5% slower
COLD = ["@pys_bytes_get"]
# the linkage, visibility and preemption words of a define line or a global's line
LINKAGE = ["dso_local", "dso_preemptable", "internal", "private", "hidden", "protected", "external",
           "linkonce", "linkonce_odr", "weak", "weak_odr", "available_externally", "extern_weak", "common"]
HEADER = "; pystachy jit helpers 1\n"


def name_end(text: str, i: int) -> int:
    # the end of the name that starts at text[i] (after its @ or %): quoted, or of [-a-zA-Z$._0-9]
    n = len(text)
    if i < n and text[i] == '"':
        j = text.find('"', i + 1)
        return n if j < 0 else j + 1
    j = i
    while j < n:
        c = ord(text[j])
        if (c >= 97 and c <= 122) or (c >= 65 and c <= 90) or (c >= 48 and c <= 57) or c == 46 or c == 95 or c == 36 or c == 45:
            j += 1
        else:
            return j
    return j


def tokens(text: str, sigil: str) -> list[str]:
    # the names in text that start with sigil (@ or %), in order, each once
    out: list[str] = []
    seen: dict[str, bool] = {}
    i = text.find(sigil)
    while i >= 0:
        j = name_end(text, i + 1)
        if j > i + 1:
            t = text[i:j]
            if t not in seen:
                seen[t] = True
                out.append(t)
        i = text.find(sigil, max(j, i + 1))
    return out


def rename(text: str, names: dict[str, str]) -> str:
    # text with each @ or % name of names replaced (whole names only)
    out: list[str] = []
    i = 0
    while i < len(text):
        a = text.find("@", i)
        p = text.find("%", i)
        k = a if a >= 0 and (p < 0 or a < p) else p
        if k < 0:
            out.append(text[i:])
            break
        out.append(text[i:k])
        j = name_end(text, k + 1)
        t = text[k:j]
        out.append(names[t] if t in names else t)
        i = max(j, k + 1)
    return "".join(out)


def first_name(line: str) -> str:
    # the first @ name of a define or declare line, or of a global's line: its own
    i = line.find("@")
    return "" if i < 0 else line[i : name_end(line, i + 1)]


def inline_attributes(text: str, groups: dict[str, str]) -> str:
    # text with each attribute group #N spelled in line
    out: list[str] = []
    i = 0
    while True:
        k = text.find(" #", i)
        if k < 0:
            out.append(text[i:])
            break
        j = k + 2
        while j < len(text) and text[j].isdigit():
            j += 1
        out.append(text[i:k])
        g = text[k + 1 : j]
        if j > k + 2 and g in groups:
            out.append(" " + groups[g] if groups[g] != "" else "")
        else:
            out.append(text[k:j])
        i = j
    return "".join(out)


def strip_metadata(line: str) -> str:
    # an instruction without its metadata attachments (", !tbaa !5"); a define line without its own
    if not line.startswith("define "):
        k = line.find(", !")
        return line[:k] if k >= 0 else line
    words = line.split(" ")
    kept: list[str] = []
    skip = False
    for w in words:
        if skip:
            skip = False
        elif w.startswith("!") and len(w) > 1 and w[1] != "=":
            skip = True
        else:
            kept.append(w)
    return " ".join(kept)


def params(header: str) -> str:
    # the text between a define or declare line's name and its parameters' closing parenthesis
    i = header.find("(", header.find("@"))
    depth = 0
    j = i
    while j < len(header):
        if header[j] == "(":
            depth += 1
        elif header[j] == ")":
            depth -= 1
            if depth == 0:
                break
        j += 1
    return header[i + 1 : j]


def relink(header: str, start: str) -> str:
    # a define line (or "declare") with its linkage words dropped, begun with start
    word = header[: header.find(" ")]
    at = header.find("@")
    before = [w for w in header[len(word) + 1 : at].split(" ") if w != "" and w not in LINKAGE]
    return start + " " + " ".join(before) + (" " if len(before) > 0 else "") + header[at:]


def signature(header: str) -> str:
    # "ret(p1,p2,...)" of a define or declare line whose types are all SCALARS, else ""
    at = header.find("@")
    before = header[:at].strip().split(" ")
    ret = before[-1]
    if ret not in SCALARS:
        return ""
    types: list[str] = []
    ps = params(header).strip()
    if ps != "":
        for p in ps.split(","):
            t = p.strip().split(" ")[0]
            if t not in SCALARS or t == "void":
                return ""
            types.append(t)
    return ret + "(" + ",".join(types) + ")"


def declaration(header: str, groups: dict[str, str]) -> str:
    # a declare line for a define line: its parameters' names, linkage and metadata dropped
    ps = params(header)
    kept: list[str] = []
    if ps.strip() != "":
        for p in ps.split(","):
            words = p.strip().split(" ")
            if len(words) > 1 and words[-1].startswith("%"):
                words = words[:-1]
            kept.append(" ".join(words))
    at = header.find("@")
    start = header.find("(", at)
    tail = strip_metadata("define " + header[start + len(ps) + 2 :].rstrip())[len("define ") :].rstrip()
    if tail.endswith("{"):
        tail = tail[:-1].rstrip()
    line = relink(header[:start], "declare") + "(" + ", ".join(kept) + ")" + (" " + tail if tail != "" else "")
    return inline_attributes(line, groups)


def global_kind(line: str) -> str:
    # "global" or "constant": the word of a global's line that says which, "" if none
    words = line[line.find(" = ") + 3 :].split(" ")
    i = 0
    while i < len(words) and words[i] != "global" and words[i] != "constant":
        if words[i].startswith("c\"") or words[i].startswith("["):
            return ""
        i += 1
    return words[i] if i < len(words) else ""


def global_declaration(line: str) -> str:
    # an external declaration for an exported global's definition line (its initializer dropped)
    name = first_name(line)
    words = line[line.find(" = ") + 3 :].split(" ")
    i = 0
    while i < len(words) and words[i] != "global" and words[i] != "constant":
        i += 1
    if i + 1 >= len(words) or "thread_local" in words[:i]:
        return ""
    kind = words[i]
    j = i + 1
    parts: list[str] = []
    depth = 0
    while j < len(words):
        w = words[j]
        parts.append(w)
        depth += w.count("[") + w.count("{") + w.count("<") - w.count("]") - w.count("}") - w.count(">")
        if depth <= 0:
            break
        j += 1
    t = " ".join(parts).rstrip(",")
    k = line.rfind(", align ")
    return f"{name} = external {kind} {t}" + (line[k:] if k >= 0 else "")


def size(body: list[str]) -> int:
    # a function's instructions
    return len([b for b in body[1:-1] if b.startswith("  ") and not b.startswith("  ;")])


def barred(body: list[str]) -> bool:
    # does a function hold what no copy may (BARRED), or a header a copy could not keep?
    if "..." in params(body[0]):
        return True
    if " comdat" in body[0] or " section " in body[0] or " prefix " in body[0] or " prologue " in body[0]:
        return True
    text = "\n".join(body)
    return len([b for b in BARRED if b in text]) > 0


def copy(body: list[str], groups: dict[str, str], renamed: dict[str, str], start: str) -> str:
    # a function's lines as a copy, begun with start ("define available_externally" or "define
    # internal"): its attributes in line, no metadata, local names renamed
    out = [rename(inline_attributes(strip_metadata(b), groups), renamed) for b in body]
    out[0] = relink(out[0], start)
    return "\n".join(out)


def prepare(runtime: str) -> str:
    # the runtime's IR text -> the helpers' text: items, each a line "; item KIND NAME ..." and its
    # text. KIND helper is an available_externally copy (NAME, its signature, then the names of the
    # items it needs); const (a constant's copy), local (a local function's copy) and decl (a
    # declaration of the runtime's) are what helpers need (NAME, then the items they need)
    groups: dict[str, str] = {}
    types: dict[str, str] = {}
    globals_: dict[str, str] = {}
    decls: dict[str, str] = {}
    funcs: dict[str, list[str]] = {}
    local: dict[str, bool] = {}
    lines = runtime.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("attributes #"):
            k = line.find(" = { ")
            if k > 0 and line.endswith(" }"):
                groups[line[len("attributes ") : k]] = line[k + 5 : -2]
        elif line.startswith("%") and " = type " in line:
            types[line[: line.find(" = type ")]] = line
        elif line.startswith("@"):
            n = first_name(line)
            globals_[n] = line
            rest = line[len(n) + 3 :]
            local[n] = rest.startswith("private ") or rest.startswith("internal ")
        elif line.startswith("declare "):
            decls[first_name(line)] = line
        elif line.startswith("define "):
            n = first_name(line)
            body: list[str] = []
            while i < len(lines) and lines[i] != "}":
                body.append(lines[i])
                i += 1
            body.append("}")
            funcs[n] = body
            local[n] = line.startswith("define internal ") or line.startswith("define private ")
        i += 1

    # each named type as its literal type ({ i64, ptr }), the named types within it spelled too (a
    # struct holds another by value, never itself)
    renamed: dict[str, str] = {}
    for n in types:
        renamed[n] = types[n][len(n) + len(" = type ") :]
    rounds = 0
    changed = True
    while changed and rounds < 64:
        changed = False
        for n in types:
            e = rename(renamed[n], renamed)
            if e != renamed[n]:
                renamed[n] = e
                changed = True
        rounds += 1

    helpers: list[str] = []
    items: list[str] = []
    made: dict[str, bool] = {}
    for n in [f for f in funcs]:
        if local[n] or not n.startswith("@pys_") or n in COLD:
            continue
        sig = signature(funcs[n][0])
        if sig == "" or size(funcs[n]) > MOST or barred(funcs[n]) or " noinline" in inline_attributes(funcs[n][0], groups):
            continue
        # what it reaches: local functions and constants (copied), types, and the runtime's other
        # functions and globals (declared), through the text of each
        need: list[str] = []
        scan = ["\n".join(funcs[n])]
        seen: dict[str, bool] = {n: True}
        ok = True
        local_size = 0
        while len(scan) > 0 and ok:
            text = scan.pop()
            for t in tokens(text, "%"):
                if t in types and ("opaque" in renamed[t] or "%" in renamed[t]):
                    ok = False  # (a type of no layout here)
            for t in tokens(text, "@"):
                if t in seen:
                    continue
                seen[t] = True
                if t in funcs and local[t]:
                    if barred(funcs[t]):
                        ok = False
                    local_size += size(funcs[t])
                    need.append(t)
                    scan.append("\n".join(funcs[t]))
                elif t in globals_ and local[t]:
                    if global_kind(globals_[t]) != "constant" or "thread_local" in globals_[t]:
                        ok = False  # (a variable of the runtime's own, which a copy would split)
                    need.append(t)
                    scan.append(globals_[t][len(t) :])
                elif t in globals_:
                    d = global_declaration(globals_[t])
                    if d == "":
                        ok = False  # (one of each thread, or a global this cannot declare)
                    need.append(t)
                    scan.append(d[len(t) :])
                elif t in funcs:
                    need.append(t)
                    scan.append(declaration(funcs[t][0], groups)[len("declare ") :])
                elif t in decls:
                    need.append(t)
                    scan.append(decls[t][len("declare ") :])
        if not ok or local_size > LOCAL_MOST:
            continue
        for t in need:
            if t not in renamed and (t in funcs or t in globals_) and local[t]:
                renamed[t] = "@" + ('"rtj.' + t[2:] if t.startswith('@"') else "rtj." + t[1:])
        deps = [renamed[t] if t in renamed else t for t in need]
        helpers.append("; item helper " + n + " " + sig + (" " + " ".join(deps) if len(deps) > 0 else ""))
        helpers.append(copy(funcs[n], groups, renamed, "define available_externally"))
        # the items it needs, each once
        for t in need:
            r = renamed[t] if t in renamed else t
            if r in made:
                continue
            made[r] = True
            text = ""
            inner: list[str] = []
            kind = "decl"
            if t in funcs and local[t]:
                kind = "local"
                text = copy(funcs[t], groups, renamed, "define internal")
                for u in tokens("\n".join(funcs[t]), "@"):
                    if u != t and (u in funcs or u in globals_ or u in decls):
                        inner.append(renamed[u] if u in renamed else u)
            elif t in funcs:
                text = rename(declaration(funcs[t][0], groups), renamed)
            elif t in globals_ and local[t]:
                kind = "const"
                g = rename(globals_[t], renamed)
                words = g[len(r) + 3 :].split(" ")
                k = 0
                while k < len(words) and words[k] != global_kind(g):
                    k += 1
                text = r + " = private " + " ".join([w for w in words[:k] if w not in LINKAGE] + words[k:])
                inner = [renamed[u] if u in renamed else u for u in tokens(globals_[t][len(t) :], "@")
                         if u in funcs or u in globals_ or u in decls]
            elif t in globals_:
                text = rename(global_declaration(globals_[t]), renamed)
            else:
                text = rename(inline_attributes(strip_metadata(relink(decls[t], "declare")), groups), renamed)
            if text == "":
                return ""  # (a global this code cannot declare: no helpers)
            items.append("; item " + kind + " " + r + (" " + " ".join(inner) if len(inner) > 0 else ""))
            items.append(text)
    return HEADER + "\n".join(helpers + items) + "\n" if len(helpers) > 0 else ""


def module(table: str) -> str:
    # every helper and item of table as one module, which opt verifies once per runtime build: a
    # declaration of a function that the table also copies is left out (a module holds one of each)
    copied: dict[str, bool] = {}
    for b in table.split("; item helper ")[1:]:
        copied[b[: b.find(" ")]] = True
    out: list[str] = []
    for b in table.split("; item ")[1:]:
        words = b[: b.find("\n")].split(" ")
        if words[0] == "decl" and words[1] in copied:
            continue
        out.append(b[b.find("\n") + 1 :])
    return "".join(out)


def opcode_at(line: str) -> int:
    # where an instruction's opcode begins ("  %x = call ..." -> at "call"), -1 for a line that holds none
    if not line.startswith("  ") or line.startswith("   "):
        return -1
    if not line.startswith("  %"):
        return 2
    k = line.find(" = ", 3)
    return -1 if k < 0 else k + 3


def calls_at(line: str, o: int) -> bool:
    # is the opcode at line[o] a call's or an invoke's?
    return (line.startswith("call ", o) or line.startswith("invoke ", o) or line.startswith("tail call ", o)
            or line.startswith("musttail call ", o) or line.startswith("notail call ", o))


def callee_from(line: str, i: int) -> int:
    # where the name that the call at line[i:] calls (@f or %fp) begins: the first name followed by its
    # arguments' parenthesis, -1 if none
    while i < len(line):
        a = line.find("@", i)
        p = line.find("%", i)
        s = a if a >= 0 and (p < 0 or a < p) else p
        if s < 0:
            return -1
        j = name_end(line, s + 1)
        if j > s + 1 and j < len(line) and line[j] == "(":
            return s
        i = max(j, s + 1)
    return -1


def callee_at(line: str) -> int:
    # where the name that a call or invoke instruction calls (@f or %fp) begins, -1 for another line
    o = opcode_at(line)
    return callee_from(line, o) if o >= 0 and calls_at(line, o) else -1


def callee(line: str) -> str:
    # the name that a call or invoke instruction calls, "" for another line
    s = callee_at(line)
    return "" if s < 0 else line[s : name_end(line, s + 1)]


def noinline(line: str) -> str:
    # a call or invoke instruction that the inliner may not inline: the attribute after its arguments
    s = callee_at(line)
    if s < 0:
        return line
    k = name_end(line, s + 1)
    depth = 0
    while k < len(line):
        if line[k] == "(":
            depth += 1
        elif line[k] == ")":
            depth -= 1
            if depth == 0:
                break
        k += 1
    return line[: k + 1] + " noinline" + line[k + 1 :]


def cyclic(succ: list[list[int]]) -> list[bool]:
    # which nodes of a graph (each node's successors) lie on a cycle: those of its strongly connected
    # components of more than one node, or with an edge to itself (Tarjan's algorithm, without recursion)
    n = len(succ)
    index = [-1] * n
    low = [0] * n
    held = [False] * n
    out = [False] * n
    stack: list[int] = []
    work: list[int] = []
    at: list[int] = []  # (the next successor of each node of work to visit)
    count = 0
    for root in range(n):
        if index[root] >= 0:
            continue
        index[root] = count
        low[root] = count
        count += 1
        stack.append(root)
        held[root] = True
        work.append(root)
        at.append(0)
        while len(work) > 0:
            v = work[-1]
            k = at[-1]
            if k < len(succ[v]):
                at[-1] = k + 1
                w = succ[v][k]
                if index[w] < 0:
                    index[w] = count
                    low[w] = count
                    count += 1
                    stack.append(w)
                    held[w] = True
                    work.append(w)
                    at.append(0)
                elif held[w] and index[w] < low[v]:
                    low[v] = index[w]
                continue
            work.pop()
            at.pop()
            if len(work) > 0 and low[v] < low[work[-1]]:
                low[work[-1]] = low[v]
            if low[v] == index[v]:
                w = stack.pop()
                held[w] = False
                if w != v:
                    out[w] = True
                    out[v] = True
                    while w != v:
                        w = stack.pop()
                        held[w] = False
                        out[w] = True
                elif v in succ[v]:
                    out[v] = True
    return out


# the opcodes of the instructions that name blocks to branch to (as "label %name")
BRANCHES = ["br ", "switch ", "invoke ", "indirectbr ", "callbr ", "catchswitch ", "catchret ", "cleanupret "]


def hot_calls(lines: list[str], callees: dict[int, str]) -> dict[int, bool]:
    # each call (or invoke) instruction of the program's functions, by its line (and in callees, the
    # name it calls): True for one that may run many times, as far as the text shows. That is one in a
    # loop (a cycle of its function's blocks), or in a function that such a call reaches, as one that
    # the runtime calls (an exported function other than main, such as pys_obj_eq, which a dict's
    # lookups call; or one whose address is taken: a callback, or what an indirect call may call), or
    # a recursion, reaches
    names: dict[str, int] = {}
    first: list[int] = []
    last: list[int] = []
    i = 0
    while i < len(lines):
        if lines[i].startswith("define "):
            names[first_name(lines[i])] = len(first)
            first.append(i)
            j = i
            while j < len(lines) and lines[j] != "}":
                j += 1
            last.append(j)
            i = j
        i += 1
    calls: dict[int, bool] = {}
    owner: dict[int, int] = {}
    edges: list[list[int]] = []
    seeds: list[int] = []
    for f in range(len(first)):
        edges.append([])
        header = lines[first[f]]
        words = header[: header.find("@")].split(" ")
        if "internal" not in words and "private" not in words and first_name(header) != "@main":
            seeds.append(f)
        # its blocks: the first (entry) holds what precedes a label
        label: dict[str, int] = {}
        targets: list[list[str]] = [[]]
        sites: list[int] = []
        blocks: list[int] = []
        b = 0
        for k in range(first[f] + 1, last[f]):
            line = lines[k]
            branches = line.startswith("    ")  # (a switch's cases, or another list of labels, continued)
            if not line.startswith("  "):
                if line == "" or line.startswith(";"):
                    continue
                name = line[: line.find('"', 1) + 1] if line.startswith('"') else line[: line.find(":")]
                b = len(targets)
                label["%" + name] = b
                targets.append([])
                continue
            o = opcode_at(line)
            if o >= 0 and calls_at(line, o):
                c = callee_from(line, o)
                if c >= 0:
                    sites.append(k)
                    blocks.append(b)
                    callees[k] = line[c : name_end(line, c + 1)]
                branches = line.startswith("invoke ", o) or line.startswith("callbr ", o)
            elif o >= 0:
                for w in BRANCHES:
                    if line.startswith(w, o):
                        branches = True
            if branches:
                p = line.find("label %")
                while p >= 0:
                    e = name_end(line, p + 7)
                    targets[b].append(line[p + 6 : e])
                    p = line.find("label %", e)
        succ: list[list[int]] = []
        for named in targets:
            succ.append([label[x] for x in named if x in label])
        looped = cyclic(succ)
        for s in range(len(sites)):
            k = sites[s]
            calls[k] = looped[blocks[s]]
            owner[k] = f
            c = callees[k]
            if c in names:
                edges[f].append(names[c])
                if looped[blocks[s]]:
                    seeds.append(names[c])
    # functions whose addresses are taken: named anywhere but as what a call calls
    for line in lines:
        p = line.find("@")
        if p < 0 or line.startswith("define ") or line.startswith("declare ") or line.startswith(";"):
            continue
        while p >= 0:
            e = name_end(line, p + 1)
            t = line[p:e]
            if t in names and (e >= len(line) or line[e] != "("):
                seeds.append(names[t])
            p = line.find("@", max(e, p + 1))
    recursive = cyclic(edges)
    for f in range(len(first)):
        if recursive[f]:
            seeds.append(f)
    hot = [False] * len(first)
    while len(seeds) > 0:
        f = seeds.pop()
        if not hot[f]:
            hot[f] = True
            seeds.extend(edges[f])
    for k in calls:
        if hot[owner[k]]:
            calls[k] = True
    return calls


def splice(ir: str, table: str, loops: bool) -> str:
    # the program's IR with available_externally copies of the runtime functions it declares (those
    # of table, prepare()'s text, whose signatures match), and the items they need that it lacks. With
    # loops, only those that a call which may run many times makes (hot_calls()), whose other calls
    # are marked noinline
    if not table.startswith(HEADER):
        return ir
    sigs: dict[str, str] = {}
    code: dict[str, str] = {}
    texts: dict[str, str] = {}
    kinds: dict[str, str] = {}
    deps: dict[str, list[str]] = {}
    for b in table[len(HEADER) :].split("; item "):
        nl = b.find("\n")
        words = b[:nl].split(" ")
        if nl < 0 or len(words) < 2:
            continue
        if words[0] == "helper":
            sigs[words[1]] = words[2]
            code[words[1]] = b[nl + 1 :].rstrip("\n")
            deps["helper " + words[1]] = words[3:]
        else:
            kinds[words[1]] = words[0]
            texts[words[1]] = b[nl + 1 :].rstrip("\n")
            deps[words[1]] = words[2:]
    lines = ir.split("\n")
    present: dict[str, bool] = {}
    declared: dict[str, int] = {}
    for i in range(len(lines)):
        line = lines[i]
        if line.startswith("declare "):
            n = first_name(line)
            present[n] = True
            declared[n] = i
        elif line.startswith("define ") or line.startswith("@"):
            present[first_name(line)] = True
    candidates = [n for n in declared if n in code and signature(lines[declared[n]]) == sigs[n]]
    if len(candidates) == 0:
        return ir
    hot: dict[int, bool] = {}
    callees: dict[int, str] = {}
    wanted: dict[str, bool] = {}
    if loops:
        hot = hot_calls(lines, callees)
        for k in hot:
            if hot[k]:
                wanted[callees[k]] = True
    todo: list[str] = []
    copied: dict[str, bool] = {}
    for n in candidates:
        if not loops or n in wanted:
            lines[declared[n]] = code[n]
            todo = todo + deps["helper " + n]
            copied[n] = True
    if len(copied) == 0:
        return ir
    for k in hot:
        if not hot[k] and callees[k] in copied:
            lines[k] = noinline(lines[k])
    added: list[str] = []
    done: dict[str, bool] = {}
    while len(todo) > 0:
        t = todo.pop()
        if t in done or t not in kinds:
            continue
        done[t] = True
        if kinds[t] == "decl" and t in present:
            continue
        added.append(texts[t])
        todo = todo + deps[t]
    return "\n".join(lines) + ("\n" + "\n".join(added) + "\n" if len(added) > 0 else "")
