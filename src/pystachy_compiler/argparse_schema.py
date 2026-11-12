"""Lower literal argparse declarations to an ordinary, statically typed Namespace."""
from __future__ import annotations

from src.pystachy_compiler.analysis import binds, globals_deep, names_name, scope_names, sole_binding
from src.pystachy_compiler.diagnostics import fail
from src.pystachy_compiler.lexer import KEYWORDS, Lexer
from src.pystachy_compiler.parser import Parser
from src.pystachy_compiler.syntax import Node, comp_names, mk


class SchemaError(Exception):
    def __init__(self, message: str, line: int):
        super().__init__(message)
        self.line = line


def reject(n: Node, message: str) -> None:
    raise SchemaError("argparse schema: " + message, n.line)


def parsed(source: str, line: int) -> list[Node]:
    return Parser(Lexer(source, line).file()).module().kids


def identifier(s: str) -> bool:
    return s != "" and not s.startswith("__") and s not in KEYWORDS and all([
        c == "_" or "A" <= c <= "Z" or "a" <= c <= "z" or (i > 0 and "0" <= c <= "9") for i, c in enumerate(s)
    ])


def string_arg(kws: dict[str, Node], key: str, default: str) -> str:
    if key not in kws:
        return default
    v = kws[key]
    if v.kind != "str":
        reject(v, key + " requires a literal string")
    return v.s


def literal_kind(n: Node) -> str:
    if n.kind == "unary" and n.s == "-" and n.kids[0].kind in ("int", "float"):
        return n.kids[0].kind
    return "bool" if n.kind in ("True", "False") else n.kind


def keywords(call: Node, allowed: list[str]) -> dict[str, Node]:
    kws: dict[str, Node] = {}
    for a in call.kids[1:]:
        if a.kind == "kw":
            if a.s not in allowed or a.s in kws:
                reject(a, "unsupported or repeated keyword " + a.s)
            kws[a.s] = a.kids[0]
    return kws


