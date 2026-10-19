"""re_specialize: matchers generated for a program's regular expressions, which lib/re then runs in
place of its bytecode interpreter (lib/re/_sre.py).

lib/re compiles each pattern to CPython's code and interprets that code; a pattern a program uses
again and again runs the same code each time. This tool records which patterns a program uses
(running it under CPython, which counts the matching calls made on each compiled pattern) and
writes, for each that was used often enough, Python functions that match that one pattern: the
interpreter's work for its code, written out, with its characters' classes decided by tables of
the 256 code points a subject read in place can hold. Pystachy compiles them with the program:
put the module this tool writes (_pystachy_re_specialized.py) next to the program or on
PYSTACHY_PATH, where it is found before lib/'s, which has no matchers.

lib/re looks a pattern up in the module when it compiles it, by its source, its flags and the
code it compiled it to (a matcher made from other code is not used). A matcher runs only on a
subject that lib/re reads in place (bytes: an ASCII str, or a file's bytes that are not UTF-8):
for match() and fullmatch(), and at each position a search tries (_sre.sre_search() keeps its
own loop and prefilters). It declines a match that would nest more than DEPTH group repeats, and
lib/re then runs its interpreter, from where it began. Each matcher does what CPython's sre_lib.h does
for its opcodes, in the same order (marks set and restored, repeats counted and given back), so a
match has the same span, groups and lastindex; tools/test_re_specialize.py checks them against
CPython's re. GROUPREF_EXISTS and the LOCALE opcodes (of bytes patterns, which lib/re does not
have) are not generated: those patterns keep the interpreter.

usage:
  python3 tools/re_specialize.py record [-o PROFILE] PROGRAM [ARG...]
      run PROGRAM under CPython; write the calls of match(), fullmatch(), search(), findall(),
      finditer(), split(), sub(), subn() and scanner() made on each pattern (JSON)
  python3 tools/re_specialize.py generate [-o OUT] [--min-calls N] [--pattern P [--flags F]]... [PROFILE...]
      write OUT (default _pystachy_re_specialized.py) with a matcher for each pattern of the
      profiles called at least N times (default 1), and each pattern given with --pattern
  python3 tools/re_specialize.py check [N] [SEED]
      generate matchers for N random patterns (default 400) and compare lib/re running them, on
      CPython, with CPython's re (see tools/test_re_specialize.py)
"""
import builtins
import importlib.util
import json
import os
import pkgutil
import runpy
import sys
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEPTH = 1000  # the group repeats a match may nest (each a native call) before the interpreter takes it
MAXLINES = 4000  # the generated lines of one pattern's matcher, at most
FORMAT = 1  # the profile's format
RUNNERS = ("runpy", "importlib._bootstrap", "importlib._bootstrap_external")  # (what runs a program for record)

# ---- lib/re on CPython

_loaded = 0


def load_port(specialized=None):
    """lib/re as a package of its own, run by CPython, importing the module of generated matchers
    at the path specialized (default lib/'s, which has none): a new package each time."""
    global _loaded
    # (a matcher nests a call for each group repeat, DEPTH at most, a few frames each)
    sys.setrecursionlimit(max(sys.getrecursionlimit(), 10 * DEPTH))
    # lib/re's private primitives, which Pystachy compiles for re alone: a str's UTF-8 size, and the
    # bytes of a str whose every character is a byte (an ASCII str, on CPython)
    builtins.__pys_text_size = lambda s: len(s.encode("utf-8", "surrogatepass"))
    builtins.__pys_text_bytes = lambda s: s.encode("latin-1")
    path = specialized or os.path.join(ROOT, "lib", "_pystachy_re_specialized.py")
    spec = importlib.util.spec_from_file_location("_pystachy_re_specialized", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["_pystachy_re_specialized"] = module
    spec.loader.exec_module(module)
    _loaded += 1
    name = "pys_re_%d" % _loaded
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "lib", "re", "__init__.py"),
                                                  submodule_search_locations=[os.path.join(ROOT, "lib", "re")])
    port = importlib.util.module_from_spec(spec)
    sys.modules[name] = port
    spec.loader.exec_module(port)
    return port


# ---- the code, as nodes


class Unsupported(Exception):
    pass


def parse(port, code):
    """The code of a pattern (INFO first, SUCCESS last) as (the least width of a match, its nodes):
    ("char", op, pos): a test of one character (op at code[pos]); ("at", kind); ("mark", i);
    ("rep1", op, min, max, char): REPEAT_ONE, MIN_REPEAT_ONE or POSSESSIVE_REPEAT_ONE of a char;
    ("branch", [alternatives]); ("repeat", lazy, min, max, body); ("assert", negative, back, body);
    ("atomic", body); ("possrep", min, max, body); ("groupref", op, group); ("fail",)."""
    C = sys.modules[port.__name__ + "._constants"]
    if len(code) < 2 or code[0] != C.INFO:
        raise Unsupported("no INFO block")
    nodes, i, term = _seq(C, code, 1 + code[1])
    if term != "success" or i != len(code) - 1:
        raise Unsupported("code past its SUCCESS")
    return code[3], nodes


