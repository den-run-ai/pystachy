"""Bounded structural patterns lowered to ordinary typed branches."""
from __future__ import annotations
from src.pystachy_compiler.ir import Val
from src.pystachy_compiler.syntax import Node, made_var, mk
from src.pystachy_compiler.utils import clone, is_tuple, is_union, targs, typestr, unopt


# subject types that are never sequences to a sequence pattern (CPython excludes str and bytes)
SEQ_SCALARS: list[str] = ["int", "int+", "float", "bool", "str", "bytes", "None"]


def pattern_then(test: Node, tail: Node, line: int) -> Node:
    # Only test's compiler-generated conjunction is flattened. Its operands
    # already produce condition booleans, so reassociation preserves callback
    # order and short circuiting. OR alternatives and tail (possibly the user's
    # guard) stay intact. Keeping later reads inside each successful operand's
    # RHS lets ordinary flow analysis see the preceding staged assignments.
    if test.kind == "boolop" and test.s == "and":
        return mk("boolop", "and", line, [test.kids[0], pattern_then(test.kids[1], tail, line)])
    return mk("boolop", "and", line, [test, tail])


def conjunction(parts: list[Node], line: int) -> Node:
    if len(parts) == 0:
        return mk("True", "", line, [])
    out = parts[-1]
    for i in range(len(parts) - 2, -1, -1):
        out = pattern_then(parts[i], out, line)
    return out


def unsupported_pattern(node: Node) -> Node | None:
    # the first pattern in node, in source order, that this lowering does not support: a
    # mapping, a starred name in a sequence, or a complex literal
    if node.kind in ["pmap", "pstar"] or (node.kind == "pnum" and "j" in node.s):
        return node
    for child in node.kids:
        bad = unsupported_pattern(child)
        if bad is not None:
            return bad
    return None


def unsupported_match(st: Node) -> Node | None:
    # the first unsupported pattern among the cases of match statement st, or None
    for i in range(1, len(st.kids), 2):
        bad = unsupported_pattern(st.kids[i].kids[-1])
        if bad is not None:
            return bad
    return None


def unsupported_reason(node: Node) -> str:
    # the diagnostic for unsupported_pattern's node
    if node.kind == "pmap":
        return "mapping patterns are not supported"
    if node.kind == "pstar":
        return "starred sequence patterns are not supported; use a fixed tuple pattern"
    return "complex literal patterns are not supported"


def wildcard(pattern: Node) -> bool:
    return pattern.kind == "pas" and pattern.s == "" and len(pattern.kids) == 0


def leaf_pattern(pattern: Node) -> bool:
    # a pattern that only compares or binds its subject: no nested sequence or class pattern
    if pattern.kind == "pvalue" or pattern.kind == "pconst":
        return True
    if pattern.kind == "pas" or pattern.kind == "por":
        return all(leaf_pattern(p) for p in pattern.kids)
    return False


def pattern_captures(pattern: Node, out: list[str]) -> None:
    # The retained tree has already had private names mangled. OR alternatives
    # bind the same names, but may encounter them in different orders.
    for child in pattern.kids:
        pattern_captures(child, out)
    if pattern.kind == "pas" and pattern.s != "" and pattern.s not in out:
        out.append(pattern.s)