class Argument:
    def __init__(self, call: Node, shadowed: dict[str, bool], prefix: str):
        line = call.line
        kws = keywords(call, ["action", "type", "default", "dest", "nargs", "required", "choices", "metavar", "help", "version"])
        names: list[str] = []
        for a in call.kids[1:]:
            if a.kind != "kw":
                if a.kind != "str" or a.s == "" or a.s in names:
                    reject(a, "argument names must be distinct nonempty string literals")
                names.append(a.s)
        if len(names) == 0:
            # argparse accepts add_argument(dest="name", ...) as a positional.
            if "dest" not in kws or kws["dest"].kind != "str" or not identifier(kws["dest"].s):
                reject(call, "add_argument requires a literal name")
            names.append(kws["dest"].s)
            del kws["dest"]
        self.optional: bool = names[0].startswith("-")
        dest = names[0]
        if self.optional:
            for s in names:
                # One short option or a long option with an ASCII name.
                if not ((len(s) == 2 and s[0] == "-" and s[1].isalpha()) or
                        (s.startswith("--") and identifier(s[2:].replace("-", "_")))):
                    reject(call, "expected short or long option names")
            for s in names:
                if s.startswith("--"):
                    dest = s
                    break
            dest = dest.lstrip("-").replace("-", "_")
        elif len(names) != 1 or "dest" in kws or "required" in kws:
            reject(call, "a positional takes a single destination name")
        self.dest: str = string_arg(kws, "dest", dest)
        if not identifier(self.dest):
            reject(call, "dest must be a plain ASCII field name")
        self.action: str = string_arg(kws, "action", "store")
        if self.action not in ("store", "store_true", "store_false", "version"):
            reject(call, "unsupported action " + self.action)
        version = ""
        if self.action == "version":
            if not self.optional or "version" not in kws or any([k not in ("action", "version", "help") for k in kws]):
                reject(call, "version action requires an option and literal version text with optional help")
            version = string_arg(kws, "version", "")
            if "%(prog)" in version and "%" in version.replace("%%", "").replace("%(prog)s", ""):
                reject(call, "version formatting supports %% and %(prog)s")
        elif "version" in kws:
            reject(call, "version text requires the version action")
        flag = self.action in ("store_true", "store_false")
        self.nargs: str = string_arg(kws, "nargs", "")
        if "nargs" in kws and (self.optional or self.nargs not in ("?", "+", "*")):
            reject(call, "nargs supports positional '?', '+' and '*'")
        self.required: bool = not self.optional and self.nargs not in ("?", "*")
        if "required" in kws:
            if kws["required"].kind not in ("True", "False"):
                reject(call, "required must be a literal bool")
            self.required = kws["required"].kind == "True"
        self.kind: str = "bool" if flag else "str"
        if "type" in kws:
            v = kws["type"]
            if v.kind != "name" or v.s not in ("str", "int", "float") or v.s in shadowed:
                reject(v, "type must name the unshadowed builtin str, int or float")
            self.kind = v.s
        if flag and (not self.optional or "type" in kws or "choices" in kws or "metavar" in kws):
            reject(call, "boolean options take no value, conversion, choices or metavar")
        default = mk("True" if self.action == "store_false" else "False" if flag else "None", "", line, [])
        if "default" in kws:
            default = kws["default"]
            if self.nargs in ("*", "+") or (default.kind != "None" and literal_kind(default) != self.kind):
                reject(default, "default must be None or a scalar literal of the result type")
        self.default: Node = default
        self.names: list[str] = names
        choices: list[Node] = []
        if "choices" in kws:
            v = kws["choices"]
            if v.kind not in ("tuple", "list") or len(v.kids) == 0:
                reject(v, "choices requires a nonempty literal tuple or list")
            for item in v.kids:
                if literal_kind(item) != self.kind:
                    reject(item, "choices must match the converter")
                # The caller's integer policy and the normal expression lowering
                # determine the value, including wide and nondecimal literals.
                choices.append(item if self.kind == "str" else mk("call", "", line, [
                    mk("name", prefix + "_str", line, []), item
                ]))
            if self.nargs == "?" and default.kind == "str" and default.s not in [x.s for x in choices]:
                reject(default, "a string default for an optional positional must be one of its choices")
        help_text = string_arg(kws, "help", "show program's version number and exit" if self.action == "version" else "")
        if "%" in help_text.replace("%%", "").replace("%(prog)s", ""):
            reject(call, "help supports %% and %(prog)s")
        metavar = string_arg(kws, "metavar", "")
        if "metavar" in kws and metavar == "":
            reject(call, "metavar must be nonempty")
        call.kids[0].s = "_add"
        call.kids = [call.kids[0], mk("list", "", line, [mk("str", s, line, []) for s in names])]
        for s in [self.dest, self.action, self.kind, self.nargs]:
            call.kids.append(mk("str", s, line, []))
        call.kids += [mk("True" if self.required else "False", "", line, []), mk("list", "", line, choices),
                      mk("str", help_text, line, []), mk("str", metavar, line, []), mk("str", version, line, [])]