def _seq(C, code, i):
    # the nodes from code[i] to the SUCCESS, JUMP or UNTIL that ends them, its position and kind
    nodes = []
    while True:
        op = code[i]
        if op == C.SUCCESS:
            return nodes, i, "success"
        if op == C.JUMP:
            return nodes, i, "jump"
        if op == C.MAX_UNTIL or op == C.MIN_UNTIL:
            return nodes, i, "until"
        if op in (C.LITERAL, C.NOT_LITERAL, C.LITERAL_IGNORE, C.LITERAL_UNI_IGNORE, C.NOT_LITERAL_IGNORE,
                  C.NOT_LITERAL_UNI_IGNORE, C.CATEGORY):
            nodes.append(("char", op, i))
            i += 2
        elif op == C.ANY or op == C.ANY_ALL:
            nodes.append(("char", op, i))
            i += 1
        elif op in (C.IN, C.IN_IGNORE, C.IN_UNI_IGNORE):
            nodes.append(("char", op, i))
            i += 1 + code[i + 1]
        elif op == C.AT:
            nodes.append(("at", code[i + 1]))
            i += 2
        elif op == C.MARK:
            nodes.append(("mark", code[i + 1]))
            i += 2
        elif op == C.FAILURE:
            nodes.append(("fail",))
            i += 1
        elif op == C.BRANCH:
            # <BRANCH> <skip> alternative <JUMP> <offset> ... <FAILURE>: each JUMP to after the FAILURE
            p = i + 1
            alternatives = []
            targets = set()
            while code[p] != C.FAILURE:
                body, j, term = _seq(C, code, p + 1)
                if term != "jump":
                    raise Unsupported("an alternative without its JUMP")
                targets.add(j + 1 + code[j + 1])
                alternatives.append(body)
                p += code[p]
            if targets - {p + 1}:
                raise Unsupported("an alternative that jumps elsewhere")
            nodes.append(("branch", alternatives))
            i = p + 1
        elif op in (C.REPEAT_ONE, C.MIN_REPEAT_ONE, C.POSSESSIVE_REPEAT_ONE):
            # <op> <skip> <min> <max> item <SUCCESS> tail
            body, j, term = _seq(C, code, i + 4)
            if term != "success" or j != i + code[i + 1] or len(body) != 1 or body[0][0] != "char":
                raise Unsupported("a single-character repeat of something else")
            nodes.append(("rep1", op, code[i + 2], code[i + 3], body[0]))
            i += 1 + code[i + 1]
        elif op == C.REPEAT:
            # <REPEAT> <skip> <min> <max> item <MAX_UNTIL or MIN_UNTIL> tail
            body, j, term = _seq(C, code, i + 4)
            if term != "until" or j != i + 1 + code[i + 1]:
                raise Unsupported("a REPEAT without its UNTIL")
            nodes.append(("repeat", code[j] == C.MIN_UNTIL, code[i + 2], code[i + 3], body))
            i = j + 1
        elif op == C.ASSERT or op == C.ASSERT_NOT:
            # <op> <skip> <back> pattern <SUCCESS> tail
            body, j, term = _seq(C, code, i + 3)
            if term != "success" or j != i + code[i + 1]:
                raise Unsupported("an assertion without its SUCCESS")
            nodes.append(("assert", op == C.ASSERT_NOT, code[i + 2], body))
            i += 1 + code[i + 1]
        elif op == C.ATOMIC_GROUP:
            # <ATOMIC_GROUP> <skip> pattern <SUCCESS> tail
            body, j, term = _seq(C, code, i + 2)
            if term != "success" or j != i + code[i + 1]:
                raise Unsupported("an atomic group without its SUCCESS")
            nodes.append(("atomic", body))
            i += 1 + code[i + 1]
        elif op == C.POSSESSIVE_REPEAT:
            # <POSSESSIVE_REPEAT> <skip> <min> <max> pattern <SUCCESS> tail
            body, j, term = _seq(C, code, i + 4)
            if term != "success" or j != i + 1 + code[i + 1]:
                raise Unsupported("a possessive repeat without its SUCCESS")
            nodes.append(("possrep", code[i + 2], code[i + 3], body))
            i = j + 1
        elif op in (C.GROUPREF, C.GROUPREF_IGNORE, C.GROUPREF_UNI_IGNORE):
            nodes.append(("groupref", op, code[i + 1]))
            i += 2
        else:
            raise Unsupported(C.OPNAMES[op])


# ---- Python source from the nodes


class Ctx:
    # where nodes are generated: the parameters of the group repeats around them (a count and the
    # position its iteration began, for each), and whether a repeat's body holds them (then marks are
    # saved and restored at choices, as _sre does where state.repeat is set)
    def __init__(self, params, in_rep):
        self.params = params
        self.in_rep = in_rep