def pattern_test(pattern: Node, subject: Node, counter: list[int], captures: dict[str, str]) -> Node:
    k = pattern.kind
    line = pattern.line
    if k == "pas":
        parts = [pattern_test(pattern.kids[0], clone(subject), counter, captures)] if len(pattern.kids) > 0 else []
        if pattern.s != "":
            # A later subpattern may fail, or its equality callback may read the
            # old user binding. Stage each value without asking for its truth;
            # the case commits user names only once the entire pattern succeeds.
            parts.append(mk("matchbind", "", line, [mk("walrus", captures[pattern.s], line, [clone(subject)])]))
        return conjunction(parts, line)
    if k == "pconst":
        return mk("matchconst", pattern.s, line, [clone(subject)])
    if k == "pvalue":
        value = clone(pattern.kids[0])
        if value.kind == "pnum":
            if "j" in value.s:
                return mk("matchunsupported", unsupported_reason(value), line, [])
            # Very large binary/octal/hex literals retain a canonical 0x form.
            # Its hexadecimal 'e' digits are not a floating-point exponent.
            digits = value.s[1:] if value.s.startswith("-") else value.s
            floating = not digits.startswith("0x") and ("." in digits or "e" in digits.lower() or "inf" in digits)
            value = mk("float" if floating else "int", value.s, line, [])
        return mk("matchvalue", "", line, [clone(subject), value])
    if k == "por":
        out = pattern_test(pattern.kids[0], clone(subject), counter, captures)
        for alt in pattern.kids[1:]:
            out = mk("boolop", "or", line, [out, pattern_test(alt, clone(subject), counter, captures)])
        return out
    if k == "pseq":
        stars = [p for p in pattern.kids if p.kind == "pstar"]
        if len(stars) > 0:
            return mk("matchunsupported", unsupported_reason(stars[0]), line, [])
        parts = [mk("matchseq", str(len(pattern.kids)), line, [clone(subject)])]
        items: list[Node] = []
        for i in range(len(pattern.kids)):
            item = mk("index", "", line, [clone(subject), mk("int", str(i), line, [])])
            if leaf_pattern(pattern.kids[i]) and not wildcard(pattern.kids[i]):
                # CPython unpacks every item (UNPACK_SEQUENCE) before it matches the first
                # subpattern; reading a fixed tuple's items first runs no code. Staged reads
                # leave the comparisons free of loads, which branch-free code can then join.
                # A nested sequence or class pattern keeps its item's index expression, from
                # which pattern_type knows the item's type before any of it is compiled.
                counter[0] += 1
                name = f"__pys_match_item_{line}.{counter[0]}"
                parts.append(mk("matchbind", "", line, [mk("walrus", name, line, [item])]))
                item = made_var(name, line)
            items.append(item)
        for i in range(len(pattern.kids)):
            parts.append(pattern_test(pattern.kids[i], items[i], counter, captures))
        return conjunction(parts, line)
    if k == "pclass":
        cls = pattern.kids[0]
        # The class check validates every requested field, even a wildcard field.
        labels = [str(i) if p.kind != "pkw" else p.s for i, p in enumerate(pattern.kids[1:])]
        parts = [mk("matchclass", " ".join(labels), line, [clone(subject), clone(cls)])]
        held: list[Node] = []
        for i in range(len(pattern.kids) - 1):
            part = pattern.kids[i + 1]
            field = mk("matchfield", str(i) if part.kind != "pkw" else part.s, line, [clone(subject), clone(cls)])
            # CPython obtains the class pattern's attributes before it compares
            # their values. An equality callback may change a later field.
            counter[0] += 1
            name = f"__pys_match_field_{line}.{counter[0]}"
            parts.append(mk("matchbind", "", line, [mk("walrus", name, line, [field])]))
            held.append(made_var(name, line))
        for i in range(len(held)):
            part = pattern.kids[i + 1]
            parts.append(pattern_test(part.kids[0] if part.kind == "pkw" else part, held[i], counter, captures))
        return conjunction(parts, line)
    return mk("matchunsupported", unsupported_reason(pattern) if k == "pmap" else "unsupported pattern", line, [])


def lower_matches(node: Node, counter: list[int], class_body: bool = False) -> None:
    # Parsing and symbol-table checks still see the original patterns. Afterwards,
    # rewrite each match to one subject assignment and an if/elif chain. No runtime
    # matcher, boxed subject, or compiler-wide speculative state is introduced.
    for child in node.kids:
        lower_matches(child, counter, node.kind == "class" and child.kind == "block")
    if node.kind != "block" or class_body:
        # A class body holds fields and methods only: the class-body check rejects
        # its match statements as it rejects an if statement there, rather than
        # the subject and captures becoming class attributes.
        return
    body: list[Node] = []
    for st in node.kids:
        if st.kind != "match":
            body.append(st)
            continue
        if unsupported_match(st) is not None:
            # Keep unsupported patterns in their original AST: captures in a
            # dropped or uncalled match must still be locals of that scope. Code
            # generation reports the first such pattern (unsupported_reason).
            body.append(st)
            continue
        counter[0] += 1
        name = f"__pys_match_subject_{st.line}.{counter[0]}"
        body.append(mk("assign", "", st.line, [made_var(name, st.line), st.kids[0]]))
        tail = mk("block", "", st.line, [])
        for i in range(len(st.kids) - 2, 0, -2):
            pattern = st.kids[i]
            names: list[str] = []
            pattern_captures(pattern.kids[-1], names)
            captures: dict[str, str] = {}
            for capture in names:
                counter[0] += 1
                captures[capture] = f"__pys_match_capture_{pattern.line}.{counter[0]}"
            tests = [pattern_test(pattern.kids[-1], made_var(name, st.line), counter, captures)]
            for capture in names:
                tests.append(mk("matchbind", "", pattern.line, [mk("walrus", capture, pattern.line, [made_var(captures[capture], pattern.line)])]))
            test = conjunction(tests, pattern.line)
            if pattern.kids[0].kind != "True":
                test = conjunction([test, pattern.kids[0]], pattern.line)
            branch = mk("if", "", pattern.line, [test, st.kids[i + 1], tail])
            tail = mk("block", "", pattern.line, [branch])
        body.extend(tail.kids)
    node.kids = body