class Schema:
    def __init__(self, name: str, generated: str, constr: Node):
        self.name = name
        self.generated = generated
        self.line: int = constr.line
        self.arguments: list[Argument] = []
        self.options: list[str] = []
        self.parsed = False
        kws = keywords(constr, ["prog", "description", "add_help", "allow_abbrev"])
        for arg in constr.kids[1:]:
            if arg.kind != "kw":
                reject(arg, "ArgumentParser takes named literal options")
        for key in kws:
            v = kws[key]
            if key in ("add_help", "allow_abbrev"):
                if v.kind not in ("True", "False"):
                    reject(v, key + " must be a literal bool")
            elif v.kind not in ("None", "str"):
                reject(v, key + " must be a literal string or None")
            elif key == "description" and "%(prog)" in v.s and "%" in v.s.replace("%%", "").replace("%(prog)s", ""):
                reject(v, "description formatting supports %% and %(prog)s")
        if "add_help" not in kws or kws["add_help"].kind == "True":
            self.options = ["-h", "--help"]

    def add(self, n: Node, shadowed: dict[str, bool], prefix: str) -> None:
        if self.parsed:
            reject(n, "add_argument must precede parsing")
        arg = Argument(n, shadowed, prefix)
        for prev in self.arguments:
            if prev.dest == arg.dest and prev.action != "version" and arg.action != "version":
                reject(n, "duplicate destination " + arg.dest)
            if not arg.optional and prev.nargs in ("+", "*"):
                reject(n, "a variadic positional must be last")
        for s in arg.names if arg.optional else []:
            if s in self.options:
                reject(n, "duplicate option " + s)
            self.options.append(s)
        self.arguments.append(arg)

    def declarations(self, prefix: str) -> list[Node]:
        # Only checked identifiers and compiler-owned expressions enter this source.
        # Literal defaults are spliced into the parsed AST so user text is never code.
        ns = self.generated
        src = f"class {ns}({prefix}.Namespace):\n    def __init__(self, raw: {prefix}._Result):\n"
        # Version actions exit during parsing and have no Namespace field.
        fields = [i for i in range(len(self.arguments)) if self.arguments[i].action != "version"]
        for i in fields:
            a = self.arguments[i]
            # Explicit numeric converters have already been proven to be the
            # caller's builtins. Implicit text/flag fields can exist even if
            # that module shadows str or bool.
            typ = prefix + "._Text" if a.kind == "str" else prefix + "._Flag" if a.kind == "bool" else a.kind
            v = f"raw.values[{i}][0]"
            v = v if a.kind == "str" else f"{a.kind}({v})"
            if a.nargs in ("*", "+"):
                typ = prefix + "_list[" + typ + "]"
                v = f"raw.values[{i}]" if a.kind == "str" else f"[{a.kind}(x) for x in raw.values[{i}]]"
            else:
                if a.action != "store":
                    v = "True" if a.action == "store_true" else "False"
                if not a.required:
                    if a.default.kind == "None":
                        typ += " | None"
                    v += f" if raw.seen[{i}] else _pys_default"
            src += f"        self.{a.dest}: {typ} = {v}\n"
        if len(fields) == 0:
            src += "        pass\n"
        src += f"    def __repr__(self) -> {prefix}._Text:\n        fields: {prefix}_list[{prefix}._Text] = []\n"
        for i in fields:
            a = self.arguments[i]
            src += f"        fields.append('{a.dest}=' + {prefix}_repr(self.{a.dest}))\n"
        src += "        return 'Namespace(' + ', '.join(fields) + ')'\n"
        src += f"def {ns}_known(raw: {prefix}._Result):\n    return {ns}(raw), raw.extras\n"
        out = parsed(src, self.line)
        body = out[0].kids[0].kids[0].kids[0].kids[2]
        for field, i in enumerate(fields):
            value = body.kids[field].kids[-1]
            if value.kind == "ifexp":
                value.kids[2] = self.arguments[i].default
        return out


def captures(n: Node, name: str) -> bool:
    # Defaults, annotations and decorators run in the enclosing scope. The
    # function body sees its parameters and local bindings instead.
    if n.kind == "def":
        if any([names_name(k, name) for k in n.kids[:2] + n.kids[3:]]):
            return True
        if name in scope_names(n):
            return False
    if n.kind == "lambda" and any([p.s == name for p in n.kids[0].kids]):
        return names_name(n.kids[0], name)
    if n.kind in ("listcomp", "setcomp", "dictcomp"):
        bound: list[str] = []
        comp_names(n, bound)
        if name in bound:
            # Only the outermost iterable runs in the enclosing scope.
            return captures(n.kids[2], name)
    if n.kind == "name" and n.s == name:
        return True
    return any([captures(k, name) for k in n.kids])


def parse_uses(n: Node, schemas: dict[str, Schema]) -> None:
    if n.kind == "call" and n.kids[0].kind == "attr" and n.kids[0].kids[0].kind == "name" and n.kids[0].kids[0].s in schemas:
        method = n.kids[0].s
        schema = schemas[n.kids[0].kids[0].s]
        n.kids[0].kids[0].s = schema.name
        for kid in n.kids[1:]:
            parse_uses(kid, schemas)
        if method in ("parse_args", "parse_known_args"):
            if len(n.kids) > 2:
                reject(n, "parse accepts only an optional argv")
            arg = n.kids[1] if len(n.kids) == 2 else mk("None", "", n.line, [])
            if arg.kind == "kw" and arg.s == "args":
                arg = arg.kids[0]
            if arg.kind in ("kw", "starred", "dstar"):
                reject(arg, "parse accepts only an optional argv")
            schema.parsed = True
            n.kids[0].s = "_parse"
            raw = mk("call", "", n.line, [n.kids[0], arg, mk("True" if method == "parse_known_args" else "False", "", n.line, [])])
            target = schema.generated + ("_known" if method == "parse_known_args" else "")
            n.kids = [mk("name", target, n.line, []), raw]
            return
        if method in ("format_usage", "print_usage", "format_help", "print_help", "error", "exit"):
            return
        reject(n, "only direct declarations followed by supported parser methods are allowed")
    if n.kind in ("lambda", "class", "subclass", "def", "listcomp", "setcomp", "dictcomp"):
        if any([captures(n, k) for k in schemas]):
            reject(n, "parser must be used in its declaring scope")
        return
    if n.kind == "name" and n.s in schemas:
        reject(n, "parser cannot escape or be rebound")
    for kid in n.kids:
        parse_uses(kid, schemas)