class Matcher:
    """The functions that match one pattern, compiled to code."""

    def __init__(self, port, module, rid, code):
        self.port = port
        self.C = sys.modules[port.__name__ + "._constants"]
        self.sre = sys.modules[port.__name__ + "._sre"]
        self.module = module
        self.rid = rid
        self.code = code
        self.info_min, self.nodes = parse(port, code)
        self.functions = []
        self.lines = 0
        self.repeats = 0
        self.made = 0  # (the functions named so far)

    def name(self, what):
        return "_p%d_%s" % (self.rid, what)

    # -- a character's test

    def table(self, char):
        # the 256 answers of the char's test, as _sre gives them, for the code points a subject read
        # in place can hold
        C = self.C
        sre = self.sre
        code = self.code
        _, op, p = char
        if op == C.IN:
            values = [sre.charset(code, p + 2, ch) for ch in range(256)]
        elif op == C.IN_IGNORE:
            values = [sre.charset(code, p + 2, sre.lower_ascii(ch)) for ch in range(256)]
        elif op == C.IN_UNI_IGNORE:
            values = [sre.charset(code, p + 2, sre.lower_unicode(ch)) for ch in range(256)]
        elif op == C.CATEGORY:
            values = [sre.category(code[p + 1], ch) for ch in range(256)]
        elif op == C.LITERAL_IGNORE:
            values = [sre.lower_ascii(ch) == code[p + 1] for ch in range(256)]
        elif op == C.LITERAL_UNI_IGNORE:
            values = [sre.lower_unicode(ch) == code[p + 1] for ch in range(256)]
        elif op == C.NOT_LITERAL_IGNORE:
            values = [sre.lower_ascii(ch) != code[p + 1] for ch in range(256)]
        elif op == C.NOT_LITERAL_UNI_IGNORE:
            values = [sre.lower_unicode(ch) != code[p + 1] for ch in range(256)]
        else:
            raise AssertionError(op)
        return self.module.table(bytes(int(v) for v in values))

    def test(self, char, x):
        # the expression: is the char's test true of s[x]
        C = self.C
        _, op, p = char
        if op == C.LITERAL:
            return "s[%s] == %d" % (x, self.code[p + 1])
        if op == C.NOT_LITERAL:
            return "s[%s] != %d" % (x, self.code[p + 1])
        if op == C.ANY:
            return "s[%s] != 10" % x
        if op == C.ANY_ALL:
            return "True"
        return "%s[s[%s]] != 0" % (self.table(char), x)

    # -- functions

    def args(self, ctx, extra=""):
        return "s, state, ptr, ne, d" + "".join(", " + p for p in ctx.params) + extra

    def function(self, name, ctx, body, extra_params=()):
        params = "".join(", %s: int" % p for p in list(ctx.params) + list(extra_params))
        lines = ["def %s(s: bytes, state, ptr: int, ne: int, d: int%s) -> int:" % (name, params),
                 "    end = state.end"]
        lines += body
        self.lines += len(lines)
        if self.lines > MAXLINES:
            raise Unsupported("more than %d lines" % MAXLINES)
        self.functions.append("\n".join(lines))

    def seq(self, nodes, ctx, term):
        # a new function of the nodes and then term: ("success", toplevel) or ("call", function),
        # which is called with the same parameters
        name = self.name(str(self.made))
        self.made += 1
        body = []
        self.body(body, nodes, ctx, term)
        self.function(name, ctx, body)
        return name

    def body(self, out, nodes, ctx, term):
        C = self.C
        k = 0
        while k < len(nodes):
            node = nodes[k]
            kind = node[0]
            if kind == "char":
                # a run of character tests, one check of the length
                run = [node]
                while k + len(run) < len(nodes) and nodes[k + len(run)][0] == "char":
                    run.append(nodes[k + len(run)])
                tests = [self.test(c, "ptr + %d" % i if i else "ptr") for i, c in enumerate(run)]
                tests = [t for t in tests if t != "True"]
                cond = "end - ptr < %d" % len(run) if len(run) > 1 else "ptr >= end"
                if tests:
                    cond += " or not (" + " and ".join(tests) + ")"
                out += ["    if %s:" % cond, "        return 0", "    ptr += %d" % len(run)]
                k += len(run)
                continue
            if kind == "at":
                out += self.at(node[1])
            elif kind == "mark":
                i = node[1]
                if i & 1:
                    out.append("    state.lastindex = %d" % (i // 2 + 1))
                if i == 0:
                    out += ["    if state.lastmark < 0:", "        state.lastmark = 0"]
                else:
                    # (the marks between the last one and i are not set)
                    out += ["    if %d > state.lastmark:" % i,
                            "        j = state.lastmark + 1",
                            "        while j < %d:" % i,
                            "            state.mark[j] = -1",
                            "            j += 1",
                            "        state.lastmark = %d" % i]
                out.append("    state.mark[%d] = ptr" % i)
            elif kind == "fail":
                out.append("    return 0")
                return
            elif kind == "groupref":
                out += self.groupref(node[1], node[2])
            elif kind == "rep1" and node[1] == C.POSSESSIVE_REPEAT_ONE:
                _, _, lo, hi, char = node
                out += ["    if ptr + %d > end:" % lo, "        return 0"]
                out += self.count(char, lo, hi)
                out += ["    if q - ptr < %d:" % lo, "        return 0", "    ptr = q"]
            elif kind == "assert":
                _, negative, back, sub = node
                f = self.seq(sub, Ctx([], ctx.in_rep), ("success", False))
                at = "ptr - %d" % back if back else "ptr"
                if not negative:
                    if back:
                        out += ["    if ptr < %d:" % back, "        return 0"]
                    out += ["    r = %s(s, state, %s, -1, d)" % (f, at), "    if r != 1:", "        return r"]
                else:
                    # (lookahead, or lookbehind with characters enough before ptr)
                    out += ["    if ptr >= %d:" % back,
                            "        lm = state.lastmark",
                            "        li = state.lastindex"]
                    if ctx.in_rep:
                        out.append("        _push(state, lm + 1)")
                    out += ["        r = %s(s, state, %s, -1, d)" % (f, at),
                            "        if r != 0:",
                            "            if r < 0:",
                            "                return r"]
                    if ctx.in_rep:
                        out.append("            _drop(state, lm + 1)")
                    out.append("            return 0")
                    if ctx.in_rep:
                        out.append("        _pop(state, lm + 1)")
                    out += ["        state.lastmark = lm", "        state.lastindex = li"]
            elif kind == "atomic":
                f = self.seq(node[1], Ctx([], ctx.in_rep), ("success", False))
                out += ["    r = %s(s, state, ptr, -1, d)" % f, "    if r != 1:", "        return r",
                        "    ptr = state.ptr"]
            elif kind == "possrep":
                _, lo, hi, sub = node
                f = self.seq(sub, Ctx([], True), ("success", False))
                out += ["    q = ptr", "    cnt = 0"]
                if lo > 0:
                    out += ["    while cnt < %d:" % lo,
                            "        r = %s(s, state, q, -1, d)" % f,
                            "        if r != 1:",
                            "            return r",
                            "        q = state.ptr",
                            "        cnt += 1"]
                out += ["    prev = -1",
                        "    while %sq != prev:" % ("" if hi == C.MAXREPEAT else "cnt < %d and " % hi),
                        "        lm = state.lastmark",
                        "        li = state.lastindex",
                        "        _push(state, lm + 1)",
                        "        prev = q",
                        "        r = %s(s, state, q, -1, d)" % f,
                        "        if r < 0:",
                        "            return r",
                        "        if r == 0:",
                        "            _pop(state, lm + 1)",
                        "            state.lastmark = lm",
                        "            state.lastindex = li",
                        "            q = prev",
                        "            break",
                        "        _drop(state, lm + 1)",
                        "        q = state.ptr",
                        "        cnt += 1",
                        "    ptr = q"]
            else:
                # a choice: the nodes after it are a function of their own, which it calls
                tail = self.seq(nodes[k + 1:], ctx, term)
                if kind == "rep1":
                    out += self.rep1(node, ctx, tail, nodes[k + 1] if k + 1 < len(nodes) else None)
                elif kind == "branch":
                    out += self.branch(node[1], ctx, tail)
                elif kind == "repeat":
                    out += self.repeat(node, ctx, tail)
                else:
                    raise AssertionError(kind)
                return
            k += 1
        # the end of the nodes
        if term[0] == "success":
            if term[1]:
                out += ["    if (state.match_all and ptr != end) or ptr == ne:", "        return 0"]
            out += ["    state.ptr = ptr", "    return 1"]
        else:
            out.append("    return %s(%s)" % (term[1], self.args(ctx)))

    def at(self, kind):
        C = self.C
        if kind == C.AT_BEGINNING or kind == C.AT_BEGINNING_STRING:
            cond = "ptr != 0"
        elif kind == C.AT_BEGINNING_LINE:
            cond = "ptr != 0 and s[ptr - 1] != 10"
        elif kind == C.AT_END:
            cond = "not ((end - ptr == 1 and s[ptr] == 10) or ptr == end)"
        elif kind == C.AT_END_LINE:
            cond = "not (ptr == end or (ptr < len(s) and s[ptr] == 10))"
        elif kind == C.AT_END_STRING:
            cond = "ptr != end"
        else:
            if kind in (C.AT_BOUNDARY, C.AT_NON_BOUNDARY, C.AT_LOC_BOUNDARY, C.AT_LOC_NON_BOUNDARY):
                word = self.module.table(bytes(int(self.sre.is_word(ch)) for ch in range(256)))
            elif kind in (C.AT_UNI_BOUNDARY, C.AT_UNI_NON_BOUNDARY):
                word = self.module.table(bytes(int(self.sre.uni_is_word(ch)) for ch in range(256)))
            else:
                raise Unsupported("AT %d" % kind)
            boundary = kind in (C.AT_BOUNDARY, C.AT_LOC_BOUNDARY, C.AT_UNI_BOUNDARY)
            cond = "end == 0 or (ptr > 0 and %s[s[ptr - 1]] != 0) %s (ptr < end and %s[s[ptr]] != 0)" % (
                word, "==" if boundary else "!=", word)
        return ["    if %s:" % cond, "        return 0"]

    def groupref(self, op, group):
        C = self.C
        if op == C.GROUPREF:
            same = "s[ptr] != s[p]"
        else:
            lower = self.sre.lower_ascii if op == C.GROUPREF_IGNORE else self.sre.lower_unicode
            folded = [lower(ch) for ch in range(256)]
            if max(folded) > 255:
                raise Unsupported("case folding past 255")
            t = self.module.table(bytes(folded))
            same = "%s[s[ptr]] != %s[s[p]]" % (t, t)
        return ["    if %d >= state.lastmark:" % (2 * group), "        return 0",
                "    p = state.mark[%d]" % (2 * group), "    e = state.mark[%d]" % (2 * group + 1),
                "    if p < 0 or e < 0 or e < p:", "        return 0",
                "    while p < e:",
                "        if ptr >= end or %s:" % same,
                "            return 0",
                "        p += 1",
                "        ptr += 1"]

    def count(self, char, lo, hi):
        # q: how far from ptr the char repeats, at most hi times (sre_count)
        C = self.C
        out = []
        if hi == C.MAXREPEAT:
            out.append("    lim = end")
        else:
            out.append("    lim = ptr + %d if %d < end - ptr else end" % (hi, hi))
        if char[1] == C.ANY_ALL:
            out.append("    q = lim")
        else:
            out += ["    q = ptr", "    while q < lim and %s:" % self.test(char, "q"), "        q += 1"]
        return out

    def attempt(self, call, ctx, indent):
        # call the tail (or an alternative): its result where it matched or gave up, else restore what
        # it changed, as _sre does after a failed nested match
        i = " " * indent
        out = [i + "r = " + call, i + "if r != 0:"]
        if ctx.in_rep:
            out += [i + "    if r > 0:", i + "        _drop(state, lm + 1)"]
        out.append(i + "    return r")
        if ctx.in_rep:
            out.append(i + "_keep(state, lm + 1)")
        out += [i + "state.lastmark = lm", i + "state.lastindex = li"]
        return out

    def save(self, ctx):
        out = ["    lm = state.lastmark", "    li = state.lastindex"]
        if ctx.in_rep:
            out.append("    _push(state, lm + 1)")
        return out

    def done(self, ctx):
        return (["    _drop(state, lm + 1)"] if ctx.in_rep else []) + ["    return 0"]

    def rep1(self, node, ctx, tail, after):
        # REPEAT_ONE (greedy: the most first, given back one at a time) or MIN_REPEAT_ONE (the least
        # first), as SRE(match) does
        C = self.C
        _, op, lo, hi, char = node
        call = "%s(s, state, q, ne, d%s)" % (tail, "".join(", " + p for p in ctx.params))
        out = ["    if %d > end - ptr:" % lo, "        return 0"]
        if op == C.REPEAT_ONE:
            out += self.count(char, lo, hi)
            out += ["    stop = ptr + %d" % lo, "    if q < stop:", "        return 0"]
            out += self.save(ctx)
            if after is not None and after[0] == "char" and after[1] == C.LITERAL:
                # the tail begins with a literal: skip the positions where it cannot match
                c = self.code[after[2] + 1]
                out += ["    while True:",
                        "        while q >= stop and (q >= end or s[q] != %d):" % c,
                        "            q -= 1",
                        "        if q < stop:",
                        "            break"]
                out += self.attempt(call, ctx, 8)
                out.append("        q -= 1")
            else:
                out.append("    while q >= stop:")
                out += self.attempt(call, ctx, 8)
                out.append("        q -= 1")
            return out + self.done(ctx)
        # MIN_REPEAT_ONE
        out.append("    q = ptr")
        if lo > 0:
            out += ["    stop = ptr + %d" % lo,
                    "    while q < stop and %s:" % self.test(char, "q"),
                    "        q += 1",
                    "    if q < stop:",
                    "        return 0"]
        out += self.save(ctx)
        if hi == C.MAXREPEAT:
            out.append("    while True:")
        else:
            out.append("    while q <= ptr + %d:" % hi)
        out += self.attempt(call, ctx, 8)
        out += ["        if q >= end or not (%s):" % self.test(char, "q"),
                "            break",
                "        q += 1"]
        return out + self.done(ctx)

    def branch(self, alternatives, ctx, tail):
        # BRANCH: each alternative, then the tail, until one matches
        out = self.save(ctx)
        for alt in alternatives:
            f = self.seq(alt, ctx, ("call", tail))
            call = "%s(%s)" % (f, self.args(ctx))
            if alt and alt[0][0] == "char":
                # (as SRE(match)'s test of an alternative's first literal or set)
                test = self.test(alt[0], "ptr")
                out.append("    if ptr < end%s:" % ("" if test == "True" else " and " + test))
                out += self.attempt(call, ctx, 8)
            else:
                out += self.attempt(call, ctx, 4)
        return out + self.done(ctx)

    def repeat(self, node, ctx, tail):
        # REPEAT with MAX_UNTIL or MIN_UNTIL: the UNTIL is a function of the repeat's count and the
        # position its iteration began, which the body ends by calling
        C = self.C
        _, lazy, lo, hi, sub = node
        self.repeats += 1
        n = self.repeats
        until = self.name("u%d" % n)
        inner = Ctx(list(ctx.params) + ["c%d" % n, "l%d" % n], True)
        body = self.seq(sub, inner, ("call", until))
        outer = "".join(", " + p for p in ctx.params)
        b = "%s(s, state, ptr, ne, d + 1%s, count, %%s)" % (body, outer)
        t = "%s(s, state, ptr, ne, d%s)" % (tail, outer)
        out = ["    if d > %d:" % DEPTH,
               "        return -1",
               "    count = rc + 1"]
        if lo > 0:
            out += ["    if count < %d:" % lo, "        return " + b % "rl"]
        more = "" if hi == C.MAXREPEAT else "count < %d and " % hi
        if not lazy:
            # MAX_UNTIL: another iteration where it may, the tail where it does not match
            out += ["    if %sptr != rl:" % more,
                    "        lm = state.lastmark",
                    "        li = state.lastindex",
                    "        _push(state, lm + 1)",
                    "        r = " + b % "ptr",
                    "        if r != 0:",
                    "            if r > 0:",
                    "                _drop(state, lm + 1)",
                    "            return r",
                    "        _pop(state, lm + 1)",
                    "        state.lastmark = lm",
                    "        state.lastindex = li",
                    "    return " + t]
        else:
            # MIN_UNTIL: the tail first, then another iteration
            out += self.save(ctx)
            out += ["    r = " + t, "    if r != 0:"]
            if ctx.in_rep:
                out += ["        if r > 0:", "            _drop(state, lm + 1)"]
            out.append("        return r")
            if ctx.in_rep:
                out.append("    _pop(state, lm + 1)")
            out += ["    state.lastmark = lm",
                    "    state.lastindex = li",
                    "    if %sptr == rl:" % ("" if hi == C.MAXREPEAT else "count >= %d or " % hi),
                    "        return 0",
                    "    return " + b % "ptr"]
        self.function(until, ctx, out, ("rc", "rl"))
        return ["    return %s(s, state, ptr, ne, d%s, -1, -1)" % (until, outer)]

    def generate(self):
        main = self.seq(self.nodes, Ctx([], False), ("success", True))
        m = ["def %s(s: bytes, state) -> int:" % self.name("match"),
             "    # sre_match() at the top level: from state.ptr",
             "    ptr = state.ptr"]
        if self.info_min > 0:
            m += ["    if state.end - ptr < %d:" % self.info_min, "        return 0"]
        m.append("    return %s(s, state, ptr, state.start if state.must_advance else -1, 0)" % main)
        a = ["def %s(s: bytes, state, toplevel: bool) -> int:" % self.name("attempt"),
             "    # sre_match() of the whole code where a search tries state.start",
             "    ptr = state.start",
             "    return %s(s, state, ptr, ptr if toplevel and state.must_advance else -1, 0)" % main]
        self.functions.append("\n".join(m))
        self.functions.append("\n".join(a))
        return self.functions


class Module:
    """The source of a _pystachy_re_specialized module: matchers, and the tables they share."""

    def __init__(self, port):
        self.port = port
        self.tables = {}  # name -> bytes
        self.names = {}  # bytes -> name
        self.patterns = []  # (pattern, flags, code, functions, note)
        self.skipped = []  # (pattern, flags, reason)

    def table(self, data):
        if data not in self.names:
            name = "_T%d" % len(self.names)
            self.names[data] = name
            self.tables[name] = data
        return self.names[data]

    def add(self, pattern, flags, note=""):
        """Generate the matcher of pattern with flags (as Pattern.flags gives them), or record why not."""
        if any(0xD800 <= ord(c) <= 0xDFFF for c in pattern):
            self.skipped.append((pattern, flags, "a surrogate in the pattern"))
            return False
        try:
            compiled = self.port.compile(pattern, flags)
        except Exception as e:  # (lib/re's error: CPython's too, for this pattern)
            self.skipped.append((pattern, flags, "%s: %s" % (type(e).__name__, e)))
            return False
        if compiled.flags != flags:
            self.skipped.append((pattern, flags, "compiles with flags %d" % compiled.flags))
            return False
        tables = dict(self.tables)
        names = dict(self.names)
        try:
            functions = Matcher(self.port, self, len(self.patterns), list(compiled._code)).generate()
        except Unsupported as e:
            self.tables = tables
            self.names = names
            self.skipped.append((pattern, flags, str(e)))
            return False
        self.patterns.append((pattern, flags, list(compiled._code), functions, note))
        return True

    def source(self, header):
        out = ['"""Matchers generated by tools/re_specialize.py for %d patterns: do not edit.' % len(self.patterns),
               "",
               "lib/re's Pattern runs the one generated for it (lookup()), in place of its interpreter,",
               "on the subjects it reads in place; see tools/re_specialize.py."]
        out += header
        out += ['"""', "",
                "# (pattern, flags) -> its matcher; and the code each was generated from, which lookup() checks",
                "_KEYS: dict[tuple[str, int], int] = {"]
        for i, (pattern, flags, _, _, note) in enumerate(self.patterns):
            out.append("    (%s, %d): %d,%s" % (_quote(pattern), flags, i, "  # " + note if note else ""))
        out += ["}", "_CODES: list[list[int]] = ["]
        for _, _, code, _, _ in self.patterns:
            out.append("    %r," % code)
        out += ["]", "",
                "",
                "def lookup(pattern: str, flags: int, code: list[int]) -> int:",
                "    # the matcher of the pattern compiled with flags to code, or -1",
                "    key = (pattern, flags)",
                "    if key in _KEYS:",
                "        i = _KEYS[key]",
                "        if _CODES[i] == code:",
                "            return i",
                "    return -1",
                "",
                ""]
        for entry in ("match", "attempt"):
            if entry == "match":
                out += ["def match(i: int, state) -> int:",
                        "    # sre_match() from state.ptr by matcher i: 1 or 0, or -1 where it declines (the interpreter",
                        "    # then runs), as on a subject not read in place"]
            else:
                out += ["def attempt(i: int, state, toplevel: bool) -> int:",
                        "    # sre_match() of the whole code at state.start by matcher i: 1 or 0, or -1 where it declines"]
            args = "s, state" if entry == "match" else "s, state, toplevel"
            if self.patterns:
                out += ["    s = state.s", "    if isinstance(s, bytes):"]
            for i in range(len(self.patterns)):
                out += ["        if i == %d:" % i, "            return _p%d_%s(%s)" % (i, entry, args)]
            out += ["    return -1", "", ""]
        if self.patterns:
            out += ["# the data stack's saved marks, as _sre's _mark_push(), _mark_pop() and _drop() keep them",
                    "def _push(state, n: int) -> None:",
                    "    data = state.data",
                    "    mark = state.mark",
                    "    for i in range(n):",
                    "        data.append(mark[i])",
                    "",
                    "",
                    "def _keep(state, n: int) -> None:",
                    "    # restore the marks saved last, and keep them saved",
                    "    data = state.data",
                    "    mark = state.mark",
                    "    base = len(data) - n",
                    "    for i in range(n):",
                    "        mark[i] = data[base + i]",
                    "",
                    "",
                    "def _pop(state, n: int) -> None:",
                    "    # restore the marks saved last, and drop them",
                    "    if n > 0:",
                    "        _keep(state, n)",
                    "        _drop(state, n)",
                    "",
                    "",
                    "def _drop(state, n: int) -> None:",
                    "    if n > 0:",
                    "        del state.data[len(state.data) - n:]",
                    "",
                    ""]
            for name, data in self.tables.items():
                out.append("%s = %s" % (name, _bytes(data)))
            if self.tables:
                out += ["", ""]
            for i, (pattern, flags, _, functions, _) in enumerate(self.patterns):
                out.append("# %d: %s, flags %d" % (i, _quote(pattern)[:100], flags))
                out.append("")
                out.append("\n\n\n".join(functions))
                out += ["", ""]
        while out and out[-1] == "":
            out.pop()
        return "\n".join(out) + "\n"


def _quote(s):
    # repr(s), with the characters past ASCII escaped, so that the module's source is ASCII
    return "".join(c if ord(c) < 128 else "\\u%04x" % ord(c) if ord(c) < 0x10000 else "\\U%08x" % ord(c)
                   for c in repr(s))


def _shown(s):
    # _quote(s) for a line of the module's docstring, its double quotes escaped: if longer than 80
    # characters, the quoted start of s, cut between characters (not inside an escape), and "..."
    q = _quote(s)
    if len(q) > 80:
        s = s[:75]
        while len(_quote(s)) > 77:
            s = s[:-1]
        q = _quote(s) + "..."
    return q.replace('"', '\\"')


def _text(s):
    # s for the module's docstring, where it reads as s: ASCII, its backslashes and double quotes escaped
    return _quote(s)[1:-1].replace('"', '\\"')


def _bytes(data):
    return "b'" + "".join("\\x%02x" % b for b in data) + "'"


# ---- profiles


def record(argv, out):
    """Run the program argv[0] with argv under CPython, as python PROGRAM does (by runpy.run_path, whose
    paths keep the spelling given: __file__, and a directory's or zip file's entry of sys.path),
    counting the matching calls made on each compiled pattern (through sys.monitoring: the calls of
    Pattern's methods, wherever made)."""
    import re
    out = os.path.abspath(out)  # (the program may change the working directory)
    counts = {}
    methods = {"match", "fullmatch", "search", "findall", "finditer", "split", "sub", "subn", "scanner"}
    mon = sys.monitoring
    # (a tool id that nothing holds, of no predefined tool first: a program's own debugger, coverage or
    # profiler keeps its id; a program that takes this one fails, as with any other tool on that id)
    tool = next((i for i in (4, 3, 5, 2, 1, 0) if mon.get_tool(i) is None), -1)
    if tool < 0:
        raise SystemExit("record: every sys.monitoring tool id is in use")
    mon.use_tool_id(tool, "re_specialize")

    # (p.search(s) calls Pattern.search with p first; m = p.match; m(s) calls the bound method: C types,
    # told apart by type alone, so that nothing of the program's own callables runs here)
    unbound = type(re.Pattern.match)
    bound = {type(re.compile("").match), type(re.compile("").findall)}

    def call(code, offset, callable, arg0):
        t = type(callable)
        if t is unbound:
            p = arg0 if callable.__objclass__ is re.Pattern else None
        elif t in bound:
            p = callable.__self__
        else:
            return
        if type(p) is re.Pattern and isinstance(p.pattern, str) and callable.__name__ in methods:
            key = (p.pattern, p.flags)
            counts[key] = counts.get(key, 0) + 1

    mon.register_callback(tool, mon.events.CALL, call)
    mon.set_events(tool, mon.events.CALL)
    saved = sys.argv, sys.path, sys.path[:]  # (the list itself too: the program may bind sys.path anew)
    sys.argv = list(argv)
    if not sys.flags.safe_path:
        # (python PROGRAM imports from the program's directory, in place of this tool's; from PROGRAM
        # itself where it is a directory or a zip file, which run_path then puts first)
        if pkgutil.get_importer(argv[0]) is None:
            sys.path[0] = os.path.dirname(os.path.realpath(argv[0]))
        else:
            del sys.path[0]
    status = 0
    error = None
    interrupt = None
    try:
        runpy.run_path(argv[0], run_name="__main__")
    except SystemExit as e:
        # (as python PROGRAM exits: with 0 for None, an int's status, else 1 once the value is printed)
        if e.code is None or isinstance(e.code, int):
            status = 0 if e.code is None else e.code
        else:
            error = e
            status = 1
    except Exception as e:
        # (as python PROGRAM ends on an uncaught exception; the calls made until then are still written)
        error = e
        status = 1
    except BaseException as e:
        # (KeyboardInterrupt: the calls made until then are written, then it is raised again)
        interrupt = e
    finally:
        if mon.get_tool(tool) == "re_specialize":  # (unless the program freed it)
            mon.set_events(tool, 0)
            mon.register_callback(tool, mon.events.CALL, None)
            mon.free_tool_id(tool)
        sys.argv, sys.path = saved[0], saved[1]
        sys.path[:] = saved[2]
    # (printed once calls are no longer counted: traceback's own patterns are not the program's)
    if isinstance(error, SystemExit):
        print(error.code, file=sys.stderr)
    elif error is not None:
        # (from the program's own frames, as python PROGRAM shows them: none where it did not run)
        tb = error.__traceback__
        while tb is not None and (tb.tb_frame.f_code.co_filename == record.__code__.co_filename or
                                  tb.tb_frame.f_globals.get("__name__") in RUNNERS):
            tb = tb.tb_next
        if tb is None and isinstance(error, OSError) and error.filename in (argv[0], os.path.abspath(argv[0])):
            print("%s: can't open file %r: [Errno %d] %s" % (sys.orig_argv[0], os.path.abspath(argv[0]), error.errno,
                                                             error.strerror),
                  file=sys.stderr)
            return 2  # (as python PROGRAM; no profile, of a program that did not run)
        if tb is None and isinstance(error, ImportError):
            print("%s: %s" % (sys.executable, error), file=sys.stderr)  # (a directory without __main__.py)
            return 1
        traceback.print_exception(type(error), error, tb, chain=tb is not None)
        if tb is None:
            return 1  # (the program did not run, as on its SyntaxError: no profile)
    profile = {"format": FORMAT, "program": argv[0],
               "patterns": [{"pattern": p, "flags": f, "calls": n}
                            for (p, f), n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]}
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(profile, fh, indent=1, ensure_ascii=True)
        fh.write("\n")
    if interrupt is not None:
        raise interrupt
    return status


def generate(profiles, patterns, min_calls, out):
    port = load_port()
    module = Module(port)
    seen = set()
    sources = []
    calls = {}  # (pattern, flags) -> its calls in all the profiles, in the order first seen
    for path in profiles:
        with open(path, encoding="utf-8") as fh:
            profile = json.load(fh)
        if profile.get("format") != FORMAT:
            raise SystemExit("%s: not a profile of format %d" % (path, FORMAT))
        sources.append(os.path.basename(path))
        for entry in profile["patterns"]:
            key = (entry["pattern"], entry["flags"])
            calls[key] = calls.get(key, 0) + entry["calls"]
    for key, n in calls.items():
        if n >= min_calls:
            seen.add(key)
            module.add(key[0], key[1], "%d calls" % n)
    for pattern, flags in patterns:
        try:
            flags = port.compile(pattern, flags).flags
        except Exception as e:  # (lib/re's error: CPython's too, for this pattern)
            module.skipped.append((pattern, flags, "%s: %s" % (type(e).__name__, e)))
            continue
        if (pattern, flags) not in seen:
            seen.add((pattern, flags))
            module.add(pattern, flags)
    header = ["", "From: %s." % _text(", ".join(sources + (["--pattern"] if patterns else [])) or "nothing")]
    if module.skipped:
        header += ["", "Not generated (lib/re's interpreter runs them):"]
        for pattern, flags, reason in module.skipped:
            header.append("  %s, flags %d: %s" % (_shown(pattern), flags, _text(reason)))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="ascii") as fh:
        fh.write(module.source(header))
    return module


def main(argv):
    if len(argv) >= 1 and argv[0] == "record":
        out = "re-profile.json"
        rest = argv[1:]
        if len(rest) >= 2 and rest[0] == "-o":
            out = rest[1]
            rest = rest[2:]
        if not rest:
            raise SystemExit(__doc__)
        return record(rest, out)
    if len(argv) >= 1 and argv[0] == "generate":
        out = "_pystachy_re_specialized.py"
        min_calls = 1
        profiles = []
        patterns = []
        i = 1
        while i < len(argv):
            a = argv[i]
            if a == "-o" and i + 1 < len(argv):
                out = argv[i + 1]
                i += 2
            elif a == "--min-calls" and i + 1 < len(argv):
                min_calls = int(argv[i + 1])
                i += 2
            elif a == "--pattern" and i + 1 < len(argv):
                pattern = argv[i + 1]
                flags = 0
                i += 2
                if i + 1 < len(argv) and argv[i] == "--flags":
                    flags = int(argv[i + 1])
                    i += 2
                patterns.append((pattern, flags))
            else:
                profiles.append(a)
                i += 1
        module = generate(profiles, patterns, min_calls, out)
        print("%s: %d matchers, %d patterns not generated" % (out, len(module.patterns), len(module.skipped)))
        return 0
    if len(argv) >= 1 and argv[0] == "check":
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import test_re_specialize
        n = int(argv[1]) if len(argv) > 1 else 400
        seed = int(argv[2]) if len(argv) > 2 else 1
        return 1 if test_re_specialize.fuzz(n, seed, verbose=True)[0] else 0
    raise SystemExit(__doc__)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