def pattern_class(self, node: Node) -> str:
    cls = node.kids[1]
    if cls.kind != "name" or cls.s not in self.classes or cls.s in self.ltype or not self.is_dc(cls.s):
        self.err("class patterns require a statically known dataclass")
    ci = self.classes[cls.s]
    if ci.tag > 0 or ci.hook != "" or "__match_args__" in ci.ftypes or "__match_args__" in ci.fdefault or "__match_args__" in ci.methods:
        self.err("class patterns require a dataclass without a hierarchy, attribute hooks or custom __match_args__")
    return cls.s


def pattern_field(self, cls: str, label: str) -> str:
    ci = self.classes[cls]
    name = label
    if label.isdigit():
        fields = [f for f in self.dc_fields(ci) if "no-init" not in ci.fopts.get(f, {}) and "kw_only" not in ci.fopts.get(f, {})]
        if "no-match_args" in ci.dcopts:
            fields = []
        i = int(label)
        if i >= len(fields):
            self.err(f"{cls}() accepts {len(fields)} positional sub-patterns ({i + 1} given)")
        name = fields[i]
    if name not in ci.ftypes or name in ci.methods or name in ci.fflag:
        self.err(f"class pattern attribute '{name}' requires an initialized plain dataclass field")
    return name


def pattern_class_subject(self, t: str) -> None:
    # A boxed/tagged value can contain the requested class even when its storage
    # type has another name. This bounded matcher cannot fold that possibility
    # away, and currently has no runtime dispatch/narrowing for those subjects.
    if t == "dyn" or is_union(unopt(t)):
        self.err("class patterns require a concrete subject type; dynamic Any and union subjects are not supported")


def pattern_static(self, node: Node) -> int:
    t = pattern_type(self, node.kids[0])
    if node.kind == "matchclass":
        cls = pattern_class(self, node)
        pattern_class_subject(self, t)
        return 0 if t != "" and t != cls else -1
    if t == "":
        return -1
    if is_tuple(t):
        return 1 if len(targs(t)) == int(node.s) else 0
    if t in SEQ_SCALARS:
        return 0
    self.err(f"sequence patterns require a fixed tuple subject, got {typestr(t)}")
    return -1


def pattern_type(self, node: Node) -> str:
    if node.kind == "index" and node.kids[1].kind == "int":
        parent = pattern_type(self, node.kids[0])
        i = int(node.kids[1].s)
        if is_tuple(parent) and i < len(targs(parent)):
            return targs(parent)[i]
        return ""
    return self.static_type(node)


def pattern_expr(self, node: Node) -> Val:
    k = node.kind
    if k == "matchunsupported":
        self.err(node.s)
    if k == "matchbind":
        self.expr(node.kids[0], "")
        return Val("true", "bool")
    if k == "matchconst":
        value = self.expr(node.kids[0], "")
        if node.s != "None" and value.t not in ["bool", "dyn"]:
            if is_union(unopt(value.t)) or value.t == "opt[bool]":
                self.err("boolean singleton patterns require a concrete bool or dynamic Any subject")
            return Val("false", "bool")
        op = "==" if value.t == "bool" and node.s != "None" else "is"
        return self.expr(mk("cmp", op, node.line, [self.vnode(value), mk(node.s, "", node.line, [])]), "bool")
    if k == "matchvalue":
        left = self.expr(node.kids[0], "")
        right = self.expr(node.kids[1], "")
        scalars = ["int", "int+", "float", "bool", "str", "bytes", "None"]
        numeric = ["int", "int+", "float", "bool"]
        if left.t in scalars and right.t in scalars and left.t != right.t and not (left.t in numeric and right.t in numeric):
            return Val("false", "bool")
        return self.expr(mk("cmp", "==", node.line, [self.vnode(left), self.vnode(right)]), "bool")
    if k == "matchseq":
        value = self.expr(node.kids[0], "")
        if value.t in SEQ_SCALARS:
            return Val("false", "bool")  # (as pattern_static decides where it knows the type)
        if not is_tuple(value.t):
            self.err(f"sequence patterns require a fixed tuple subject, got {typestr(value.t)}")
        return Val("true" if len(targs(value.t)) == int(node.s) else "false", "bool")
    cls = pattern_class(self, node)
    value = self.expr(node.kids[0], "")
    pattern_class_subject(self, value.t)
    self.isinst_reads(node.kids[1])
    if k == "matchclass":
        names: list[str] = []
        for label in node.s.split():
            name = pattern_field(self, cls, label)
            if name in names:
                self.err(f"{cls}() got multiple sub-patterns for attribute '{name}'")
            names.append(name)
        return self.ptr_cmp("!=", value, Val("null", "None")) if value.t == cls else Val("false", "bool")
    if value.t != cls:
        self.err("a dataclass pattern field requires a subject of that dataclass's concrete type")
    name = pattern_field(self, cls, node.s)
    return self.getfield(value, self.field(value, name), name)