def namespace_reads(n: Node, name: str, reads: list[Node]) -> bool:
    # Does code n use local name only to read its attributes? The reads in name's own scope are
    # collected; a function, class or comprehension in n may read attributes too. Any other use
    # (the bare name, a store through it, a declaration) may alias or change the object it holds.
    if n.kind == "attr" and n.kids[0].kind == "name" and n.kids[0].s == name:
        reads.append(n)
        return True
    if n.s == name and n.kind in ("name", "alias", "walrus", "global", "nonlocal", "except"):
        return False
    stores: list[Node] = []
    if n.kind == "assign":
        stores = n.kids[:-1]
    elif n.kind in ("augassign", "annassign", "for", "compfor"):
        stores = n.kids[:1]
    elif n.kind in ("listcomp", "asynccomp"):
        stores = n.kids[1:2]
    elif n.kind == "del":
        stores = n.kids
    elif n.kind == "withitem":
        stores = n.kids[1:]
    for t in stores:
        if names_name(t, name):
            return False
    inner = reads
    if n.kind in ("lambda", "def", "class", "subclass", "listcomp", "asynccomp", "setcomp", "dictcomp"):
        inner = []  # (another scope's reads stay reads of the field)
    for k in n.kids:
        if not namespace_reads(k, name, inner):
            return False
    return True


def copy_optional_fields(body: list[Node], schemas: dict[str, Schema]) -> None:
    # args = parser.parse_args(...) in a function's own statements, where the function then only
    # reads args.FIELD: nothing else holds the new Namespace, so no call can change its fields.
    # Each optional field the function reads is copied to a local of its own after the statement,
    # and the reads become that local, which a test narrows as it does any local:
    #     if args.output:
    #         open(args.output, "w")
    by: dict[str, Schema] = {}
    for k in schemas:
        by[schemas[k].generated] = schemas[k]
    for i in range(len(body) - 1, -1, -1):
        st = body[i]
        if st.kind != "assign" or len(st.kids) != 2 or st.kids[0].kind != "name" or st.kids[1].kind != "call":
            continue
        fn = st.kids[1].kids[0]
        if fn.kind != "name" or fn.s not in by:
            continue
        name = st.kids[0].s
        reads: list[Node] = []
        ok = sole_binding(body, i, name) and not names_name(st.kids[1], name)
        for j in range(len(body)):
            if j < i and names_name(body[j], name):
                ok = False
            elif j > i and not namespace_reads(body[j], name, reads):
                ok = False
        if not ok:
            continue
        schema = by[fn.s]
        copies: list[Node] = []
        for a in schema.arguments:
            if a.action == "version" or a.nargs in ("*", "+") or a.required or a.default.kind != "None":
                continue  # (not a field, or one that is never None: Schema.declarations())
            local = fn.s + "_" + name + "_" + a.dest
            used = False
            for r in reads:
                if r.kind == "attr" and r.s == a.dest:
                    r.kind = "name"
                    r.s = local
                    r.kids = []
                    used = True
            if used:
                field = mk("attr", a.dest, st.line, [mk("name", name, st.line, [])])
                copies.append(mk("assign", "", st.line, [mk("name", local, st.line, []), field]))
        for c in reversed(copies):
            body.insert(i + 1, c)


def dotted_name(n: Node) -> str:
    if n.kind == "name":
        return n.s
    if n.kind == "attr" and n.kids[0].kind == "name":
        return n.kids[0].s + "." + n.s
    return ""


def lower_scope(body: list[Node], aliases: dict[str, int], shadowed: dict[str, bool], prefix: str, made: list[Node], top: bool) -> None:
    schemas: dict[str, Schema] = {}
    for i in range(len(body)):
        st = body[i]
        if st.kind == "assign" and len(st.kids) == 2 and st.kids[1].kind == "call":
            ctor = st.kids[1]
            origin = dotted_name(ctor.kids[0])
            if origin in aliases and aliases[origin] <= st.line:
                dest = st.kids[0]
                if dest.kind != "name" or not sole_binding(body, i, dest.s):
                    reject(st, "assign ArgumentParser to a single fresh name")
                generated = prefix + str(len(made)) + "_" + str(len(schemas))
                # A module global is otherwise visible to imports from other modules,
                # which cannot participate in this scope's schema proof.
                name = generated + "_parser" if top else dest.s
                schemas[dest.s] = Schema(name, generated, ctor)
                dest.s = name
                ctor.kids[0] = mk("attr", "_Parser", st.line, [mk("name", prefix, st.line, [])])
                ctor.kids.append(mk("kw", "_int_text", st.line, [mk("name", prefix + "_int", st.line, [])]))
                continue
        if st.kind == "expr" and len(st.kids) == 1 and st.kids[0].kind == "call":
            call = st.kids[0]
            fn = call.kids[0]
            if fn.kind == "attr" and fn.s == "add_argument" and fn.kids[0].kind == "name" and fn.kids[0].s in schemas:
                schema = schemas[fn.kids[0].s]
                fn.kids[0].s = schema.name
                schema.add(call, shadowed, prefix)
                continue
        if len(schemas) > 0:
            parse_uses(st, schemas)
    for k in schemas:
        # A definition before the constructor may also capture the later binding.
        for st in body:
            if st.kind in ("def", "class", "subclass") and captures(st, k):
                reject(st, "parser must be used in its declaring scope")
        made += schemas[k].declarations(prefix)
    if not top and len(schemas) > 0:
        copy_optional_fields(body, schemas)


def uses_prefix(n: Node, prefix: str) -> bool:
    if n.s.startswith(prefix):
        return True
    return any([uses_prefix(k, prefix) for k in n.kids])


def parser_import(n: Node) -> str:
    for a in n.kids if n.kind == "import" else []:
        if a.kind == "alias" and len(a.kids) == 2 and a.kids[1].s == "argparse":
            if n.s == "from" and a.kids[0].s == "argparse.ArgumentParser":
                return a.s
            if n.s == "":
                return a.s + ".ArgumentParser"
    return ""


def lower_argparse(body: Node) -> None:
    aliases: dict[str, int] = {}
    at = -1
    for i in range(len(body.kids)):
        name = parser_import(body.kids[i])
        if name != "" and sole_binding(body.kids, i, name.split(".")[0]):
            aliases[name] = body.kids[i].line
            if at < 0:
                at = i
    if len(aliases) == 0:
        return
    prefix = "_pys_argparse"
    while uses_prefix(body, prefix):
        prefix += "_"
    bound: dict[str, bool] = {}
    binds(body.kids, bound, True)
    globals_deep(body.kids, bound)
    made: list[Node] = []
    try:
        lower_scope(body.kids, aliases, bound, prefix, made, True)
    except SchemaError as exc:
        fail(str(exc), exc.line)
    for st in body.kids:
        if st.kind == "def":
            local = scope_names(st)
            visible = {a: aliases[a] for a in aliases if a.split(".")[0] not in local}
            shadowed = bound.copy()
            shadowed.update(local)
            try:
                lower_scope(st.kids[2].kids, visible, shadowed, prefix, made, False)
            except SchemaError as exc:
                # Match other unsupported function-local imports. Leave the
                # diagnostic on the function so an unused template stays dormant.
                st.kids[2].kids = [mk("badimport", str(exc), exc.line, [])]
    if len(made) > 0:
        line = body.kids[at].line
        imports = f"import argparse as {prefix}\nfrom typing import List as {prefix}_list\n"
        imports += f"from builtins import str as {prefix}_str, repr as {prefix}_repr, int as {prefix}_to_int\n"
        helper = f"def {prefix}_int(s: {prefix}._Text) -> {prefix}._Text:\n    return {prefix}_str({prefix}_to_int(s))\n"
        body.kids = body.kids[:at + 1] + parsed(imports + helper, line) + made + body.kids[at + 1:]
